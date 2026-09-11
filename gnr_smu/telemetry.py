#!/usr/bin/env python3
"""Telemetry field schema for GNR-SMU exporters.

Owns the named-column definitions (COMMON_FIELDS, per-part extras) and the
pure helpers that resolve them against a HardwareProfile (global_fields,
named_fields, floats_to_row, live_power_index). Every numeric offset comes
from the profile; an unmapped key is skipped, never filled from another
part's offset. Extracted verbatim from tools/export_telemetry.py; the
sysfs I/O and CLI remain there.
"""


# Key named fields: (column_name, globals_map key, unit).  A key missing
# from the profile's map is unsupported there and the column is omitted —
# the exporter must never fill a column from another part's offset.
COMMON_FIELDS = [
    ("timestamp",        None,  "s"),
    # Zone 0x000 is the Zen (LIMIT, VALUE) pair layout — corrected 2026-07-30.
    # d[8] is TDC (not EDC) and d[10] is the thermal limit in °C (not TDC in A).
    ("ppt_limit",        "ppt_limit", "W"),
    ("ppt_value",        "ppt_value", "W"),    # total package power, incl. SoC/uncore
    ("tdc_limit",        "tdc_limit", "A"),
    ("tdc_value",        "tdc_value", "A"),
    ("thm_limit",        "thm_limit", "C"),
    ("tctl",             "tctl",  "C"),    # direct °C, matches k10temp Tctl
    ("edc_limit",        "edc_limit", "A"),
    ("vcore_peak",       None,  "V"),   # computed from the profile's core-voltage block
    ("vcore_avg",        None,  "V"),
    ("fclk",             "fclk",  "MHz"),
    ("uclk",             "uclk",  "MHz"),
    ("mclk",             "mclk",  "MHz"),
]

# Version-specific extras.  Only the (column, key, unit) presentation lives
# here; every numeric offset lives on the HardwareProfile so an unmapped key
# is skipped instead of read from the wrong place.
_EXTRA_9950X3D = [
    ("fit_metric", "fit_metric", "metric"),
    ("vid_limit", "vid_limit", "V"),
    ("vid_live", "vid", "V"),
    ("vddcr_cpu_power", "cpu_power", "W"),
    ("vddcr_soc_power", "soc_power", "W"),
    ("vddio_mem_power", "vddio_power", "W"),
    ("vdd18_power", "vdd18_power", "W"),
    ("socket_power", "socket_power", "W"),
    ("vdd_misc", "vdd_misc", "V"),
    ("vddcr_soc", "vsoc", "V"),
    ("cldo_vddg_iod", "vddg_iod", "V"),
    ("cldo_vddg_ccd", "vddg_ccd", "V"),
    ("cldo_vddp", "vddp", "V"),
]

# Phase 2 (Vermeer): rail columns plus the RAPL-validated socket power.
# Column names reuse the Granite Ridge vocabulary on purpose so downstream
# consumers see one schema; the offsets come from the profile map.
_EXTRA_VERMEER = [
    ("socket_power", "socket_power", "W"),
    ("vddcr_soc", "vsoc", "V"),
    ("cldo_vddg_iod", "vddg_iod", "V"),
    ("cldo_vddg_ccd", "vddg_ccd", "V"),
    ("cldo_vddp", "vddp", "V"),
]

_EXTRA_9800X3D = [
    ("vcore_telemetry_peak", "vcore_telemetry_peak", "V"),
    ("vcore_telemetry_average", "vcore_telemetry_average", "V"),
    ("vddio_mem_voltage", "vddio_mem_voltage", "V"),
    ("vddcr_cpu_vid", "vddcr_cpu_vid", "V"),
    ("hotspot_temp", "hotspot_temp", "C"),
    ("pkg_power", "pkg_power", "W"),
    ("soc_power", "soc_power", "W"),
    ("igpu_power", "igpu_power", "W"),
    ("igpu_clock", "igpu_clock", "MHz"),
]

def _resolve(profile, column, key, unit):
    if key is None:
        return (column, None, unit)
    idx = profile.gidx(key)
    if idx is None:
        return None
    return (column, idx, unit)


def global_fields(profile):
    """Return only fields whose meaning is established for this table version."""
    fields = []
    for column, key, unit in COMMON_FIELDS:
        resolved = _resolve(profile, column, key, unit)
        if resolved is not None:
            fields.append(resolved)
    if profile.pm_version == 0x620205:
        extras = _EXTRA_9950X3D
    elif profile.pm_version == 0x620105:
        extras = _EXTRA_9800X3D
    elif profile.pm_version == 0x380905:
        extras = _EXTRA_VERMEER
    else:
        extras = []
    for column, key, unit in extras:
        resolved = _resolve(profile, column, key, unit)
        if resolved is not None:
            fields.append(resolved)
    return fields

def named_fields(profile):
    fields = global_fields(profile)
    for core in range(profile.cores):
        fields.append((f"c{core}_power", profile.lane(profile.core_power, core), "W"))
        fields.append((f"c{core}_voltage", profile.lane(profile.core_voltage, core), "V"))
        fields.append((f"c{core}_temp", profile.lane(profile.core_temp, core), "C"))
        if profile.core_frequency is not None:
            fields.append(
                (f"c{core}_frequency", profile.lane(profile.core_frequency, core), "GHz")
            )
        if profile.core_eff_frequency is not None:
            fields.append(
                (f"c{core}_freq_eff",
                 profile.lane(profile.core_eff_frequency, core), "GHz")
            )
        if profile.core_fit is not None:
            fields.append((f"c{core}_fit",
                           profile.lane(profile.core_fit, core), "metric"))
        if profile.core_activity is not None:
            activity_name = (f"c{core}_activity_metric"
                             if profile.core_c0 is not None
                             else f"c{core}_light_cstate_metric")
            fields.append(
                (activity_name, profile.lane(profile.core_activity, core), "metric")
            )
        if profile.core_c0 is not None:
            fields.append((f"c{core}_c0_residency",
                           profile.lane(profile.core_c0, core), "%"))
        if profile.core_cc1 is not None:
            fields.append((f"c{core}_cc1_residency",
                           profile.lane(profile.core_cc1, core), "%"))
        fields.append((f"c{core}_cc6_residency",
                       profile.lane(profile.core_cc6, core), "%"))
        if profile.core_boost_limit is not None:
            boost_name = (f"c{core}_boost_limit" if profile.boost_limit_confident
                          else f"c{core}_boost_limit_candidate")
            fields.append((boost_name,
                           profile.lane(profile.core_boost_limit, core), "GHz"))
    return fields

def floats_to_row(d, ts, profile, fields=None):
    row = {}
    fields = fields or named_fields(profile)
    vcores = profile.lane_values(d, profile.core_voltage)
    for name, idx, _ in fields:
        if name == "timestamp":
            row[name] = f"{ts:.3f}"
        elif name == "vcore_peak":
            row[name] = f"{max(vcores):.4f}"
        elif name == "vcore_avg":
            row[name] = f"{sum(vcores)/profile.cores:.4f}"
        else:
            row[name] = f"{d[idx]:.4f}"
    return row

def live_power_index(profile):
    """Profile-backed package-power index for the live status line.

    Prefers ppt_value, falls back to socket_power, else None.  Explicit
    None checks throughout: index 0 is a valid table index.
    """
    idx = profile.gidx("ppt_value")
    if idx is None:
        idx = profile.gidx("socket_power")
    return idx
