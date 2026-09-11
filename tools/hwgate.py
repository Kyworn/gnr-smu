#!/usr/bin/env python3
"""Compatibility entrypoint: the runtime now lives in :mod:`gnr_smu`.

``python3 tools/hwgate.py`` still runs the hardware-gate self-test.
New code should import from ``gnr_smu.hardware``, ``gnr_smu.safety``,
``gnr_smu.profiles`` or ``gnr_smu.telemetry`` instead.
"""

import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from gnr_smu.hardware import (  # noqa: E402,F401
    PM_TABLE_PATH,
    SIZE_PATH,
    VERSION_PATH,
    detect_active_slots,
    get_hardware_profile,
    hardware_supported,
    map_labels_supported,
)
from gnr_smu.profiles import (  # noqa: E402,F401
    GLOBAL_FIELD_NAMES,
    PROFILES,
    HardwareProfile,
    validate_profile_globals,
)
from gnr_smu.safety import (  # noqa: E402,F401
    BLOCKED_MP1_IDS,
    MAILBOXES,
    RSMU_ALLOWED_IDS,
    curve_optimizer_command,
    curve_optimizer_read_command,
    decode_curve_optimizer_response,
    msg_id_blocked,
    payload_allowed,
    read_curve_optimizer_offsets,
    smu_command_allowed,
    smu_message_supported,
    smu_writes_supported,
)

if __name__ == "__main__":
    from gnr_smu.selftest import main  # noqa: E402
    main()
