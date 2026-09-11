#!/usr/bin/env python3
"""Conservative sysfs sensor discovery for live research experiments."""

from pathlib import Path


HWMON_ROOT = Path("/sys/class/hwmon")
POWERCAP_ROOT = Path("/sys/class/powercap")


def named_device(root, pattern, expected_name):
    """Return the only device whose ``name`` file matches, or fail closed."""
    matches = []
    for device in Path(root).glob(pattern):
        try:
            if (device / "name").read_text().strip() == expected_name:
                matches.append(device)
        except OSError:
            continue
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one {expected_name!r} device under {root}, "
            f"found {len(matches)}")
    return matches[0]


def hwmon_inputs(device_name, required, root=HWMON_ROOT):
    """Resolve uniquely labelled hwmon inputs and verify they are readable.

    ``required`` maps a logical name to ``(kind, exact_label)``, for example
    ``{"tctl": ("temp", "Tctl")}``.
    """
    device = named_device(root, "hwmon*", device_name)
    resolved = {}
    for logical_name, (kind, expected_label) in required.items():
        matches = []
        for label_path in device.glob(f"{kind}*_label"):
            try:
                label = label_path.read_text().strip()
            except OSError:
                continue
            if label != expected_label:
                continue
            input_path = device / f"{label_path.stem.removesuffix('_label')}_input"
            try:
                float(input_path.read_text().strip())
            except (OSError, ValueError) as exc:
                raise RuntimeError(
                    f"{device_name} {expected_label!r} input is not readable") from exc
            matches.append(input_path)
        if len(matches) != 1:
            raise RuntimeError(
                f"expected exactly one {device_name} {kind} input labelled "
                f"{expected_label!r}, found {len(matches)}")
        resolved[logical_name] = matches[0]
    return resolved


def powercap_energy(domain_name="package-0", root=POWERCAP_ROOT):
    """Return the unique readable energy counter for a named powercap domain."""
    device = named_device(root, "intel-rapl:*", domain_name)
    energy = device / "energy_uj"
    try:
        int(energy.read_text().strip())
    except (OSError, ValueError) as exc:
        raise RuntimeError(
            f"powercap domain {domain_name!r} has no readable energy counter") from exc
    return energy
