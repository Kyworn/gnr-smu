#!/usr/bin/env python3
"""Regression tests for the Granite Ridge profiles.

Guards the multi-generation refactor: the globals_map must reproduce the
exact offsets the tools used before, and SMU writes must stay allowed here.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gnr_smu.profiles import PROFILES  # noqa: E402


class TestGraniteRidgeMaps(unittest.TestCase):
    def test_9800x3d_globals_reproduce_legacy_offsets(self):
        p = PROFILES[(0x620105, 1828, 8)]
        # Every offset the GUI/exporter hardcoded before the map existed.
        expected = {
            "ppt_limit": 2, "ppt_value": 3,
            "tdc_limit": 8, "tdc_value": 9,
            "thm_limit": 10, "tctl": 11,
            "edc_limit": 63,
            "fclk": 71, "uclk": 75, "mclk": 79,
            "vid_limit": 18, "vid": 19,
            "vdd_misc": 58, "vsoc": 83,
            "vddg_iod": 259, "vddg_ccd": 261, "vddp": 269,
            "socket_power": 20, "cpu_power": 20, "pkg_power": 20,
            "soc_power": 21, "vddio_power": 22, "vdd18_power": 23,
            "hotspot_temp": 270,
            "soc_telemetry": 87, "soc_telemetry_metric": 95,
            "igpu_power": 107, "igpu_clock": 108,
            "slow_temp_0": 298, "slow_temp_1": 299,
            "pkg_energy": 212,
        }
        for name, idx in expected.items():
            self.assertEqual(p.gidx(name), idx, name)
        self.assertEqual(p.float_count, 457)

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
