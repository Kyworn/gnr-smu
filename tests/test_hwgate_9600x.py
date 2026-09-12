#!/usr/bin/env python3
"""Ryzen 5 9600X / Granite Ridge (0x620105, 1828 B, 6 cores) profile tests.

Detection is tested against fake sysfs files pointing at the two real
snapshots in tests/fixtures/granite_ridge/9600x/ (captured on the physical
9600X via tools/submit_dump.py, 2026-09-12: one idle, one --with-load
all-core). Unlike the 9800X3D/9950X3D, this profile has a non-identity
core_slots mapping (slots 4-5 fused off), so the fixtures exist specifically
to pin that layout against real bytes rather than a synthetic table.
"""
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gnr_smu import hardware as hwgate  # noqa: E402
from gnr_smu.hardware import detect_active_slots, get_hardware_profile  # noqa: E402
from gnr_smu.profiles import PROFILES  # noqa: E402

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "granite_ridge", "9600x")
P9600 = PROFILES[(0x620105, 1828, 6)]

# Linux core -> SMU slot, established by detect_active_slots() on the real
# dump's core-power/core-voltage blocks (see docs/architectures/granite_ridge/9600X.md).
EXPECTED_SLOTS = (0, 1, 2, 3, 6, 7)


def load_fixture(name):
    with open(os.path.join(FIX, name), "rb") as f:
        data = f.read()
    assert len(data) == 1828, name
    return struct.unpack("<457f", data)


def fake_cpuinfo(tmp, model="AMD Ryzen 5 9600X 6-Core Processor"):
    blocks = []
    for cpu in range(12):
        core = cpu % 6
        blocks.append(
            f"processor\t: {cpu}\nphysical id\t: 0\ncore id\t\t: {core}\n"
            f"model name\t: {model}\n")
    path = os.path.join(tmp, "cpuinfo")
    with open(path, "w") as f:
        f.write("\n".join(blocks) + "\n")
    return path


class Test9600XDetection(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ver_path = os.path.join(self.tmp.name, "pm_table_version")
        self.size_path = os.path.join(self.tmp.name, "pm_table_size")
        self.pm_path = os.path.join(self.tmp.name, "pm_table")
        with open(self.ver_path, "wb") as f:
            f.write(struct.pack("<I", 0x620105))
        with open(self.size_path, "wb") as f:
            f.write(struct.pack("<Q", 1828))
        with open(os.path.join(FIX, "pm_table_idle.bin"), "rb") as src, \
                open(self.pm_path, "wb") as dst:
            dst.write(src.read())
        self.old_ver, self.old_size = hwgate.VERSION_PATH, hwgate.SIZE_PATH
        self.old_pm = hwgate.PM_TABLE_PATH
        self.old_count, self.old_model = hwgate._core_count, hwgate._cpu_model
        hwgate.VERSION_PATH, hwgate.SIZE_PATH = self.ver_path, self.size_path
        hwgate.PM_TABLE_PATH = self.pm_path
        cpuinfo = fake_cpuinfo(self.tmp.name)
        hwgate._core_count = lambda cpuinfo=cpuinfo: self.old_count(cpuinfo)
        hwgate._cpu_model = lambda cpuinfo=cpuinfo: self.old_model(cpuinfo)
        hwgate._cached = None

    def tearDown(self):
        hwgate.VERSION_PATH, hwgate.SIZE_PATH = self.old_ver, self.old_size
        hwgate.PM_TABLE_PATH = self.old_pm
        hwgate._core_count, hwgate._cpu_model = self.old_count, self.old_model
        hwgate._cached = None
        self.tmp.cleanup()

    def test_selects_9600x_profile(self):
        profile, why = get_hardware_profile()
        self.assertIs(profile, P9600)
        self.assertIn("9600X", why)
        self.assertEqual(profile.float_count, 457)
        self.assertEqual(profile.cores, 6)

    def test_wrong_model_name_refuses(self):
        cpuinfo = fake_cpuinfo(self.tmp.name, model="AMD Ryzen 7 9800X3D")
        hwgate._cpu_model = lambda cpuinfo=cpuinfo: self.old_model(cpuinfo)
        hwgate._cached = None
        profile, _ = get_hardware_profile()
        self.assertIsNone(profile)


class Test9600XSlots(unittest.TestCase):
    def test_slot_table(self):
        self.assertEqual(
            [P9600.slot(c) for c in range(6)], list(EXPECTED_SLOTS))

    def test_slot_range_checked(self):
        with self.assertRaises(ValueError):
            P9600.slot(6)
        with self.assertRaises(ValueError):
            P9600.slot(-1)

    def test_fused_slots(self):
        self.assertEqual(P9600.fused_slots(), (4, 5))

    def test_detected_active_slots_match_both_snapshots(self):
        for name in ("pm_table_idle.bin", "pm_table_load.bin"):
            values = load_fixture(name)
            for base in (P9600.core_power, P9600.core_voltage):
                got = detect_active_slots(values, (base,))
                self.assertEqual(got, EXPECTED_SLOTS,
                                 f"{name} d[{base}]")

    def test_fused_slots_read_exactly_zero(self):
        # The zero-signature blocks must read exactly 0.0 on the fused
        # slots, not merely "small" -- that is the whole basis for
        # detect_active_slots() and _fused_layout_matches().
        for name in ("pm_table_idle.bin", "pm_table_load.bin"):
            values = load_fixture(name)
            for base in (P9600.core_power, P9600.core_voltage):
                for slot in P9600.fused_slots():
                    self.assertEqual(values[base + slot], 0.0,
                                     f"{name} d[{base + slot}]")

    def test_active_slots_are_nonzero_under_load(self):
        values = load_fixture("pm_table_load.bin")
        for slot in EXPECTED_SLOTS:
            self.assertGreater(values[P9600.core_power + slot], 0.0,
                               f"slot {slot} power under load")


class TestFusedLayoutGuardReal(unittest.TestCase):
    """Same guard as the 5600X's, exercised against the real 9600X bytes."""

    def test_real_idle_snapshot_passes(self):
        from gnr_smu.hardware import _fused_layout_matches
        ok, _ = _fused_layout_matches(
            P9600, os.path.join(FIX, "pm_table_idle.bin"))
        self.assertTrue(ok)

    def test_real_load_snapshot_passes(self):
        from gnr_smu.hardware import _fused_layout_matches
        ok, _ = _fused_layout_matches(
            P9600, os.path.join(FIX, "pm_table_load.bin"))
        self.assertTrue(ok)

    def test_live_fused_slot_refuses(self):
        # A hypothetical 9600X sample with slots 4-5 actually present must
        # not be mislabelled: a nonzero fused lane refuses the profile.
        from gnr_smu.hardware import _fused_layout_matches
        row = list(load_fixture("pm_table_idle.bin"))
        row[P9600.core_power + 4] = 3.7
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "pm_table")
        with open(path, "wb") as f:
            f.write(struct.pack("<457f", *row))
        ok, why = _fused_layout_matches(P9600, path)
        self.assertFalse(ok)
        self.assertIn("differs from the validated machine", why)


class Test9600XTelemetrySanity(unittest.TestCase):
    """Structural sanity on the real bytes; the independent k10temp/RAPL
    cross-checks that back the CONFIRMED/HIGH labels were done live and are
    recorded in docs/architectures/granite_ridge/9600X.md, not repeated here."""

    def test_tctl_in_plausible_range(self):
        for name in ("pm_table_idle.bin", "pm_table_load.bin"):
            tctl = load_fixture(name)[P9600.gidx("tctl")]
            self.assertGreater(tctl, 20.0, name)
            self.assertLess(tctl, 100.0, name)

    def test_ccd_l3_temperature_in_plausible_range(self):
        for name in ("pm_table_idle.bin", "pm_table_load.bin"):
            value = load_fixture(name)[P9600.ccd_l3_temperature]
            self.assertGreater(value, 20.0, name)
            self.assertLess(value, 100.0, name)

    def test_load_snapshot_is_hotter_or_equal(self):
        idle_tctl = load_fixture("pm_table_idle.bin")[P9600.gidx("tctl")]
        load_tctl = load_fixture("pm_table_load.bin")[P9600.gidx("tctl")]
        self.assertGreaterEqual(load_tctl, idle_tctl - 1.0)


if __name__ == "__main__":
    unittest.main()
