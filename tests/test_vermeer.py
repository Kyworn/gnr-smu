#!/usr/bin/env python3
"""Ryzen 5 5600X / Vermeer (0x380905, 1488 B) profile tests.

Detection and safety are tested against fake sysfs files; per-core mapping
and telemetry semantics are tested against the 15 real snapshots in
tests/fixtures/vermeer/ (captured on the physical 5600X, 2026-09-10).
"""
import os
import statistics
import struct
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from gnr_smu import hardware as hwgate  # noqa: E402
from gnr_smu import safety  # noqa: E402
from gnr_smu.hardware import get_hardware_profile  # noqa: E402
from gnr_smu.profiles import (GLOBAL_FIELD_NAMES, PROFILES,  # noqa: E402
                              validate_profile_globals)
from gnr_smu.safety import (curve_optimizer_command,  # noqa: E402
                            read_curve_optimizer_offsets,
                            smu_message_supported, smu_writes_supported)

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "vermeer")
VERMEER = PROFILES[(0x380905, 1488, 6)]

# Linux core -> SMU slot, established by the per-core captures ( hottest
# temperature lane per pinned load; see docs/architectures/vermeer/VERMEER_5600X.md ).
EXPECTED_SLOTS = (0, 1, 4, 5, 6, 7)


def load_fixture(name):
    with open(os.path.join(FIX, name), "rb") as f:
        data = f.read()
    assert len(data) == 1488, name
    return struct.unpack("<372f", data)


def median(names, idx):
    return statistics.median(load_fixture(n)[idx] for n in names)


def fake_cpuinfo(tmp, model="AMD Ryzen 5 5600X 6-Core Processor"):
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


class TestVermeerDetection(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ver_path = os.path.join(self.tmp.name, "pm_table_version")
        self.size_path = os.path.join(self.tmp.name, "pm_table_size")
        self.pm_path = os.path.join(self.tmp.name, "pm_table")
        with open(self.ver_path, "wb") as f:
            f.write(struct.pack("<I", 0x380905))
        with open(self.size_path, "wb") as f:
            f.write(struct.pack("<Q", 1488))
        with open(os.path.join(FIX, "idle_01.bin"), "rb") as src, \
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

    def test_selects_vermeer_profile(self):
        profile, why = get_hardware_profile()
        self.assertIs(profile, VERMEER)
        self.assertIn("5600X", why)
        self.assertEqual(profile.float_count, 372)
        self.assertEqual(profile.cores, 6)

    def test_wrong_model_name_refuses(self):
        cpuinfo = fake_cpuinfo(self.tmp.name, model="AMD Ryzen 7 9800X3D")
        hwgate._cpu_model = lambda cpuinfo=cpuinfo: self.old_model(cpuinfo)
        hwgate._cached = None
        profile, _ = get_hardware_profile()
        self.assertIsNone(profile)

    def test_smu_writes_blocked(self):
        ok, _ = smu_writes_supported()
        self.assertFalse(ok)

    def test_no_message_id_allowlisted(self):
        # 0x00/None-ish fields, the three Vermeer RSMU power IDs from
        # external docs, both GNR CO styles, the CO readback and an
        # out-of-range ID: nothing may form an implicit allowlist.
        for msg in (0x00, 0x35, 0x3C, 0x3D, 0x3E, 0x50, 0x53, 0x54, 0x55,
                    0xD5, 0x04, 0xFFFFFFFF):
            self.assertFalse(smu_message_supported(VERMEER, msg),
                             f"0x{msg:02x}")

    def test_co_write_unconstructible(self):
        with self.assertRaises(ValueError):
            curve_optimizer_command(VERMEER, 0, -30)

    def test_rsmu_readback_refuses(self):
        with mock.patch.object(safety, "get_hardware_profile",
                               return_value=(VERMEER, "matched")):
            with self.assertRaises(RuntimeError):
                read_curve_optimizer_offsets(VERMEER)

    def test_global_map_is_exactly_the_validated_set(self):
        expected = {"fclk": 48, "uclk": 50, "mclk": 51, "vsoc": 45,
                    "vddp": 137, "vddg_iod": 138, "vddg_ccd": 139,
                    "socket_power": 1}
        self.assertEqual(dict(VERMEER.globals_map), expected)
        # Deliberately absent: Tctl (no sample-level coherence), power
        # limits, FCLK-adjacent unknowns.
        for name in ("tctl", "ppt_limit", "ppt_value", "tdc_limit",
                     "tdc_value", "thm_limit", "edc_limit", "vid",
                     "vdd_misc", "pkg_power", "cpu_power"):
            self.assertIsNone(VERMEER.gidx(name), name)

    def test_global_confidence_levels(self):
        for name in ("fclk", "uclk", "mclk", "vsoc", "vddp",
                     "vddg_iod", "vddg_ccd"):
            self.assertEqual(VERMEER.confidence(name), "high", name)
        self.assertEqual(VERMEER.confidence("socket_power"), "confirmed")
        self.assertIsNone(VERMEER.confidence("tctl"))
        self.assertIsNone(VERMEER.confidence("vid"))


class TestCoreTemperatureValidator(unittest.TestCase):
    def test_physical_core_discovery_uses_pathlib(self):
        from validate_core_temps import physical_core_cpus

        with tempfile.TemporaryDirectory() as tmp:
            cpu = os.path.join(tmp, "cpu7")
            topology = os.path.join(cpu, "topology")
            os.makedirs(topology)
            with open(os.path.join(topology, "physical_package_id"), "w") as f:
                f.write("0\n")
            with open(os.path.join(topology, "core_id"), "w") as f:
                f.write("3\n")
            with mock.patch("validate_core_temps.glob.glob", return_value=[cpu]):
                self.assertEqual(physical_core_cpus(), [7])


class TestCurveOptimizerLiveProfileGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.args_path = os.path.join(self.tmp.name, "smu_args")
        self.cmd_path = os.path.join(self.tmp.name, "rsmu_cmd")
        with open(self.args_path, "wb") as f:
            f.write(b"A" * 24)
        with open(self.cmd_path, "wb") as f:
            f.write(b"C" * 4)
        self.before = self._tree_contents()

    def _tree_contents(self):
        contents = {}
        for root, _, names in os.walk(self.tmp.name):
            for name in names:
                path = os.path.join(root, name)
                with open(path, "rb") as f:
                    contents[os.path.relpath(path, self.tmp.name)] = f.read()
        return contents

    def assert_zero_writes(self):
        self.assertEqual(self._tree_contents(), self.before)

    def assert_refused_without_writes(self, supplied, live_result, message):
        with mock.patch.object(safety, "get_hardware_profile",
                               return_value=live_result), \
                mock.patch.object(
                    safety, "_read_curve_optimizer_offsets") as transaction:
            with self.assertRaisesRegex(RuntimeError, message):
                read_curve_optimizer_offsets(supplied, self.tmp.name)
        transaction.assert_not_called()
        self.assert_zero_writes()

    def test_matching_live_profiles_can_proceed(self):
        for key in ((0x620105, 1828, 8), (0x620205, 2452, 16)):
            profile = PROFILES[key]
            expected = [-30] * profile.cores
            with self.subTest(profile=profile.name), \
                    mock.patch.object(safety, "get_hardware_profile",
                                      return_value=(profile, "matched")), \
                    mock.patch.object(safety, "_read_curve_optimizer_offsets",
                                      return_value=expected) as transaction:
                self.assertEqual(
                    read_curve_optimizer_offsets(profile, self.tmp.name), expected)
                transaction.assert_called_once_with(profile, self.tmp.name)

    def test_mismatched_profile_performs_zero_writes(self):
        supplied = PROFILES[(0x620105, 1828, 8)]
        live = PROFILES[(0x620205, 2452, 16)]
        self.assert_refused_without_writes(
            supplied, (live, "matched"), "profile mismatch")

    def test_unsupported_hardware_performs_zero_writes(self):
        supplied = PROFILES[(0x620105, 1828, 8)]
        self.assert_refused_without_writes(
            supplied, (None, "unsupported test hardware"),
            "unsupported test hardware")

    def test_vermeer_performs_zero_writes(self):
        self.assert_refused_without_writes(
            VERMEER, (VERMEER, "matched"), "not validated")


class TestVermeerSlots(unittest.TestCase):
    def test_slot_table(self):
        self.assertEqual(
            [VERMEER.slot(c) for c in range(6)], list(EXPECTED_SLOTS))

    def test_slot_range_checked(self):
        with self.assertRaises(ValueError):
            VERMEER.slot(6)
        with self.assertRaises(ValueError):
            VERMEER.slot(-1)

    def test_core2_avoids_fused_lane(self):
        self.assertEqual(VERMEER.lane(188, 2), 192)
        self.assertEqual(VERMEER.lane_values(list(range(500)), 172),
                         [172, 173, 176, 177, 178, 179])

    def test_hottest_temp_lane_matches_slot(self):
        idle = ["idle_01.bin", "idle_02.bin", "idle_03.bin"]
        for core, slot in enumerate(EXPECTED_SLOTS):
            base = [median(idle, 188 + s) for s in range(8)]
            hot = load_fixture(f"core{core}_load.bin")
            delta = [hot[188 + s] - base[s] for s in range(8)]
            self.assertEqual(max(range(8), key=delta.__getitem__), slot,
                             f"linux core {core}")

    def test_temp_block_only_slots_live_selectively(self):
        # Slots 2-3 (d[190]/d[191]) move with load but follow no single core.
        idle = ["idle_01.bin", "idle_02.bin", "idle_03.bin"]
        for slot in (2, 3):
            idx = 188 + slot
            per_core = [load_fixture(f"core{c}_load.bin")[idx]
                        - median(idle, idx) for c in range(6)]
            self.assertLess(max(per_core), 12.0,
                            f"slot {slot} must not be core-selective")

    def test_residency_semantics(self):
        all_names = ["all_core_01.bin", "all_core_02.bin",
                     "all_core_03.bin"]
        for core, slot in enumerate(EXPECTED_SLOTS):
            c0 = median(all_names, 228 + slot)
            cc1 = median(all_names, 236 + slot)
            cc6 = median(all_names, 244 + slot)
            self.assertGreater(c0, 95.0, f"core {core} C0 under full load")
            self.assertLess(cc1, 5.0, f"core {core} CC1 under full load")
            self.assertLess(cc6, 5.0, f"core {core} CC6 under full load")

    def test_cc6_fused_slots_read_full(self):
        # Fused-off slots report CC6=100.0.  This is the firmware
        # representation for inactive/non-present core slots, not an actual
        # sleeping physical core.
        for name in ("idle_01.bin", "all_core_01.bin"):
            row = load_fixture(name)
            self.assertAlmostEqual(row[246], 100.0, places=3)
            self.assertAlmostEqual(row[247], 100.0, places=3)

    def test_freq_and_eff_freq_ranges(self):
        all_names = ["all_core_01.bin", "all_core_02.bin",
                     "all_core_03.bin"]
        for core, slot in enumerate(EXPECTED_SLOTS):
            freq = median(all_names, 212 + slot)
            eff = median(all_names, 220 + slot)
            self.assertGreater(freq, 3.0)
            self.assertLess(freq, 5.0)
            self.assertGreater(eff, 3.0)
            self.assertLess(eff, 5.0)

    def test_voltage_range(self):
        all_names = ["all_core_01.bin", "all_core_02.bin",
                     "all_core_03.bin"]
        for core, slot in enumerate(EXPECTED_SLOTS):
            v = median(all_names, 180 + slot)
            self.assertGreater(v, 0.8)
            self.assertLess(v, 1.5)


class TestPhase2Globals(unittest.TestCase):
    """Phase 2: clocks/rails/package-power in the 15 fixtures."""

    def test_clocks_bit_constant(self):
        for name in ("idle_01.bin", "single_core_02.bin", "all_core_03.bin",
                     "core4_load.bin"):
            row = load_fixture(name)
            self.assertEqual(row[48], 1800.0, name)
            self.assertEqual(row[50], 1600.0, name)
            self.assertEqual(row[51], 1600.0, name)

    def test_rails_bit_constant(self):
        for name in ("idle_01.bin", "all_core_01.bin", "core0_load.bin"):
            row = load_fixture(name)
            self.assertEqual(row[45], 1.1875, name)
            self.assertAlmostEqual(row[137], 0.9002, places=3, msg=name)
            self.assertAlmostEqual(row[138], 0.9976, places=3, msg=name)
            self.assertAlmostEqual(row[139], 0.9976, places=3, msg=name)

    def test_socket_power_range_and_load_response(self):
        idle = median(["idle_01.bin", "idle_02.bin", "idle_03.bin"], 1)
        single = median(["single_core_01.bin", "single_core_02.bin",
                         "single_core_03.bin"], 1)
        full = median(["all_core_01.bin", "all_core_02.bin",
                       "all_core_03.bin"], 1)
        self.assertGreater(idle, 15.0)
        self.assertLess(idle, 35.0)
        self.assertGreater(single, idle + 3.0)
        self.assertGreater(full, 60.0)
        self.assertLess(full, 100.0)

    def test_socket_mirrors_identical(self):
        # d[13]/d[29] track d[1] to ~1e-3 (same reading, float32 noise);
        # only d[1] is mapped.
        for name in ("idle_01.bin", "all_core_02.bin", "core3_load.bin"):
            row = load_fixture(name)
            self.assertAlmostEqual(row[13], row[1], places=2, msg=name)
            self.assertAlmostEqual(row[29], row[1], places=2, msg=name)


class TestVermeerExporterFields(unittest.TestCase):
    def test_named_fields_use_slots(self):
        from export_telemetry import named_fields
        fields = named_fields(VERMEER)
        by_name = {name: idx for name, idx, _ in fields}
        self.assertEqual(by_name["c2_temp"], 192)
        self.assertEqual(by_name["c0_temp"], 188)
        self.assertEqual(by_name["c5_temp"], 195)
        self.assertEqual(by_name["c2_freq_eff"], 224)
        # Phase 2 globals with exact indices.
        for name, idx in (("fclk", 48), ("uclk", 50), ("mclk", 51),
                          ("socket_power", 1), ("vddcr_soc", 45),
                          ("cldo_vddg_iod", 138), ("cldo_vddg_ccd", 139),
                          ("cldo_vddp", 137)):
            self.assertEqual(by_name[name], idx, name)
        # Still absent: Tctl, limits, unmapped rails.
        for name in ("ppt_limit", "tctl", "vdd_misc", "vid_live"):
            self.assertNotIn(name, by_name)
        # No boost column without a validated boost block.
        self.assertFalse(any("boost" in n for n in by_name))


class TestFusedLayoutGuard(unittest.TestCase):
    """The slot tuple is one machine's layout until the live table says so."""

    def _write_pm(self, mutate=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        row = list(load_fixture("idle_01.bin"))
        if mutate:
            mutate(row)
        path = os.path.join(tmp.name, "pm_table")
        with open(path, "wb") as f:
            f.write(struct.pack("<372f", *row))
        return path

    def test_valid_layout_passes(self):
        from gnr_smu.hardware import _fused_layout_matches
        ok, _ = _fused_layout_matches(VERMEER, self._write_pm())
        self.assertTrue(ok)

    def test_live_fused_slot_refuses(self):
        # Another chip with slots 2-3 actually present must not be
        # mislabelled: a nonzero fused lane refuses the profile.
        from gnr_smu.hardware import _fused_layout_matches
        ok, why = _fused_layout_matches(
            VERMEER, self._write_pm(lambda r: r.__setitem__(214, 3.7)))
        self.assertFalse(ok)
        self.assertIn("differs from the validated machine", why)

    def test_dead_mapped_lane_refuses(self):
        # ... and a mapped lane reading 0.0 refuses too (fail closed both
        # ways), e.g. a dual-CCD SKU exposing a different CCD.
        from gnr_smu.hardware import _fused_layout_matches
        ok, why = _fused_layout_matches(
            VERMEER, self._write_pm(lambda r: r.__setitem__(212, 0.0)))
        self.assertFalse(ok)
        self.assertIn("differs from the validated machine", why)

    def test_other_blocks_checked_too(self):
        # The signature spans power/voltage/frequency: corrupting a fused
        # lane in any of them refuses, even with the frequency block intact.
        from gnr_smu.hardware import _fused_layout_matches
        for base in (172, 180):
            ok, _ = _fused_layout_matches(
                VERMEER, self._write_pm(lambda r, b=base: r.__setitem__(b + 2,
                                                                       1.0)))
            self.assertFalse(ok, f"base d[{base}]")

    def test_detection_refuses_foreign_layout(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ver_path = os.path.join(tmp.name, "pm_table_version")
        size_path = os.path.join(tmp.name, "pm_table_size")
        with open(ver_path, "wb") as f:
            f.write(struct.pack("<I", 0x380905))
        with open(size_path, "wb") as f:
            f.write(struct.pack("<Q", 1488))
        pm_path = self._write_pm(lambda r: r.__setitem__(214, 3.7))
        cpuinfo = fake_cpuinfo(tmp.name)
        old = (hwgate.VERSION_PATH, hwgate.SIZE_PATH, hwgate.PM_TABLE_PATH,
               hwgate._core_count, hwgate._cpu_model)
        hwgate.VERSION_PATH, hwgate.SIZE_PATH = ver_path, size_path
        hwgate.PM_TABLE_PATH = pm_path
        hwgate._core_count = lambda cpuinfo=cpuinfo: old[3](cpuinfo)
        hwgate._cpu_model = lambda cpuinfo=cpuinfo: old[4](cpuinfo)
        hwgate._cached = None
        try:
            profile, why = get_hardware_profile()
        finally:
            (hwgate.VERSION_PATH, hwgate.SIZE_PATH, hwgate.PM_TABLE_PATH,
             hwgate._core_count, hwgate._cpu_model) = old
            hwgate._cached = None
        self.assertIsNone(profile)
        self.assertIn("differs from the validated machine", why)


class TestCcdAverages(unittest.TestCase):
    """Every CCD aggregate must come from lane_values(), never base + core."""

    BLOCKS = (172, 180, 188, 212, 220, 228, 236, 244)

    def test_lane_indices_exclude_fused_slots(self):
        row = load_fixture("all_core_01.bin")
        for base in self.BLOCKS:
            used = set()
            for core in range(VERMEER.cores):
                idx = VERMEER.lane(base, core)
                used.add(idx)
                self.assertNotIn(idx - base, (2, 3),
                                 f"d[{base}] lane of core {core}")
            self.assertEqual(
                used, {base + s for s in EXPECTED_SLOTS}, f"d[{base}]")
            # The naive contiguous range would swallow the fused lanes.
            naive = set(range(base, base + VERMEER.cores))
            self.assertIn(base + 2, naive)
            self.assertNotIn(base + 2, used)

    def test_ccd_mean_uses_active_lanes_only(self):
        # Mirrors the GUI CCD summary: mean over Linux cores via lane().
        row = load_fixture("all_core_01.bin")
        temps = VERMEER.lane_values(row, VERMEER.core_temp)
        self.assertEqual(len(temps), 6)
        self.assertAlmostEqual(sum(temps) / 6, statistics.mean(
            row[188 + s] for s in EXPECTED_SLOTS))
        powers = VERMEER.lane_values(row, VERMEER.core_power)
        self.assertTrue(all(p > 5.0 for p in powers),
                        "all-core load: every active lane must show power")


class TestGlobalNames(unittest.TestCase):
    def test_all_profile_maps_are_canonical(self):
        for key, profile in PROFILES.items():
            self.assertEqual(validate_profile_globals(profile), [],
                             profile.name)

    def test_exporter_keys_are_canonical(self):
        from export_telemetry import COMMON_FIELDS
        from export_telemetry import _EXTRA_9800X3D, _EXTRA_9950X3D
        for column, key, _ in (list(COMMON_FIELDS) + _EXTRA_9800X3D +
                               _EXTRA_9950X3D):
            if key is not None:
                self.assertIn(key, GLOBAL_FIELD_NAMES, column)

    def test_gui_requests_are_canonical(self):
        import ast
        gui = os.path.join(os.path.dirname(__file__), "..", "gnr_smu",
                           "gui", "gnr_master.py")
        with open(gui) as f:
            tree = ast.parse(f.read())
        requested = set()
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "_g"
                    and node.args
                    and isinstance(node.args[-1], ast.Constant)):
                requested.add(node.args[-1].value)
        self.assertTrue(requested, "expected _g() call sites in the GUI")
        for name in requested:
            self.assertIn(name, GLOBAL_FIELD_NAMES, name)

    def test_confidence_levels(self):
        self.assertEqual(VERMEER.confidence("core_power"), "high")
        self.assertEqual(VERMEER.confidence("core_voltage"), "high")
        self.assertEqual(VERMEER.confidence("core_temp"), "confirmed")
        self.assertEqual(VERMEER.confidence("core_c0"), "confirmed")
        self.assertEqual(
            PROFILES[(0x620105, 1828, 8)].confidence("core_power"), "high")
        self.assertEqual(
            PROFILES[(0x620205, 2452, 16)].confidence("core_power"),
            "confirmed")


class TestLivePowerIndex(unittest.TestCase):
    def test_resolves_per_profile(self):
        from export_telemetry import live_power_index
        # Granite Ridge: ppt_value.
        self.assertEqual(
            live_power_index(PROFILES[(0x620105, 1828, 8)]), 3)
        self.assertEqual(
            live_power_index(PROFILES[(0x620205, 2452, 16)]), 3)
        # Vermeer: no ppt_value, falls back to the RAPL-validated socket
        # power instead of printing NaN.
        self.assertEqual(live_power_index(VERMEER), 1)

    def test_none_when_nothing_mapped(self):
        from export_telemetry import live_power_index

        class NoPower:
            def gidx(self, name):
                return None

        self.assertIsNone(live_power_index(NoPower()))

    def test_index_zero_is_valid(self):
        # Regression guard for `or`-style resolution: index 0 must survive.
        from export_telemetry import live_power_index

        class ZeroSocket:
            def gidx(self, name):
                return {"ppt_value": None, "socket_power": 0}[name]

        self.assertEqual(live_power_index(ZeroSocket()), 0)


if __name__ == "__main__":
    unittest.main()
