#!/usr/bin/env python3
"""Compare community PM-table bundles: layout vs layout, index vs index.

Usage:
  python3 tools/compare_tables.py bundleA bundleB [bundleC ...]
  python3 tools/compare_tables.py --block 172 --block 180 --block 212 bundleA bundleB

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
from pathlib import Path
import struct
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gnr_smu.hardware import detect_active_slots  # noqa: E402
from gnr_smu.profiles import PROFILES  # noqa: E402


class _Snapshot(tuple):
    """Float values plus their original bytes for exact bit comparisons."""

    def __new__(cls, values, raw):
        snapshot = super().__new__(cls, values)
        snapshot.raw = raw
        return snapshot


def _validate_metadata(meta, path):
    if not isinstance(meta, dict):
        raise ValueError(f"{path}/meta.json: expected a JSON object")
    required = {
        "pm_table_version": str,
        "pm_table_size": int,
        "physical_cores": int,
        "snapshots": list,
    }
    for name, expected_type in required.items():
        if name not in meta or type(meta[name]) is not expected_type:
            raise ValueError(
                f"{path}/meta.json: {name!r} must be {expected_type.__name__}")

    try:
        int(meta["pm_table_version"], 16)
    except ValueError as e:
        raise ValueError(
            f"{path}/meta.json: invalid pm_table_version") from e
    size = meta["pm_table_size"]
    if size <= 0 or size % 4:
        raise ValueError(
            f"{path}/meta.json: pm_table_size must be a positive multiple of 4")
    if meta["physical_cores"] <= 0:
        raise ValueError(f"{path}/meta.json: physical_cores must be positive")

    snapshots = meta["snapshots"]
    if not snapshots:
        raise ValueError(f"{path}/meta.json: at least one snapshot is required")
    if any(not isinstance(name, str) or not name for name in snapshots):
        raise ValueError(f"{path}/meta.json: snapshot names must be non-empty strings")
    if len(set(snapshots)) != len(snapshots):
        raise ValueError(f"{path}/meta.json: snapshot names must be unique")

    if "pm_floats" in meta and (
            type(meta["pm_floats"]) is not int or meta["pm_floats"] != size // 4):
        raise ValueError(f"{path}/meta.json: pm_floats does not match pm_table_size")
    if "threads" in meta and (
            type(meta["threads"]) is not int or meta["threads"] <= 0):
        raise ValueError(f"{path}/meta.json: threads must be a positive integer")
    if "cpu_model" in meta and not isinstance(meta["cpu_model"], str):
        raise ValueError(f"{path}/meta.json: cpu_model must be a string")


def load_bundle(path):
    root = Path(path).resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"{path}: bundle path is not a directory")
    with open(root / "meta.json") as f:
        meta = json.load(f)
    _validate_metadata(meta, path)
    snaps = {}
    for name in meta["snapshots"]:
        relative = Path(name)
        if relative.is_absolute():
            raise ValueError(f"{path}/meta.json: absolute snapshot path refused: {name}")
        if ".." in relative.parts:
            raise ValueError(f"{path}/meta.json: snapshot path escape refused: {name}")
        try:
            snapshot_path = (root / relative).resolve(strict=True)
        except OSError as e:
            raise ValueError(f"{path}/{name}: cannot resolve snapshot") from e
        try:
            snapshot_path.relative_to(root)
        except ValueError as e:
            raise ValueError(f"{path}/meta.json: snapshot leaves bundle: {name}") from e
        if not snapshot_path.is_file():
            raise ValueError(f"{path}/{name}: snapshot is not a regular file")
        with open(snapshot_path, "rb") as f:
            data = f.read()
        if len(data) != meta["pm_table_size"]:
            raise ValueError(f"{path}/{name}: size mismatch")
        n = meta["pm_table_size"] // 4
        snaps[name] = _Snapshot(struct.unpack(f"<{n}f", data), data)
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


def bit_identical_indices(snapshots):
    """Return indices with equal/different raw float32 encodings."""
    snapshots = list(snapshots)
    if not snapshots:
        raise ValueError("at least one snapshot is required")
    n = len(snapshots[0])
    if any(len(snapshot) != n or len(snapshot.raw) != n * 4
           for snapshot in snapshots):
        raise ValueError("snapshot sizes do not match")
    identical, varying = [], []
    for i in range(n):
        bits = [snapshot.raw[i * 4:(i + 1) * 4] for snapshot in snapshots]
        (identical if all(value == bits[0] for value in bits)
         else varying).append(i)
    return identical, varying


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
    identical, varying = bit_identical_indices(v for _, _, v in all_snaps)
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
