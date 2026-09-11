#!/usr/bin/env python3
"""Regression tests for the Granite Ridge profiles.

Guards the multi-generation refactor: the globals_map must reproduce the
exact offsets the tools used before, and SMU writes must stay allowed here.
"""
import os
import hashlib
import json
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gnr_smu.profiles import PROFILES  # noqa: E402
from gnr_smu.telemetry import global_fields, named_fields  # noqa: E402


class TestGraniteRidgeMaps(unittest.TestCase):
    def test_9800x3d_globals_follow_current_evidence(self):
        p = PROFILES[(0x620105, 1828, 8)]
        # CONFIRMED: limits/live values, clocks and independently validated
        # telemetry in 9800X3D_PM_TABLE_0x620105.md.
        confirmed = {
            "ppt_limit": 2, "ppt_value": 3,
            "tdc_limit": 8, "tdc_value": 9,
            "thm_limit": 10, "tctl": 11,
            "edc_limit": 63,
            "fclk": 71, "uclk": 75, "mclk": 79,
            "vcore_telemetry_peak": 18,
            "vcore_telemetry_average": 19,
            "pkg_power": 20,
            "hotspot_temp": 270,
            "igpu_power": 107, "igpu_clock": 108,
        }
        # HIGH: coherent identities supported by the map but without an
        # independent measurement strong enough for CONFIRMED.
        high = {
            "soc_power": 21,
            "vddio_mem_voltage": 58,
            "vsoc": 83,
            "vddcr_cpu_vid": 269,
        }
        expected = {
            **confirmed,
            **high,
        }
        self.assertEqual(dict(p.globals_map), expected)
        for name in confirmed:
            self.assertEqual(p.confidence(name), "confirmed", name)
        for name in high:
            self.assertEqual(p.confidence(name), "high", name)
        self.assertEqual(p.float_count, 457)

    def test_9800x3d_untrusted_names_are_not_exposed(self):
        p = PROFILES[(0x620105, 1828, 8)]
        removed = {
            "vid_limit", "vid", "vdd_misc", "vddg_iod", "vddg_ccd", "vddp",
            "socket_power", "cpu_power", "vddio_power", "vdd18_power",
            "soc_telemetry", "soc_telemetry_metric", "slow_temp_0",
            "slow_temp_1", "pkg_energy",
        }
        columns = {name for name, _, _ in named_fields(p)}
        for name in removed:
            self.assertIsNone(p.gidx(name), name)
            self.assertNotIn(name, columns, name)

    def test_9800x3d_exporter_allowlist(self):
        p = PROFILES[(0x620105, 1828, 8)]
        expected_globals = {
            "timestamp": (None, "s"),
            "ppt_limit": (2, "W"), "ppt_value": (3, "W"),
            "tdc_limit": (8, "A"), "tdc_value": (9, "A"),
            "thm_limit": (10, "C"), "tctl": (11, "C"),
            "edc_limit": (63, "A"),
            # These two are derived from the confirmed per-core voltage block.
            "vcore_peak": (None, "V"), "vcore_avg": (None, "V"),
            "fclk": (71, "MHz"), "uclk": (75, "MHz"),
            "mclk": (79, "MHz"),
            "vcore_telemetry_peak": (18, "V"),
            "vcore_telemetry_average": (19, "V"),
            "pkg_power": (20, "W"), "soc_power": (21, "W"),
            "vddio_mem_voltage": (58, "V"),
            "vddcr_cpu_vid": (269, "V"),
            "hotspot_temp": (270, "C"),
            "igpu_power": (107, "W"), "igpu_clock": (108, "MHz"),
        }
        self.assertEqual(
            {name: (idx, unit) for name, idx, unit in global_fields(p)},
            expected_globals,
        )
        self.assertEqual(len(named_fields(p)), 86)

    def test_9800x3d_schema_has_no_duplicates_or_alias_collisions(self):
        p = PROFILES[(0x620105, 1828, 8)]
        fields = named_fields(p)
        names = [name for name, _, _ in fields]
        self.assertEqual(len(names), len(set(names)))
        mapped_indices = [idx for _, idx, _ in fields if idx is not None]
        self.assertEqual(len(mapped_indices), len(set(mapped_indices)))

    def test_9800x3d_gui_uses_only_evidence_backed_globals(self):
        from gnr_smu.gui.gnr_master import (_POWER_SENSORS_9800X3D,
                                            _VOLTAGE_SENSORS_9800X3D)
        keys = {key for key, _ in
                (_POWER_SENSORS_9800X3D + _VOLTAGE_SENSORS_9800X3D)}
        expected = {
            "pkg_power", "core_power", "soc_power",
            "vcore_peak", "vcore_avg", "vcore_telemetry_peak",
            "vcore_telemetry_average", "vsoc", "vddio_mem_voltage",
            "vddcr_cpu_vid",
        }
        self.assertEqual(keys, expected)

    def test_9800x3d_high_blocks_are_not_reported_confirmed(self):
        p = PROFILES[(0x620105, 1828, 8)]
        for block in ("core_power", "core_cc6", "ccd_l3_temperature"):
            self.assertEqual(p.confidence(block), "high", block)
        for block in ("core_voltage", "core_temp", "core_frequency",
                      "core_c0", "core_cc1", "core_boost_limit"):
            self.assertEqual(p.confidence(block), "confirmed", block)

    def test_candidate_fields_never_report_confirmed(self):
        p9800 = PROFILES[(0x620105, 1828, 8)]
        p9950 = PROFILES[(0x620205, 2452, 16)]
        self.assertIsNone(p9800.confidence("ccd_power_candidate"))
        self.assertEqual(p9950.confidence("ccd_power_candidate"), "candidate")
        self.assertEqual(p9950.confidence("ccd_vddm_candidate"), "candidate")
        self.assertEqual(p9950.confidence("core_boost_limit"), "candidate")
        self.assertEqual(p9950.confidence("edc_value"), "candidate")

    def test_other_profile_exporter_schemas_are_unchanged(self):
        baselines = {
            (0x620205, 2452, 16): (
                170, "59e7018faa4d51d445b76eb91564a949a1e29d9e6db2fa9aff63d3caa207996f"),
            (0x380905, 1488, 6): (
                59, "39866c75f3c50c3647e8269bf3f1097d36ad4bbabac438cc5140fcc943be1318"),
        }
        for key, (count, expected_digest) in baselines.items():
            with self.subTest(profile=PROFILES[key].name):
                fields = named_fields(PROFILES[key])
                payload = json.dumps(fields, separators=(",", ":")).encode()
                self.assertEqual(len(fields), count)
                self.assertEqual(hashlib.sha256(payload).hexdigest(),
                                 expected_digest)

    def test_9950x3d_globals_reproduce_legacy_offsets(self):
        p = PROFILES[(0x620205, 2452, 16)]
        self.assertEqual(p.gidx("socket_power"), 26)
        self.assertEqual(p.gidx("ppt_limit"), 2)
        self.assertEqual(p.gidx("tctl"), 11)
        self.assertEqual(p.gidx("fit_metric"), 16)
        self.assertEqual(p.gidx("cpu_power"), 20)
        self.assertEqual(p.gidx("vddp"), 269)
        self.assertIsNone(p.gidx("hotspot_temp"))
        self.assertEqual(p.float_count, 613)

    def test_granite_ridge_slots_are_identity(self):
        for key in ((0x620105, 1828, 8), (0x620205, 2452, 16)):
            p = PROFILES[key]
            for core in range(p.cores):
                self.assertEqual(p.slot(core), core)
                self.assertEqual(p.lane(p.core_temp, core),
                                 p.core_temp + core)

    def test_granite_ridge_writes_still_allowed(self):
        from gnr_smu.safety import smu_message_supported
        for key in ((0x620105, 1828, 8), (0x620205, 2452, 16)):
            p = PROFILES[key]
            self.assertTrue(p.allow_smu_writes)
            self.assertTrue(smu_message_supported(p, p.ppt_msg))
            self.assertTrue(smu_message_supported(p, p.tdc_msg))
            self.assertTrue(smu_message_supported(p, p.edc_msg))


if __name__ == "__main__":
    unittest.main()
