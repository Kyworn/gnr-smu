#!/usr/bin/env python3
"""Compare community PM-table bundles: layout vs layout, index vs index.

Usage:
  python3 research/compare_tables.py bundleA bundleB [bundleC ...]
  python3 research/compare_tables.py --block 172 --block 180 --block 212 bundleA bundleB

Each bundle is a directory from tools/submit_dump.py (meta.json + *.bin).
Comparison is only meaningful within one (pm_version, size); mixed versions
are reported per bundle but not compared index-wise.

For each bundle the tool reports:
  1. detected active SMU slots (zero-signature detection, no assumed tuple)
  2. topology consistency (physical cores from meta vs detected slots)
  3. whether the detected layout matches the locally validated profile
     tuple for that table (i.e. what _fused_layout_matches would decide)

Across bundles of the same table it reports:
  4. indices bit-identical everywhere (layout-common candidates: clocks,
     rails, limits) vs indices that differ (machine/load-specific)

Block bases default to the locally known profile for the bundle's table
(currently the Vermeer 0x380905 profile); use --block to override for
unmapped tables.  Only zero-signature blocks may be passed: a present core
must never legitimately read exactly 0.0 there (never temperature or
effective frequency).
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "tools"))
from hwgate import PROFILES, detect_active_slots  # noqa: E402


def load_bundle(path):
    with open(os.path.join(path, "meta.json")) as f:
        meta = json.load(f)
    snaps = {}
    for name in meta.get("snapshots", []):
        with open(os.path.join(path, name), "rb") as f:
            data = f.read()
        if len(data) != meta["pm_table_size"]:
            raise ValueError(f"{path}/{name}: size mismatch")
        n = meta["pm_table_size"] // 4
        snaps[name] = struct.unpack(f"<{n}f", data)
    return meta, snaps


def profile_bases(meta):
    key = (int(meta["pm_table_version"], 16), meta["pm_table_size"],
           meta["physical_cores"])
    prof = PROFILES.get(key)
    if prof is None:
        return None, None
    return prof, (prof.core_power, prof.core_voltage, prof.core_frequency)


def detect_bundle_layout(snaps, bases, width=8):
    active = set()
    for values in snaps.values():
        active |= set(detect_active_slots(values, bases, width))
    return tuple(sorted(active))


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bundles", nargs="+")
    ap.add_argument("--block", type=int, action="append", default=[],
                    help="zero-signature per-core block base (repeatable)")
    ap.add_argument("--width", type=int, default=8)
    args = ap.parse_args()

    loaded = [(b, *load_bundle(b)) for b in args.bundles]
    tables = {(m["pm_table_version"], m["pm_table_size"]) for _, m, _ in loaded}

    print(f"bundles: {len(loaded)}")
    layouts = {}
    for path, meta, snaps in loaded:
        print(f"\n== {path}")
        print(f"  CPU: {meta.get('cpu_model')} "
              f"({meta.get('physical_cores')}C/{meta.get('threads')}T), "
              f"PM {meta.get('pm_table_version')} "
              f"({meta.get('pm_table_size')} bytes), "
              f"snapshots: {list(snaps)}")
        prof, auto = profile_bases(meta)
        bases = tuple(args.block) if args.block else auto
        if bases is None:
            print("  no local profile for this table and no --block given: "
                  "layout detection skipped")
            continue
        layout = detect_bundle_layout(snaps, bases, args.width)
        layouts[path] = layout
        print(f"  detected active slots: {list(layout)} "
              f"(blocks {[hex(b * 4) for b in bases]})")
        ncores = meta.get("physical_cores")
        if ncores != len(layout):
            print(f"  WARNING: {ncores} physical cores but "
                  f"{len(layout)} active slots")
        else:
            print(f"  topology consistent: {ncores} cores == "
                  f"{len(layout)} slots")
        if prof is not None and prof.core_slots:
            if set(layout) == set(prof.core_slots):
                print(f"  matches validated {prof.name} layout "
                      f"{list(prof.core_slots)}: would be ACCEPTED")
            else:
                print(f"  differs from validated {prof.name} layout "
                      f"{list(prof.core_slots)}: would be REFUSED "
                      f"(fail closed, no telemetry mislabelled)")

    if len(tables) != 1:
        print("\nMixed PM tables present "
              f"{sorted(f'{v} ({s}B)' for v, s in tables)}: "
              "index-wise comparison skipped.")
        return

    print("\n== cross-bundle index comparison ==")
    all_snaps = [(path, name, vals)
                 for path, _, snaps in loaded for name, vals in snaps.items()]
    n = len(all_snaps[0][2])
    identical, varying = [], []
    for i in range(n):
        vals = [v[i] for _, _, v in all_snaps]
        (identical if all(v == vals[0] for v in vals) else varying).append(i)
    print(f"bit-identical across all {len(all_snaps)} snapshots: {len(identical)}")
    print(f"  {identical}")
    print(f"differing: {len(varying)}")
    spread = sorted(((max(all_snaps[j][2][i] for j in range(len(all_snaps)))
                      - min(all_snaps[j][2][i] for j in range(len(all_snaps)))), i)
                    for i in varying)
    print("widest spread (range, index):")
    for rng, i in spread[-15:]:
        print(f"  d[{i:3}]: range {rng:.3f}")


if __name__ == "__main__":
    main()
