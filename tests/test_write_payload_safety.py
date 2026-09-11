#!/usr/bin/env python3
"""Adversarial payload checks. Every transaction and sysfs access is mocked."""

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gnr_smu.profiles import PROFILES  # noqa: E402
from gnr_smu.safety import (curve_optimizer_command,  # noqa: E402
                            curve_optimizer_read_command,
                            payload_allowed, smu_command_allowed)


P9800 = PROFILES[(0x620105, 1828, 8)]
P9950 = PROFILES[(0x620205, 2452, 16)]
VERMEER = PROFILES[(0x380905, 1488, 6)]


def load_module(relative_path):
    path = ROOT / relative_path
    name = "test_payload_" + "_".join(path.with_suffix("").parts[-4:])
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestPowerPayloadEnvelope(unittest.TestCase):
    ENVELOPES = {
        P9800: {"ppt": (151, 162), "tdc": (111, 120), "edc": (111, 180)},
        P9950: {"ppt": (200, 200), "tdc": (160, 160), "edc": (225, 225)},
    }

    def test_exact_boundaries_are_allowed(self):
        for profile, envelopes in self.ENVELOPES.items():
            for name, (minimum, maximum) in envelopes.items():
                msg_id = getattr(profile, f"{name}_msg")
                for value in {minimum * 1000, maximum * 1000}:
                    with self.subTest(profile=profile.name, limit=name, value=value):
                        self.assertEqual(payload_allowed(profile, msg_id, value),
                                         (True, None))
                        self.assertEqual(
                            smu_command_allowed(profile, "mp1", msg_id, value),
                            (True, None))

    def test_profile_envelopes_are_well_formed(self):
        for profile, envelopes in self.ENVELOPES.items():
            for name, expected in envelopes.items():
                bounds = getattr(profile, f"{name}_write_bounds")
                stock = getattr(profile, f"stock_{name}")
                frontend_max = getattr(profile, f"max_{name}")
                with self.subTest(profile=profile.name, limit=name):
                    self.assertEqual(bounds, expected)
                    self.assertTrue(all(type(value) is int and value > 0
                                        for value in bounds))
                    self.assertLessEqual(bounds[0], stock)
                    self.assertLessEqual(stock, bounds[1])
                    self.assertLessEqual(bounds[1], frontend_max)
        self.assertIsNone(VERMEER.ppt_write_bounds)
        self.assertIsNone(VERMEER.tdc_write_bounds)
        self.assertIsNone(VERMEER.edc_write_bounds)

    def test_invalid_power_payloads_are_rejected(self):
        for profile, envelopes in self.ENVELOPES.items():
            for name, (minimum, maximum) in envelopes.items():
                msg_id = getattr(profile, f"{name}_msg")
                invalid = (True, False, 0, -1, 1, minimum * 1000 - 1,
                           maximum * 1000 + 1, 1.0, "1000", None)
                for value in invalid:
                    with self.subTest(profile=profile.name, limit=name, value=value):
                        self.assertFalse(payload_allowed(profile, msg_id, value)[0])
                        self.assertFalse(
                            smu_command_allowed(profile, "mp1", msg_id, value)[0])

    def test_unsupported_profile_is_rejected(self):
        for msg_id in (P9800.ppt_msg, P9800.tdc_msg, P9800.edc_msg):
            self.assertFalse(
                smu_command_allowed(VERMEER, "mp1", msg_id, 151_000)[0])


class TestCurveOptimizerPayloadEnvelope(unittest.TestCase):
    def assert_canonical(self, profile, core, margin):
        msg_id, arg0 = curve_optimizer_command(profile, core, margin)
        self.assertEqual(payload_allowed(profile, msg_id, arg0), (True, None))
        self.assertEqual(
            smu_command_allowed(profile, "mp1", msg_id, arg0), (True, None))

    def test_valid_canonical_boundaries(self):
        for profile in (P9800, P9950):
            for core in (0, profile.cores - 1):
                for margin in (-50, 20):
                    with self.subTest(profile=profile.name, core=core, margin=margin):
                        self.assert_canonical(profile, core, margin)

    def test_9800_adversarial_payloads(self):
        invalid = (
            (0x50, 0x7FFFFFFF),
            (0x50, (-51) & 0xFFFFFFFF),
            (0x50, 21),
            (0x58, (-30) & 0xFFFFFFFF),
            (0x50, True),
        )
        for msg_id, arg0 in invalid:
            with self.subTest(msg=msg_id, arg=arg0):
                self.assertFalse(payload_allowed(P9800, msg_id, arg0)[0])
                self.assertFalse(
                    smu_command_allowed(P9800, "mp1", msg_id, arg0)[0])

    def test_9950_adversarial_payloads(self):
        canonical_msg = P9950.co_msg
        invalid = (
            (canonical_msg, 0xFFFFFFFF),
            (canonical_msg, (-51) & 0xFFFF),
            (canonical_msg, 21),
            (canonical_msg, 2 << 28 | ((-30) & 0xFFFF)),  # invalid CCD
            (canonical_msg, 8 << 20 | ((-30) & 0xFFFF)),  # invalid core in CCD
            (canonical_msg, 1 << 24 | ((-30) & 0xFFFF)),  # reserved bit
            (canonical_msg, 1 << 16 | ((-30) & 0xFFFF)),  # reserved bit
        )
        for msg_id, arg0 in invalid:
            with self.subTest(msg=msg_id, arg=arg0):
                self.assertFalse(payload_allowed(P9950, msg_id, arg0)[0])
                self.assertFalse(
                    smu_command_allowed(P9950, "mp1", msg_id, arg0)[0])

    def test_rsmu_query_payload_is_exact(self):
        for profile in (P9800, P9950):
            for core in (0, profile.cores - 1):
                msg_id, arg0 = curve_optimizer_read_command(profile, core)
                self.assertTrue(
                    smu_command_allowed(profile, "rsmu", msg_id, arg0)[0])
            self.assertFalse(
                smu_command_allowed(profile, "rsmu", profile.co_get_msg,
                                    0xFFFFFFFF)[0])
        self.assertTrue(smu_command_allowed(P9800, "rsmu", 0x04, 1)[0])
        self.assertTrue(smu_command_allowed(P9800, "rsmu", 0x05, 0)[0])
        self.assertFalse(smu_command_allowed(P9800, "rsmu", 0x04, 0)[0])
        self.assertFalse(smu_command_allowed(P9800, "rsmu", 0x05, 1)[0])


class TestRejectedCommandsMakeZeroTransactions(unittest.TestCase):
    def test_cli_rejects_before_sysfs_write(self):
        module = load_module("tools/gnr_master.py")
        rejected = (
            (P9800.ppt_msg, True),
            (P9800.ppt_msg, 0),
            (P9800.ppt_msg, -1),
            (P9800.ppt_msg, 1),
            (P9800.ppt_msg, 150_999),
            (P9800.ppt_msg, 162_001),
            (P9800.ppt_msg, 151_000.0),
            (P9800.ppt_msg, "151000"),
            (0x50, 0x7FFFFFFF),
        )
        for msg_id, arg0 in rejected:
            with self.subTest(msg=msg_id, arg=arg0), \
                 mock.patch.object(module, "smu_writes_supported",
                                   return_value=(True, "matched")), \
                 mock.patch.object(module, "get_hardware_profile",
                                   return_value=(P9800, "matched")), \
                 mock.patch("builtins.open") as opened:
                self.assertFalse(module.apply_cmd(msg_id, arg0))
                opened.assert_not_called()

    def test_cli_unsupported_profile_makes_zero_writes(self):
        module = load_module("tools/gnr_master.py")
        with mock.patch.object(module, "smu_writes_supported",
                               return_value=(False, "unsupported")), \
             mock.patch.object(module, "get_hardware_profile",
                               return_value=(VERMEER, "matched")), \
             mock.patch("builtins.open") as opened:
            self.assertFalse(module.apply_cmd(P9800.ppt_msg, 151_000))
        opened.assert_not_called()

    def test_gui_rejects_before_sysfs_write(self):
        module = load_module("gnr_smu/gui/gnr_master.py")
        window = SimpleNamespace(profile=P9950, log_msg=mock.Mock())
        with mock.patch.object(module, "smu_writes_supported",
                               return_value=(True, "matched")), \
             mock.patch("builtins.open") as opened:
            self.assertFalse(
                module.GNRMaster.send_smu_cmd(window, P9950.co_msg, 0xFFFFFFFF))
        opened.assert_not_called()

    def test_raw_research_tools_reject_before_smn(self):
        cases = (
            ("research/dangerous/smu_send.py", (0x50, 0x7FFFFFFF)),
            ("research/dangerous/smu_advanced.py", ("mp1", 0x50, 0x7FFFFFFF)),
        )
        for path, args in cases:
            module = load_module(path)
            with self.subTest(path=path), \
                 mock.patch.object(module, "get_hardware_profile",
                                   return_value=(P9800, "matched")), \
                 mock.patch.object(module, "smu_writes_supported",
                                   return_value=(True, "matched")), \
                 mock.patch.object(module, "smn_write") as transaction:
                with self.assertRaises(SystemExit):
                    module.smu_send(*args)
            transaction.assert_not_called()


if __name__ == "__main__":
    unittest.main()
