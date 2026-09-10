#!/usr/bin/env python3
"""GNR-SMU runtime package: profiles, safety gates, detection and telemetry.

Runtime code lives here. Research experiments live under research/ and must
never be imported by this package; user-facing entrypoints live under tools/
and import from here.
"""

from .hardware import (
    PM_TABLE_PATH,
    SIZE_PATH,
    VERSION_PATH,
    detect_active_slots,
    get_hardware_profile,
    hardware_supported,
    map_labels_supported,
)
from .profiles import (
    GLOBAL_FIELD_NAMES,
    PROFILES,
    HardwareProfile,
    validate_profile_globals,
)
from .safety import (
    BLOCKED_MP1_IDS,
    MAILBOXES,
    RSMU_ALLOWED_IDS,
    curve_optimizer_command,
    curve_optimizer_read_command,
    decode_curve_optimizer_response,
    msg_id_blocked,
    payload_allowed,
    read_curve_optimizer_offsets,
    smu_message_supported,
    smu_writes_supported,
)
from .telemetry import (
    COMMON_FIELDS,
    floats_to_row,
    global_fields,
    live_power_index,
    named_fields,
)

__all__ = [
    "PM_TABLE_PATH",
    "SIZE_PATH",
    "VERSION_PATH",
    "detect_active_slots",
    "get_hardware_profile",
    "hardware_supported",
    "map_labels_supported",
    "GLOBAL_FIELD_NAMES",
    "PROFILES",
    "HardwareProfile",
    "validate_profile_globals",
    "BLOCKED_MP1_IDS",
    "MAILBOXES",
    "RSMU_ALLOWED_IDS",
    "curve_optimizer_command",
    "curve_optimizer_read_command",
    "decode_curve_optimizer_response",
    "msg_id_blocked",
    "payload_allowed",
    "read_curve_optimizer_offsets",
    "smu_message_supported",
    "smu_writes_supported",
    "COMMON_FIELDS",
    "floats_to_row",
    "global_fields",
    "live_power_index",
    "named_fields",
]
