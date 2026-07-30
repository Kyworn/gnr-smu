#!/usr/bin/env python3
"""Dump the PM table, labelled from PM_TABLE_MAP.md.

Two modes, chosen by the hardware gate rather than by a flag:

  validated hardware   every float with its documented meaning and confidence level
  anything else        raw values only, no labels

The labels used to live in a dict right here, which meant a third hand-maintained
copy of the map alongside the GUI and the exporter — and it drifted badly. By the
time it was noticed it still called d[3] "Package Temp", d[8] "EDC Limit" and d[10]
"TDC Limit", all three of which the zone 0x000 correction had already disproved, plus
a row of energy accumulators that do not accumulate. So it reads the map instead. One
source of truth, and a stale label is now impossible rather than merely unlikely.

The raw mode is the point of the unvalidated path: a dump from another Granite Ridge
part is the one thing that would let the map grow past this one machine, and refusing
to produce it would be refusing the contribution.

Run: sudo python3 tools/dump_table_full.py
"""

import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hwgate import hardware_supported  # noqa: E402

PM = "/sys/kernel/ryzen_smu_drv/pm_table"
MAP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "PM_TABLE_MAP.md")
N = 457

ROW = re.compile(r"^\|\s*0x[0-9A-Fa-f]+(?:-0x[0-9A-Fa-f]+)?\s*\|"
                 r"\s*(\d+(?:-\d+)?)\s*\|")


def labels():
    """{index: (meaning, confidence)} parsed from the map's tables."""
    out = {}
    for line in open(MAP, encoding="utf-8"):
        line = line.strip()
        m = ROW.match(line)
        if not m:
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < 6:
            continue  # malformed row; audit_map.py fails on these
        meaning = cols[4].replace("**", "")
        conf = cols[5].split("(")[0].strip()
        idx = m.group(1)
        if "-" in idx:
            a, b = (int(x) for x in idx.split("-"))
            rng = range(a, b + 1)
        else:
            rng = [int(idx)]
        for i in rng:
            out.setdefault(i, (meaning, conf))
    return out


def main():
    with open(PM, "rb") as f:
        data = f.read(N * 4)
    if len(data) != N * 4:
        sys.exit(f"unexpected table size: {len(data)} bytes, expected {N * 4}")
    floats = struct.unpack(f"<{N}f", data)

    ok, why = hardware_supported()
    if not ok:
        print(f"# unvalidated hardware: {why}")
        print("# raw values only — the offsets in PM_TABLE_MAP.md do not apply here.")
        print(f"# Please attach this dump and your CPU model to an issue.\n")
        for i, v in enumerate(floats):
            print(f"d[{i:3}] (0x{i * 4:03X}) = {v:14.4f}")
        return

    print(f"# {why}")
    print("# meanings truncated — see PM_TABLE_MAP.md for the full row and evidence\n")
    lab = labels()
    for i, v in enumerate(floats):
        meaning, conf = lab.get(i, ("", ""))
        if len(meaning) > 88:
            meaning = meaning[:87].rstrip() + "…"
        print(f"d[{i:3}] (0x{i * 4:03X}) = {v:14.4f}"
              + (f"  {conf:<9} {meaning}" if meaning else ""))


if __name__ == "__main__":
    main()
