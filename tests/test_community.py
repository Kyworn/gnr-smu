#!/usr/bin/env python3
"""Community dump tooling tests: slot detection, bundle comparison.

Uses real Vermeer fixtures plus synthetic foreign-layout bundles built in
tmp (a contiguous 0-5 layout, as a differently-binned chip might report).
No hardware, no sysfs writes, no SMU access.
"""
import json
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "research"))

from hwgate import PROFILES, detect_active_slots  # noqa: E402

import compare_tables  # noqa: E402

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "vermeer")
VERMEER = PROFILES[(0x380905, 1488, 6)]
BASES = (VERMEER.core_power, VERMEER.core_voltage, VERMEER.core_frequency)


def load_fixture(name):
    with open(os.path.join(FIX, name), "rb") as f:
        data = f.read()
    assert len(data) == 1488, name
    return struct.unpack("<372f", data)


def make_bundle(tmp, name, mutate=None, model="AMD Ryzen 5 5600X 6-Core Processor"):
    d = os.path.join(tmp, name)
    os.makedirs(d)
    row = list(load_fixture("all_core_01.bin"))
    if mutate:
        mutate(row)
    with open(os.path.join(d, "snap.bin"), "wb") as f:
        f.write(struct.pack("<372f", *row))
    meta = {"cpu_model": model, "threads": 12, "physical_cores": 6,
            "topology_logical_to_core_id": {str(i): i % 6 for i in range(12)},
            "kernel_release": "test", "ryzen_smu_drv_version": "0.1.7",
            "smu_fw_version": "56.70.0", "mp1_if_version": "2",
            "codename_raw": "12", "pm_table_version": "0x380905",
            "pm_table_size": 1488, "pm_floats": 372,
            "snapshots": ["snap.bin"]}
    with open(os.path.join(d, "meta.json"), "w") as f:
        json.dump(meta, f)
    return d


def contiguous_layout(row):
    for base in (172, 180, 188, 212, 220, 228, 236, 244):
        block = [row[base + s] for s in range(8)]
        new = [block[0], block[1], block[4], block[5], block[6], block[7],
               0.0, 0.0]
        for s in range(8):
            row[base + s] = new[s]


class TestDetectActiveSlots(unittest.TestCase):
    def test_real_fixtures(self):
        for name in ("idle_01.bin", "single_core_01.bin", "all_core_01.bin",
                     "core0_load.bin", "core5_load.bin"):
            self.assertEqual(
                detect_active_slots(load_fixture(name), BASES),
                (0, 1, 4, 5, 6, 7), name)

    def test_single_block_sufficient(self):
        row = load_fixture("idle_01.bin")
        for base in BASES:
            self.assertEqual(detect_active_slots(row, (base,)),
                             (0, 1, 4, 5, 6, 7), f"d[{base}]")

    def test_table_tuple_not_assumed(self):
        # The detector derives the set; it must not contain the answer.
        row = list(load_fixture("idle_01.bin"))
        contiguous_layout(row)
        self.assertEqual(detect_active_slots(tuple(row), BASES),
                         (0, 1, 2, 3, 4, 5))

    def test_empty_bases_empty_result(self):
        self.assertEqual(detect_active_slots(load_fixture("idle_01.bin"), ()),
                         ())


class TestCompareTables(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.a = make_bundle(self.tmp.name, "machineA")
        self.foreign = make_bundle(self.tmp.name, "machineB",
                                   mutate=contiguous_layout)

    def test_same_layout_bundles(self):
        b = make_bundle(self.tmp.name, "machineA2")
        meta, snaps = compare_tables.load_bundle(b)
        layout = compare_tables.detect_bundle_layout(
            snaps, BASES)
        self.assertEqual(layout, (0, 1, 4, 5, 6, 7))

    def test_foreign_layout_detected(self):
        meta, snaps = compare_tables.load_bundle(self.foreign)
        layout = compare_tables.detect_bundle_layout(snaps, BASES)
        self.assertEqual(layout, (0, 1, 2, 3, 4, 5))
        self.assertNotEqual(set(layout), set(VERMEER.core_slots))

    def test_profile_bases_resolve(self):
        meta, _ = compare_tables.load_bundle(self.a)
        prof, bases = compare_tables.profile_bases(meta)
        self.assertIs(prof, VERMEER)
        self.assertEqual(bases, BASES)

    def test_unknown_table_needs_blocks(self):
        meta, _ = compare_tables.load_bundle(self.a)
        meta = dict(meta, pm_table_version="0xdead01")
        prof, bases = compare_tables.profile_bases(meta)
        self.assertIsNone(prof)
        self.assertIsNone(bases)

    def test_size_mismatch_rejected(self):
        d = os.path.join(self.tmp.name, "broken")
        os.makedirs(d)
        meta, _ = compare_tables.load_bundle(self.a)
        with open(os.path.join(d, "meta.json"), "w") as f:
            json.dump(meta, f)
        with open(os.path.join(d, "snap.bin"), "wb") as f:
            f.write(b"\x00" * 16)
        with self.assertRaises(ValueError):
            compare_tables.load_bundle(d)


class TestSubmitDump(unittest.TestCase):
    def test_topology_shape(self):
        # Read-only sysfs parse on this machine; structure only.
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                        "tools"))
        import submit_dump
        topo = submit_dump.topology()
        self.assertTrue(topo)
        for cpu, core in topo.items():
            self.assertIsInstance(cpu, int)
            self.assertIsInstance(core, int)
        self.assertEqual(submit_dump.physical_cores(topo),
                         len(set(topo.values())))


if __name__ == "__main__":
    unittest.main()
