#!/usr/bin/env python3
"""Analyse the Ryzen 5 5600X / Vermeer PM table dataset (0x380905, 1488 B).

Usage: python3 research/vermeer_380905.py /path/to/5600x_smu_dump

Read-only analysis of the 15 captured .bin snapshots. Prints:
  1. constant vs dynamic fields (idle variance, load deltas)
  2. candidate per-core blocks (172..252) with per-core selectivity scores
  3. zone 0x000 structure
Prints medians over the 3-sample groups to avoid confusing noise with signal.
"""
import glob
import os
import re
import statistics
import struct
import sys

DS = sys.argv[1] if len(sys.argv) > 1 else "/tmp/opencode/ds/5600x_smu_dump"


def load():
    bins = {}
    for f in sorted(glob.glob(os.path.join(DS, "*", "*.bin"))):
        data = open(f, "rb").read()
        assert len(data) == 1488, f
        key = os.path.relpath(f, DS)
        bins[key] = struct.unpack("<372f", data)
    return bins


def groups(bins):
    g = {"idle": [], "single": [], "all": [], "per_core": {}}
    for k, v in bins.items():
        if k.startswith("idle/"):
            g["idle"].append(v)
        elif k.startswith("single_core/"):
            g["single"].append(v)
        elif k.startswith("all_core/"):
            g["all"].append(v)
        elif k.startswith("per_core/"):
            m = re.search(r"core(\d)_load", os.path.basename(k))
            core = int(m.group(1))
            g["per_core"][core] = v
    return g


def med(vals):
    return statistics.median(vals)


def main():
    bins = load()
    g = groups(bins)
    print(f"snapshots: {len(bins)}")
    print("== 1. idle variance + load deltas (medians of 3) ==")
    print(f"{'i':>4} {'idle_med':>10} {'idle_rng':>9} "
          f"{'single':>10} {'all':>10} {'dS':>8} {'dA':>8}")
    for i in range(372):
        iv = [s[i] for s in g["idle"]]
        mi, ms, ma = med(iv), med(s[i] for s in g["single"]), med(s[i] for s in g["all"])
        rng = max(iv) - min(iv)
        flag = ""
        if abs(ma - mi) > max(3 * rng, 0.5) and abs(ma - mi) > 0.01 * max(1, abs(mi)):
            flag = "  <-- LOAD-RESPONSIVE"
        elif rng == 0 and ms == mi == ma:
            flag = "  [const]"
        print(f"{i:4d} {mi:10.3f} {rng:9.3f} {ms:10.3f} {ma:10.3f} "
              f"{ms - mi:+8.2f} {ma - mi:+8.2f}{flag}")

    print()
    print("== 2. per-core selectivity: per_core[c] - idle_med, blocks 168..256 ==")
    idle_med = [med([s[i] for s in g["idle"]]) for i in range(372)]
    print(f"{'i':>4} " + "".join(f"{'c'+str(c):>9}" for c in range(6)) + f"  {'all-idle':>9}")
    all_med = [med(s[i] for s in g["all"]) for i in range(372)]
    for i in range(168, 257):
        row = "".join(f"{g['per_core'][c][i] - idle_med[i]:+9.2f}" for c in range(6))
        print(f"{i:4d} {row}  {all_med[i] - idle_med[i]:+9.2f}")

    print()
    print("== 3. same, blocks 0..100 (globals/limits spot check) ==")
    for i in range(0, 100):
        row = "".join(f"{g['per_core'][c][i] - idle_med[i]:+9.2f}" for c in range(6))
        print(f"{i:4d} {row}  {all_med[i] - idle_med[i]:+9.2f}")


if __name__ == "__main__":
    main()
