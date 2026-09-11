#!/usr/bin/env python3
"""Research execution guards; all hardware and workloads are mocked."""

import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gnr_smu.profiles import PROFILES  # noqa: E402
from research.sysfs_discovery import (hwmon_inputs,
                                      powercap_energy)  # noqa: E402


P9800 = PROFILES[(0x620105, 1828, 8)]
P9950 = PROFILES[(0x620205, 2452, 16)]
VERMEER = PROFILES[(0x380905, 1488, 6)]

RESEARCH_MODULES = (
    "research/compare_tables.py",
    "research/dangerous/probe_tdc_edc.py",
    "research/dangerous/smu_advanced.py",
    "research/dangerous/smu_send.py",
    "research/granite_ridge/edc/hunt_edc.py",
    "research/granite_ridge/edc/profile_load.py",
    "research/granite_ridge/edc/recheck_edc.py",
    "research/granite_ridge/historical/profile_demoted.py",
    "research/granite_ridge/historical/transient_demoted.py",
    "research/granite_ridge/l3/l3_specificity.py",
    "research/granite_ridge/l3/l3_specificity_controlled.py",
    "research/granite_ridge/l3/recheck_l3.py",
    "research/granite_ridge/mapping/audit_map.py",
    "research/granite_ridge/mapping/classify_unknown.py",
    "research/granite_ridge/mapping/recheck_sweep.py",
    "research/granite_ridge/mapping/recheck_zone0.py",
    "research/vermeer/mapping/vermeer_380905.py",
    "research/vermeer/topology/vermeer_fuse_check.py",
    "research/vermeer/transient/vermeer_track.py",
    "research/vermeer/transient/vermeer_transient.py",
)


def load_module(relative_path):
    path = ROOT / relative_path
    name = "test_research_" + "_".join(path.with_suffix("").parts[-4:])
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_hwmon(root, number, name, labels):
    device = Path(root) / f"hwmon{number}"
    device.mkdir()
    (device / "name").write_text(name)
    for channel, (label, value) in labels.items():
        (device / f"{channel}_label").write_text(label)
        (device / f"{channel}_input").write_text(str(value))
    return device


class TestResearchImportSafety(unittest.TestCase):
    def test_imports_do_not_execute_experiments(self):
        for relative_path in RESEARCH_MODULES:
            with self.subTest(module=relative_path):
                output = io.StringIO()
                with mock.patch.object(
                        subprocess, "Popen",
                        side_effect=AssertionError("workload launched at import")), \
                     mock.patch.object(
                         time, "sleep",
                         side_effect=AssertionError("measurement slept at import")), \
                     contextlib.redirect_stdout(output), \
                     contextlib.redirect_stderr(output):
                    load_module(relative_path)
                self.assertEqual(output.getvalue(), "")


class TestExactResearchProfiles(unittest.TestCase):
    def test_9800_audit_refuses_9950_before_sensors_or_workload(self):
        module = load_module("research/granite_ridge/mapping/audit_map.py")
        with mock.patch.object(module, "get_hardware_profile",
                               return_value=(P9950, "9950X3D")), \
             mock.patch.object(module, "hwmon_inputs") as sensors, \
             mock.patch.object(module.subprocess, "Popen") as popen:
            with self.assertRaises(SystemExit):
                module.main()
        sensors.assert_not_called()
        popen.assert_not_called()

    def test_9800_audit_refuses_missing_required_sensor_before_workload(self):
        module = load_module("research/granite_ridge/mapping/audit_map.py")
        with mock.patch.object(module, "get_hardware_profile",
                               return_value=(P9800, "9800X3D")), \
             mock.patch.object(
                 module, "hwmon_inputs",
                 side_effect=({"tctl": Path("/fake/tctl")},
                              RuntimeError("amdgpu missing"))), \
             mock.patch.object(module.subprocess, "Popen") as popen:
            with self.assertRaisesRegex(RuntimeError, "amdgpu missing"):
                module.main()
        popen.assert_not_called()

    def test_9950_l3_refuses_9800_before_topology_or_workload(self):
        module = load_module("research/granite_ridge/l3/l3_specificity.py")
        with mock.patch.object(module, "get_hardware_profile",
                               return_value=(P9800, "9800X3D")), \
             mock.patch.object(module, "physical_core_cpus") as topology, \
             mock.patch.object(module.subprocess, "Popen") as popen:
            with self.assertRaises(SystemExit):
                module.main()
        topology.assert_not_called()
        popen.assert_not_called()

    def test_vermeer_logger_refuses_granite_before_output_or_workload(self):
        module = load_module(
            "research/vermeer/transient/vermeer_transient.py")
        with mock.patch.object(module, "get_hardware_profile",
                               return_value=(P9800, "9800X3D")), \
             mock.patch.object(module, "hwmon_inputs") as sensors, \
             mock.patch.object(module.subprocess, "Popen") as popen, \
             mock.patch.object(sys, "argv", ["vermeer_transient.py", "--out", "/x"]), \
             mock.patch("builtins.open") as opened:
            with self.assertRaises(SystemExit):
                module.main()
        sensors.assert_not_called()
        popen.assert_not_called()
        opened.assert_not_called()


class TestSysfsDiscovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_named_device_and_label_ignore_old_number(self):
        make_hwmon(self.root, 3, "acpitz", {"temp1": ("Tctl", 99999)})
        expected = make_hwmon(
            self.root, 19, "k10temp",
            {"temp7": ("Tctl", 42000), "temp8": ("Tccd1", 41000)})
        found = hwmon_inputs("k10temp", {
            "tctl": ("temp", "Tctl"),
            "tccd1": ("temp", "Tccd1"),
        }, root=self.root)
        self.assertEqual(found, {
            "tctl": expected / "temp7_input",
            "tccd1": expected / "temp8_input",
        })

    def test_missing_device_fails_closed(self):
        make_hwmon(self.root, 3, "acpitz", {})
        with self.assertRaisesRegex(RuntimeError, "found 0"):
            hwmon_inputs("k10temp", {"tctl": ("temp", "Tctl")},
                         root=self.root)

    def test_ambiguous_device_fails_closed(self):
        for number in (2, 9):
            make_hwmon(self.root, number, "k10temp",
                       {"temp1": ("Tctl", 42000)})
        with self.assertRaisesRegex(RuntimeError, "found 2"):
            hwmon_inputs("k10temp", {"tctl": ("temp", "Tctl")},
                         root=self.root)

    def test_ambiguous_label_fails_closed(self):
        make_hwmon(self.root, 8, "k10temp", {
            "temp1": ("Tctl", 42000),
            "temp7": ("Tctl", 42100),
        })
        with self.assertRaisesRegex(RuntimeError, "found 2"):
            hwmon_inputs("k10temp", {"tctl": ("temp", "Tctl")},
                         root=self.root)

    def test_powercap_domain_is_discovered_by_name(self):
        wrong = self.root / "intel-rapl:0"
        wrong.mkdir()
        (wrong / "name").write_text("dram")
        (wrong / "energy_uj").write_text("1")
        expected = self.root / "intel-rapl:9"
        expected.mkdir()
        (expected / "name").write_text("package-0")
        (expected / "energy_uj").write_text("123")
        self.assertEqual(powercap_energy("package-0", root=self.root),
                         expected / "energy_uj")


class TestDangerousProbeSafety(unittest.TestCase):
    def setUp(self):
        self.probe = load_module("research/dangerous/probe_tdc_edc.py")

    def test_wrong_profile_makes_zero_transactions(self):
        with mock.patch.object(self.probe, "get_hardware_profile",
                               return_value=(P9950, "9950X3D")), \
             mock.patch.object(self.probe, "smu_writes_supported") as writes, \
             mock.patch.object(self.probe, "_send_transaction") as transaction:
            with self.assertRaisesRegex(RuntimeError, "requires.*9800X3D"):
                self.probe.send(P9800.ppt_msg, P9800.stock_ppt * 1000)
        writes.assert_not_called()
        transaction.assert_not_called()

    def test_unsupported_hardware_makes_zero_transactions(self):
        with mock.patch.object(self.probe, "get_hardware_profile",
                               return_value=(None, "unsupported")), \
             mock.patch.object(self.probe, "smu_writes_supported") as writes, \
             mock.patch.object(self.probe, "_send_transaction") as transaction:
            with self.assertRaises(RuntimeError):
                self.probe.send(P9800.ppt_msg, P9800.stock_ppt * 1000)
        writes.assert_not_called()
        transaction.assert_not_called()

    def test_vermeer_makes_zero_transactions(self):
        with mock.patch.object(self.probe, "get_hardware_profile",
                               return_value=(VERMEER, "Vermeer")), \
             mock.patch.object(self.probe, "_send_transaction") as transaction:
            with self.assertRaises(RuntimeError):
                self.probe.send(P9800.ppt_msg, P9800.stock_ppt * 1000)
        transaction.assert_not_called()

    def test_rejected_message_makes_zero_transactions(self):
        with mock.patch.object(self.probe, "get_hardware_profile",
                               return_value=(P9800, "9800X3D")), \
             mock.patch.object(self.probe, "smu_writes_supported",
                               return_value=(True, "safe")), \
             mock.patch.object(self.probe, "_send_transaction") as transaction:
            with self.assertRaisesRegex(RuntimeError, "not allowlisted"):
                self.probe.send(0x01, 1)
        transaction.assert_not_called()

    def test_rejected_payload_makes_zero_transactions(self):
        with mock.patch.object(self.probe, "get_hardware_profile",
                               return_value=(P9800, "9800X3D")), \
             mock.patch.object(self.probe, "smu_writes_supported",
                               return_value=(True, "safe")), \
             mock.patch.object(self.probe, "_send_transaction") as transaction:
            with self.assertRaisesRegex(RuntimeError, "total throttle"):
                self.probe.send(P9800.ppt_msg, 0)
        transaction.assert_not_called()

    def test_valid_profile_reaches_only_intended_transaction(self):
        value = P9800.stock_ppt * 1000
        with mock.patch.object(self.probe, "get_hardware_profile",
                               return_value=(P9800, "9800X3D")), \
             mock.patch.object(self.probe, "smu_writes_supported",
                               return_value=(True, "safe")) as writes, \
             mock.patch.object(
                 self.probe, "smu_message_supported",
                 wraps=self.probe.smu_message_supported) as message, \
             mock.patch.object(
                 self.probe, "msg_id_blocked",
                 wraps=self.probe.msg_id_blocked) as blocked, \
             mock.patch.object(
                 self.probe, "payload_allowed",
                 wraps=self.probe.payload_allowed) as payload, \
             mock.patch.object(self.probe, "_send_transaction",
                               return_value=1) as transaction:
            result = self.probe.send(P9800.ppt_msg, value)
        self.assertEqual(result, 1)
        writes.assert_called_once_with()
        message.assert_called_once_with(P9800, P9800.ppt_msg)
        blocked.assert_called_once_with(P9800.ppt_msg, "mp1")
        payload.assert_called_once_with(P9800, P9800.ppt_msg, value)
        transaction.assert_called_once_with(P9800.ppt_msg, value)


class TestWorkloadCleanup(unittest.TestCase):
    def test_sampling_exception_terminates_worker(self):
        module = load_module("research/granite_ridge/edc/hunt_edc.py")
        worker = mock.Mock()
        worker.poll.return_value = None
        with mock.patch.object(module.subprocess, "Popen",
                               return_value=worker), \
             mock.patch.object(module.time, "sleep",
                               side_effect=RuntimeError("interrupted")):
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                module.run(["--cpu", "1"], 1, 1)
        worker.terminate.assert_called_once_with()
        worker.wait.assert_called_once_with()

    def test_partial_l3_worker_launch_is_reaped(self):
        module = load_module("research/granite_ridge/l3/recheck_l3.py")
        worker = mock.Mock()
        worker.poll.return_value = None
        with mock.patch.object(
                module.subprocess, "Popen",
                side_effect=(worker, RuntimeError("second worker failed"))):
            with self.assertRaisesRegex(RuntimeError, "second worker failed"):
                module.load_cpus([0, 1])
        worker.terminate.assert_called_once_with()
        worker.wait.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
