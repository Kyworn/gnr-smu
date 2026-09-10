import sys
import struct
import subprocess
import json
import os
import glob
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

CONFIG_PATH = os.path.join(
    os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
    "gnr_master.json",
)

# Only exact, measured PM-table profiles are accepted; tools/hwgate.py owns the
# offsets and refuses unknown CPU/table combinations.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hwgate import (curve_optimizer_command, get_hardware_profile,
                    hardware_supported, msg_id_blocked, payload_allowed,
                    read_curve_optimizer_offsets,
                    smu_message_supported,
                    smu_writes_supported)  # noqa: E402

# The MP1 message IDs now come from the hardware profile, per part. This file used to
# name them inline with 0x3D as TDC and 0x3C as EDC, an emphatic comment on each line
# and no measurement behind either; research/probe_tdc_edc.py settled it by read-back
# and they were the wrong way round, so the dialog had been sending the TDC box to EDC.

# --- Color Theme ---
BG_MAIN = "#101722"
BG_SIDEBAR = "#0b111b"
BG_PANEL = "#172233"
BG_INNER = "#1d2a3d"
BG_TREE = "#0b1018"
BG_TREE_ALT = "#121b27"
BG_TREE_CURRENT = "#193451"
BORDER = "#2c3c52"
TEXT_MAIN = "#e6edf3"
TEXT_MUTED = "#91a4bd"
ACCENT_RED = "#f05d68"
ACCENT_ORANGE = "#ff9d2e"
ACCENT_GREEN = "#36c987"
ACCENT_PURPLE = "#b48cff"
ACCENT_CYAN = "#42c8e8"


def physical_core_cpu_ids():
    """Return one logical CPU per physical core, ordered by package and core ID."""
    cores = {}
    for path in glob.glob("/sys/devices/system/cpu/cpu[0-9]*"):
        cpu = int(os.path.basename(path)[3:])
        topology = os.path.join(path, "topology")
        try:
            with open(os.path.join(topology, "physical_package_id")) as f:
                package = int(f.read())
            with open(os.path.join(topology, "core_id")) as f:
                core = int(f.read())
        except OSError:
            continue
        cores[(package, core)] = min(cpu, cores.get((package, core), cpu))
    return [cores[key] for key in sorted(cores)]


def read_hwmon_temperature(label):
    """Read a named k10temp channel without assuming a hwmon number."""
    for name_path in glob.glob("/sys/class/hwmon/hwmon*/name"):
        try:
            with open(name_path) as f:
                if f.read().strip() != "k10temp":
                    continue
            base = os.path.dirname(name_path)
            for label_path in glob.glob(os.path.join(base, "temp*_label")):
                with open(label_path) as f:
                    if f.read().strip().lower() != label.lower():
                        continue
                input_path = label_path.replace("_label", "_input")
                with open(input_path) as f:
                    return float(f.read()) / 1000
        except (OSError, ValueError):
            continue
    return None


# ================= THREAD : REAL-TIME KERNEL LOGS =================
class KernelLogWorker(QThread):
    log_signal = pyqtSignal(str)

    def run(self):
        try:
            process = subprocess.Popen(
                ["dmesg", "-w"], stdout=subprocess.PIPE, text=True
            )
            for line in iter(process.stdout.readline, ""):
                if "gnr_smu" in line or "ryzen_smu" in line:
                    clean_line = (
                        line.split("] ", 1)[-1].strip()
                        if "] " in line
                        else line.strip()
                    )
                    self.log_signal.emit(clean_line)
        except Exception:
            pass


# ================= CONTROL DIALOGS =================
class PowerControlDialog(QDialog):
    def __init__(self, cur_ppt, cur_tdc, cur_edc, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Power & Thermal Controls")
        self.setStyleSheet(
            f"background-color: {BG_MAIN}; color: {TEXT_MAIN}; font-family: 'Segoe UI';"
        )
        self.setFixedSize(300, 250)
        layout = QVBoxLayout(self)
        self.inputs = {}
        configs = [
            ("PPT", 250, "W", cur_ppt),
            ("TDC", 200, "A", cur_tdc),
            ("EDC", 250, "A", cur_edc),
        ]

        for name, max_val, unit, current_val in configs:
            row = QHBoxLayout()
            lbl = QLabel(name)
            lbl.setStyleSheet("font-weight: bold; width: 40px;")
            spin = QDoubleSpinBox()
            spin.setRange(0, max_val)
            spin.setSuffix(f" {unit}")
            spin.setStyleSheet(
                f"background-color: {BG_PANEL}; border: 1px solid {BORDER}; padding: 5px;"
            )
            spin.setValue(current_val)
            self.inputs[name] = spin
            row.addWidget(lbl)
            row.addWidget(spin)
            layout.addLayout(row)

        btn_apply = QPushButton("Apply Limits (MP1)")
        btn_apply.setStyleSheet(
            f"background-color: {ACCENT_RED}; color: white; border-radius: 4px; padding: 8px; font-weight: bold;"
        )
        btn_apply.clicked.connect(self.accept)
        layout.addStretch()
        layout.addWidget(btn_apply)


class CoreControlDialog(QDialog):
    def __init__(self, current_co_offsets, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Curve Optimizer (CO)")
        self.setStyleSheet(
            f"background-color: {BG_MAIN}; color: {TEXT_MAIN}; font-family: 'Segoe UI';"
        )
        height = 400 if len(current_co_offsets) <= 8 else 560
        self.setFixedSize(350, height)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Set Curve Optimizer Offsets per Core:"))
        self.spins = []
        grid = QGridLayout()
        for i in range(len(current_co_offsets)):
            lbl = QLabel(f"Core {i}:")
            spin = QSpinBox()
            spin.setRange(-50, 20)
            spin.setStyleSheet(
                f"background-color: {BG_PANEL}; border: 1px solid {BORDER}; padding: 3px;"
            )
            spin.setValue(current_co_offsets[i])
            self.spins.append(spin)
            grid.addWidget(lbl, i // 2, (i % 2) * 2)
            grid.addWidget(spin, i // 2, (i % 2) * 2 + 1)

        layout.addLayout(grid)
        btn_apply = QPushButton("Apply Curve Optimizer")
        btn_apply.setStyleSheet(
            f"background-color: {ACCENT_ORANGE}; color: white; border-radius: 4px; padding: 8px; font-weight: bold;"
        )
        btn_apply.clicked.connect(self.accept)
        layout.addStretch()
        layout.addWidget(btn_apply)


# ================= UI COMPONENTS =================
class TelemetryPanel(QFrame):
    def __init__(self, title, subtitle=""):
        super().__init__()
        self.setObjectName("telemetryPanel")
        self.setStyleSheet(
            f"QFrame#telemetryPanel {{ background: {BG_PANEL}; border: 1px solid {BORDER}; "
            "border-radius: 9px; } QLabel { border: none; background: transparent; }"
        )
        self.layout_box = QVBoxLayout(self)
        self.layout_box.setContentsMargins(15, 13, 15, 13)
        self.layout_box.setSpacing(8)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 14px; font-weight: 700; color: #e2e8f0;")
        self.layout_box.addWidget(title_lbl)
        if subtitle:
            subtitle_lbl = QLabel(subtitle)
            subtitle_lbl.setWordWrap(True)
            subtitle_lbl.setStyleSheet(f"font-size: 10px; color: {TEXT_MUTED};")
            self.layout_box.addWidget(subtitle_lbl)

    def add_row(self, text="--", color=TEXT_MAIN):
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(
            f"color: {color}; font-size: 12px; padding: 7px 8px; "
            f"background: {BG_INNER}; border-radius: 5px;"
        )
        self.layout_box.addWidget(label)
        return label


# ================= APPLICATION PRINCIPALE =================
class GNRMaster(QMainWindow):
    def __init__(self):
        super().__init__()
        self.profile, self.profile_reason = get_hardware_profile()
        self.core_count = self.profile.cores if self.profile else 8
        cpu_name = self.profile.name if self.profile else "Unsupported CPU"
        self.setWindowTitle(f"GNR Master - {cpu_name} Telemetry")
        self.setMinimumSize(980, 620)
        self.setStyleSheet(
            f"background-color: {BG_MAIN}; color: {TEXT_MAIN}; font-family: 'Segoe UI';"
        )

        self.config = self._load_config()
        self.sensor_update_ms = self._sanitize_update_interval(
            self.config.get("sensor_update_ms", 500)
        )
        self._preferences_timer = QTimer(self)
        self._preferences_timer.setSingleShot(True)
        self._preferences_timer.timeout.connect(self._save_sensor_preferences)

        # None on unvalidated hardware: no profile means no defensible default, and
        # the write dialog must not be pre-filled with another part's numbers. The
        # guardrails already block writes there, so this only affects what is shown.
        limits = self._read_pm_limits()
        self.current_ppt, self.current_tdc, self.current_edc = limits or (None, None, None)
        self.current_co = self.read_co_offsets()
        self.core_cpu_ids = physical_core_cpu_ids()

        self._build_interface()
        self._restore_window_size()

        self.log_msg(
            "Dashboard initialized. Listening to kernel logs...", "STATUS", ACCENT_GREEN
        )
        if not smu_writes_supported()[0]:
            self.log_msg(
                f"Read-only profile ({self.profile_reason}): SMU writes and "
                "SMU queries are not validated here — telemetry only.",
                "STATUS", ACCENT_GREEN,
            )
        if getattr(self, "_co_read_error", None):
            self.log_msg(
                f"Curve Optimizer readback unavailable: {self._co_read_error}",
                "ERROR", ACCENT_RED,
            )

        self.log_worker = KernelLogWorker()
        self.log_worker.log_signal.connect(
            lambda msg: self.log_msg(msg, "KERNEL", ACCENT_PURPLE)
        )
        self.log_worker.start()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(self.sensor_update_ms)

    def _build_interface(self):
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setCentralWidget(root)

        sidebar = QFrame()
        self.sidebar_width = 138
        sidebar.setFixedWidth(self.sidebar_width)
        sidebar.setStyleSheet(
            f"background: {BG_SIDEBAR}; border-right: 1px solid {BORDER};"
        )
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 16, 10, 16)
        sidebar_layout.setSpacing(7)
        brand = QLabel("GNR\nMASTER")
        brand.setStyleSheet(
            f"color: {ACCENT_ORANGE}; font-size: 16px; font-weight: 800; "
            "letter-spacing: 2px; padding: 2px 8px 18px 8px;"
        )
        sidebar_layout.addWidget(brand)
        self.nav_buttons = []
        self.pages = QStackedWidget()
        page_specs = [
            ("Dashboard", "◫", self._build_overview_page),
            ("Logs", "≡", self._build_logs_page),
        ]
        for index, (name, icon, builder) in enumerate(page_specs):
            button = QPushButton(f"{icon}  {name}")
            button.setCheckable(True)
            button.setMinimumHeight(42)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked, i=index: self._show_page(i))
            self.nav_buttons.append(button)
            sidebar_layout.addWidget(button)
            self.pages.addWidget(builder())
        sidebar_layout.addStretch()
        controls = QLabel("CONTROLS")
        controls.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 9px; font-weight: 700; padding: 0 8px;"
        )
        sidebar_layout.addWidget(controls)
        core_control = QPushButton("⚡  Core Control")
        power_control = QPushButton("⌁  Power / Thermal")
        for button in (core_control, power_control):
            button.setMinimumHeight(42)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(self._control_button_style())
            sidebar_layout.addWidget(button)
        core_control.clicked.connect(self.open_core_control)
        power_control.clicked.connect(self.open_power_control)
        root_layout.addWidget(sidebar)
        root_layout.addWidget(self.pages, 1)
        self._show_page(0)

    def _page(self, title, subtitle):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 17, 20, 17)
        layout.setSpacing(13)
        heading = QLabel(title)
        heading.setStyleSheet("font-size: 22px; font-weight: 750; color: #f8fafc;")
        layout.addWidget(heading)
        if subtitle:
            caption = QLabel(subtitle)
            caption.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED};")
            layout.addWidget(caption)
        return page, layout

    def _build_overview_page(self):
        page, layout = self._page("Dashboard", "")
        layout.setSpacing(8)
        status_bar = QFrame()
        status_bar.setObjectName("statusBar")
        status_bar.setStyleSheet(
            f"QFrame#statusBar {{ background: {BG_PANEL}; border: 1px solid {BORDER}; "
            "border-radius: 4px; }"
        )
        status_bar.setMinimumHeight(42)
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(12, 5, 9, 5)
        status_layout.setSpacing(8)
        self.summary_values = {}
        self._add_summary_metric(status_layout, "cpu", "CPU", ACCENT_ORANGE)
        for ccd in range(max(1, (self.core_count + 7) // 8)):
            self._add_summary_metric(status_layout, f"ccd{ccd}", f"CCD{ccd + 1}", ACCENT_CYAN)
        self._add_summary_separator(status_layout)
        self._add_summary_metric(status_layout, "frequency", "FREQ", ACCENT_PURPLE)
        self._add_summary_separator(status_layout)
        self._add_summary_metric(status_layout, "limits", "", TEXT_MAIN, minimum_width=270)
        status_layout.addStretch()
        self.reset_stats_button = QPushButton("Reset min/max")
        self.reset_stats_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_stats_button.setMinimumHeight(32)
        self.reset_stats_button.setStyleSheet(
            f"QPushButton {{ color: #cbd5e1; background: {BG_PANEL}; border: 1px solid {BORDER}; "
            "border-radius: 6px; padding: 6px 16px; font-size: 12px; font-weight: 600; }} "
            f"QPushButton:hover {{ border-color: {ACCENT_ORANGE}; color: {TEXT_MAIN}; }}"
        )
        self.reset_stats_button.clicked.connect(self._reset_sensor_stats)
        refresh_label = QLabel("Refresh rate")
        refresh_label.setStyleSheet(
            f"background: transparent; color: {TEXT_MUTED}; font-size: 12px; font-weight: 700;"
        )
        self.update_rate_input = QSpinBox()
        self.update_rate_input.setRange(100, 10000)
        self.update_rate_input.setSingleStep(100)
        self.update_rate_input.setSuffix(" ms")
        self.update_rate_input.setValue(self.sensor_update_ms)
        self.update_rate_input.setToolTip("Telemetry refresh interval. Saved in the GUI configuration.")
        self.update_rate_input.setMinimumHeight(32)
        self.update_rate_input.setStyleSheet(
            f"background: {BG_INNER}; color: {TEXT_MAIN}; border: 1px solid {BORDER}; "
            "border-radius: 6px; padding: 6px 8px; font-size: 12px; font-weight: 600;"
        )
        self.update_rate_input.valueChanged.connect(self._set_update_interval)
        status_layout.addWidget(refresh_label)
        status_layout.addWidget(self.update_rate_input)
        status_layout.addWidget(self.reset_stats_button)
        layout.addWidget(status_bar)

        self.sensor_tree = QTreeWidget()
        self.sensor_tree.setHeaderLabels(["Sensor", "Current", "Minimum", "Maximum", "Average"])
        self.sensor_tree.setRootIsDecorated(True)
        self.sensor_tree.setAlternatingRowColors(True)
        self.sensor_tree.setUniformRowHeights(True)
        self.sensor_tree.setIndentation(16)
        self.sensor_tree.setAnimated(False)
        self.sensor_tree.setStyleSheet(
            f"QTreeWidget {{ background: {BG_TREE}; alternate-background-color: {BG_TREE_ALT}; "
            f"color: {TEXT_MAIN}; border: 1px solid {BORDER}; font-family: Consolas, monospace; "
            "font-size: 12px; } "
            "QTreeWidget::item { height: 22px; border-bottom: 1px solid #172231; } "
            "QTreeWidget::item:selected { background: #214364; color: #ffffff; } "
            f"QHeaderView::section {{ background: {BG_PANEL}; color: {TEXT_MAIN}; border: none; "
            f"border-right: 1px solid {BORDER}; padding: 5px 8px; font-weight: 700; }}"
        )
        header = self.sensor_tree.header()
        header.setStretchLastSection(False)
        header.setSectionsMovable(True)
        header.setSectionsClickable(True)
        header.setMinimumSectionSize(80)
        header.setToolTip("Drag column headers to reorder them; drag separators to resize.")
        for column in range(5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
        self.sensor_tree.setColumnWidth(0, 620)
        for column in range(1, 5):
            self.sensor_tree.setColumnWidth(column, 145)
        saved_header = self.config.get("sensor_header_state")
        if isinstance(saved_header, str):
            try:
                header.restoreState(QByteArray.fromBase64(saved_header.encode("ascii")))
            except UnicodeEncodeError:
                pass
        self.sensor_items = {}
        self.sensor_units = {}
        self.sensor_stats = {}
        self.sensor_groups = {}
        self._build_sensor_tree()
        header.sectionMoved.connect(self._queue_sensor_preferences)
        header.sectionResized.connect(self._queue_sensor_preferences)
        self.sensor_tree.itemExpanded.connect(self._queue_sensor_preferences)
        self.sensor_tree.itemCollapsed.connect(self._queue_sensor_preferences)
        layout.addWidget(self.sensor_tree)
        return page

    def _add_summary_section(self, layout, title):
        label = QLabel(title)
        label.setStyleSheet(
            f"background: transparent; color: {TEXT_MUTED}; font-size: 9px; font-weight: 800;"
        )
        layout.addWidget(label)

    def _add_summary_separator(self, layout):
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setStyleSheet(f"background: {BORDER}; border: none;")
        separator.setFixedWidth(1)
        layout.addWidget(separator)

    def _add_summary_metric(self, layout, key, title, color, minimum_width=0):
        metric = QWidget()
        metric.setStyleSheet("background: transparent;")
        if minimum_width:
            metric.setMinimumWidth(minimum_width)
        metric_layout = QHBoxLayout(metric)
        metric_layout.setContentsMargins(0, 0, 0, 0)
        metric_layout.setSpacing(5)
        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"background: transparent; color: {TEXT_MUTED}; font-size: 12px; font-weight: 700;"
        )
        value_label = QLabel("--")
        value_label.setStyleSheet(
            f"background: transparent; color: {color}; font-size: 12px; font-weight: 700;"
        )
        if title:
            metric_layout.addWidget(title_label)
        metric_layout.addWidget(value_label)
        layout.addWidget(metric)
        self.summary_values[key] = value_label

    def _set_summary(self, key, value):
        label = self.summary_values.get(key)
        if label is not None:
            label.setText(value)

    def _add_sensor_group(self, parent, label, expanded=True):
        item = QTreeWidgetItem([label, "", "", "", ""])
        item.setFirstColumnSpanned(True)
        parent_key = parent.data(0, Qt.ItemDataRole.UserRole) if parent is not None else ""
        group_key = f"{parent_key}/{label}" if parent_key else label
        expansion_config = self.config.get("sensor_group_expansion", {})
        if not isinstance(expansion_config, dict):
            expansion_config = {}
        saved_state = expansion_config.get(group_key)
        item.setData(0, Qt.ItemDataRole.UserRole, group_key)
        item.setForeground(0, QColor("#f8fafc"))
        font = item.font(0)
        font.setBold(True)
        item.setFont(0, font)
        if parent is None:
            self.sensor_tree.addTopLevelItem(item)
        else:
            parent.addChild(item)
        # QTreeWidget only applies the initial expansion state once the item is
        # attached to the tree.  This keeps a fresh configuration fully open.
        item.setExpanded(saved_state if isinstance(saved_state, bool) else expanded)
        self.sensor_groups[group_key] = item
        return item

    def _add_sensor(self, parent, key, label, unit, tooltip="", current_color=None):
        item = QTreeWidgetItem([label, "--", "--", "--", "--"])
        for column in range(1, 5):
            item.setTextAlignment(
                column,
                int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
            )
        item.setBackground(1, QColor(BG_TREE_CURRENT))
        item.setForeground(1, QColor(current_color or "#d6e6ff"))
        if tooltip:
            item.setToolTip(0, tooltip)
        parent.addChild(item)
        self.sensor_items[key] = item
        self.sensor_units[key] = unit

    def _build_sensor_tree(self):
        temperatures = self._add_sensor_group(None, "Temperatures")
        self._add_sensor(temperatures, "tctl", "CPU (Tctl/Tdie)", "°C")
        for ccd in range(max(1, (self.core_count + 7) // 8)):
            self._add_sensor(temperatures, f"tccd{ccd}", f"CPU CCD{ccd + 1} (k10temp)", "°C")
        core_temps = self._add_sensor_group(temperatures, "Core Temperatures")
        for core in range(self.core_count):
            self._add_sensor(core_temps, f"core_temp_{core}",
                             f"Core {core} (CCD{core // 8 + 1})", "°C")

        l3 = self._add_sensor_group(temperatures, "L3 Cache Temperatures")
        l3.setToolTip(0, "PM-table lanes validated by cache-specific load testing.")
        if self.profile and self.profile.ccd_candidate_count:
            for ccd in range(self.profile.ccd_candidate_count):
                if self.profile.pm_version == 0x620105:
                    evidence = (
                        "A shared 64 MiB L3 workload raised this lane +6.97 K; "
                        "an ALU-only control at nearly the same core/Tccd "
                        "temperature raised it only +1.05 K."
                    )
                else:
                    evidence = (
                        "CCD-selective; a temperature-matched ALU-vs-cache test "
                        "raised it an extra 4-8 K under cache load."
                    )
                self._add_sensor(l3, f"ccd_l3_temp_{ccd}",
                                 f"CCD{ccd + 1} L3 Cache · "
                                 f"d[{self.profile.ccd_l3_temperature + ccd}]",
                                 "°C",
                                 evidence)
        else:
            l3.setText(0, "L3 Cache Temperatures (not mapped for this profile)")

        limits = self._add_sensor_group(None, "Limits & current")
        self._add_sensor(limits, "ppt", "CPU PPT", "W")
        self._add_sensor(limits, "ppt_limit", "CPU PPT Limit", "W")
        self._add_sensor(limits, "tdc", "CPU TDC", "A")
        self._add_sensor(limits, "tdc_limit", "CPU TDC Limit", "A")
        if self.profile and self.profile.edc_value is not None:
            self._add_sensor(limits, "edc", "CPU EDC", "A",
                             f"Live PM-table candidate d[{self.profile.edc_value}], not yet SMU-confirmed")
        self._add_sensor(limits, "edc_limit", "CPU EDC Limit", "A")
        self._add_sensor(limits, "thermal_limit", "Thermal Limit", "°C")

        power = self._add_sensor_group(None, "Power")
        for key, label in (
            ("socket_power", "CPU Socket Power"), ("cpu_power", "CPU Core Power"),
            ("core_power", "Core Power Sum"), ("soc_power", "CPU SoC Power"),
            ("vddio_power", "VDDIO MEM Power"), ("vdd18_power", "VDD18 Power"),
        ):
            self._add_sensor(power, key, label, "W")
        core_power = self._add_sensor_group(power, "Core Powers")
        for core in range(self.core_count):
            self._add_sensor(core_power, f"core_power_{core}",
                             f"Core {core} (CCD{core // 8 + 1})", "W",
                             self._block_tooltip("core_power"))

        clocks = self._add_sensor_group(None, "Clocks")
        for key, label in (("fclk", "Infinity Fabric Clock (FCLK)"),
                           ("uclk", "Memory Controller Clock (UCLK)"),
                           ("mclk", "Memory Clock (MCLK)")):
            self._add_sensor(clocks, key, label, "MHz",
                             self._block_tooltip(key))
        core_clocks = self._add_sensor_group(clocks, "Core Clocks", expanded=True)
        for core in range(self.core_count):
            self._add_sensor(core_clocks, f"core_clock_{core}",
                             f"Core {core} (CCD{core // 8 + 1})", "MHz",
                             "Live frequency from Linux cpufreq on the 9950X3D")
        if self.profile is not None and self.profile.core_eff_frequency is not None:
            eff_clocks = self._add_sensor_group(clocks, "Core Effective Clocks")
            for core in range(self.core_count):
                self._add_sensor(
                    eff_clocks, f"core_efffreq_{core}",
                    f"Core {core} (CCD{core // 8 + 1})", "MHz",
                    f"Sleep-aware effective frequency "
                    f"d[{self.profile.lane(self.profile.core_eff_frequency, core)}].")

        voltages = self._add_sensor_group(None, "Voltages")
        for key, label in (("vcore_peak", "Vcore Peak"), ("vcore_avg", "Vcore Average"),
                           ("vsoc", "VDDCR_SOC"), ("vdd_misc", "VDD_MISC"),
                           ("vddg_iod", "CLDO_VDDG_IOD"), ("vddg_ccd", "CLDO_VDDG_CCD"),
                           ("vddp", "CLDO_VDDP"), ("vid", "CPU VID"),
                           ("vid_limit", "VID Limit")):
            self._add_sensor(voltages, key, label, "V",
                             self._block_tooltip(key))
        core_voltages = self._add_sensor_group(voltages, "Core Voltages")
        for core in range(self.core_count):
            self._add_sensor(core_voltages, f"core_voltage_{core}",
                             f"Core {core} (CCD{core // 8 + 1})", "V",
                             self._block_tooltip("core_voltage"))

        residency = self._add_sensor_group(None, "Core residency & FIT")
        ccd_summary = self._add_sensor_group(residency, "CCD residency summary")
        has_direct_c0 = self.profile is not None and self.profile.core_c0 is not None
        for ccd in range(max(1, (self.core_count + 7) // 8)):
            label = f"CCD{ccd + 1} C0 residency" if has_direct_c0 else f"CCD{ccd + 1} active/load estimate"
            self._add_sensor(ccd_summary, f"ccd_c0_{ccd}", label, "%",
                             "C0 is direct on the 9950X3D; 9800X3D uses 100 - CC6.",
                             ACCENT_GREEN)
            if has_direct_c0:
                self._add_sensor(ccd_summary, f"ccd_cc1_{ccd}", f"CCD{ccd + 1} CC1 residency", "%",
                                 current_color=ACCENT_CYAN)
            self._add_sensor(ccd_summary, f"ccd_cc6_{ccd}", f"CCD{ccd + 1} CC6 residency", "%",
                             current_color=ACCENT_PURPLE)

        if self.profile is None or self.profile.core_fit is not None:
            fit_group = self._add_sensor_group(residency, "FIT / related metric")
            for core in range(self.core_count):
                ccd = core // 8 + 1
                self._add_sensor(fit_group, f"core_fit_{core}",
                                 f"Core {core} FIT-related metric (CCD{ccd})", "",
                                 "Per-core PM-table FIT/related metric; not a direct temperature or voltage reading.",
                                 ACCENT_ORANGE)

        c0_group = self._add_sensor_group(
            residency, "C0 residency · active cores" if has_direct_c0 else "Active/load estimate · 100 - CC6"
        )
        for core in range(self.core_count):
            self._add_sensor(c0_group, f"core_c0_{core}",
                             f"Core {core} (CCD{core // 8 + 1})", "%",
                             current_color=ACCENT_GREEN)

        cc1_group = None
        if has_direct_c0:
            cc1_group = self._add_sensor_group(residency, "CC1 residency · light idle")
            for core in range(self.core_count):
                self._add_sensor(cc1_group, f"core_cc1_{core}",
                                 f"Core {core} (CCD{core // 8 + 1})", "%",
                                 current_color=ACCENT_CYAN)

        cc6_group = self._add_sensor_group(residency, "CC6 residency · deep idle")
        for core in range(self.core_count):
            self._add_sensor(cc6_group, f"core_cc6_{core}",
                             f"Core {core} (CCD{core // 8 + 1})", "%",
                             current_color=ACCENT_PURPLE)
        # The CO readback performs sysfs writes (smu_args/rsmu_cmd), so it is
        # only built where SMU queries are validated.  On write-blocked
        # profiles the group is absent rather than full of "--".
        writes_ok, _ = smu_writes_supported()
        if writes_ok:
            co_config = self._add_sensor_group(None, "Curve Optimizer · active SMU value")
            for core in range(self.core_count):
                self._add_sensor(
                    co_config, f"co_{core}", f"Core {core} (CCD{core // 8 + 1})", "int",
                    "Active value read through RSMU GetDldoPsmMargin (0xD5) at startup "
                    "and before/after changes from this application.",
                )
    def _format_sensor_value(self, value, unit):
        if value is None:
            return "--"
        if unit == "MHz":
            return f"{value:,.0f} MHz"
        if unit in ("°C", "%"):
            return f"{value:.1f} {unit}"
        if unit in ("W", "A", "V"):
            return f"{value:.3f} {unit}"
        if unit == "int":
            return f"{value:.0f}"
        return f"{value:.2f}"

    def _set_sensor(self, key, value):
        item = self.sensor_items.get(key)
        if item is None:
            return
        unit = self.sensor_units[key]
        item.setText(1, self._format_sensor_value(value, unit))
        if value is None:
            return
        stat = self.sensor_stats.get(key)
        if stat is None:
            stat = [value, value, value, 1]
            self.sensor_stats[key] = stat
        else:
            stat[0] = min(stat[0], value)
            stat[1] = max(stat[1], value)
            stat[2] += value
            stat[3] += 1
        item.setText(2, self._format_sensor_value(stat[0], unit))
        item.setText(3, self._format_sensor_value(stat[1], unit))
        item.setText(4, self._format_sensor_value(stat[2] / stat[3], unit))

    def _reset_sensor_stats(self):
        self.sensor_stats.clear()
        for item in self.sensor_items.values():
            for column in range(2, 5):
                item.setText(column, "--")
        self.log_msg("Sensor minimum, maximum and average reset.", "STATUS", ACCENT_GREEN)

    def _build_logs_page(self):
        page, layout = self._page(
            "Kernel & Application Logs", "Filtered ryzen_smu / gnr_smu messages and application events"
        )
        panel = TelemetryPanel("LIVE LOG")
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(
            f"background: {BG_INNER}; border: none; color: #a5b4c8; "
            "font-family: Consolas, monospace; font-size: 11px; padding: 8px;"
        )
        panel.layout_box.addWidget(self.log_text)
        layout.addWidget(panel)
        return page

    def _nav_button_style(self):
        return (
            f"QPushButton {{ color: {TEXT_MUTED}; background: transparent; border: none; "
            "border-radius: 6px; text-align: left; padding: 9px 11px; font-size: 12px; }} "
            f"QPushButton:hover {{ background: {BG_INNER}; color: {TEXT_MAIN}; }} "
            f"QPushButton:checked {{ background: #2d251d; color: {ACCENT_ORANGE}; "
            f"font-weight: 700; border-left: 3px solid {ACCENT_ORANGE}; }}"
        )

    def _control_button_style(self):
        return (
            f"QPushButton {{ color: #cbd5e1; background: {BG_PANEL}; border: 1px solid {BORDER}; "
            "border-radius: 6px; text-align: left; padding: 8px; font-size: 11px; }} "
            f"QPushButton:hover {{ border-color: {ACCENT_ORANGE}; color: {TEXT_MAIN}; }}"
        )

    def _show_page(self, index):
        self.pages.setCurrentIndex(index)
        style = self._nav_button_style()
        for i, button in enumerate(self.nav_buttons):
            button.setStyleSheet(style)
            button.setChecked(i == index)

    def log_msg(self, msg, level="INFO", color="#3b82f6"):
        self.log_text.append(f"<span style='color:{color};'>[{level}]</span> {msg}")
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def _load_config(self):
        try:
            with open(CONFIG_PATH, "r") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            # CO is now read from the SMU. Never retain the former local cache,
            # which could become stale after a reboot or BIOS change.
            data.pop("co_offsets", None)
            return data
        except Exception:
            return {}

    @staticmethod
    def _sanitize_update_interval(value):
        try:
            return max(100, min(10000, int(value)))
        except (TypeError, ValueError):
            return 500

    def _fit_window_size(self, width, height):
        width = max(self.minimumWidth(), int(width))
        height = max(self.minimumHeight(), int(height))
        return QSize(width, height)

    def _default_window_size(self):
        column_width = sum(
            self.sensor_tree.header().sectionSize(column) for column in range(5)
        )
        scrollbar_width = self.sensor_tree.verticalScrollBar().sizeHint().width()
        width = self.sidebar_width + column_width + scrollbar_width + 52
        return self._fit_window_size(width, 900)

    def _restore_window_size(self):
        saved_size = self.config.get("window_size")
        if (isinstance(saved_size, list) and len(saved_size) == 2
                and all(isinstance(value, (int, float)) for value in saved_size)):
            size = self._fit_window_size(saved_size[0], saved_size[1])
        else:
            size = self._default_window_size()
        self.resize(size)

    def _save_config(self, updates):
        try:
            self.config.update(updates)
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w") as f:
                json.dump(self.config, f, indent=2, sort_keys=True)
            return True
        except Exception:
            return False

    def _queue_sensor_preferences(self, *_):
        self._preferences_timer.start(300)

    def _save_sensor_preferences(self):
        if not hasattr(self, "sensor_tree"):
            return
        header_state = bytes(self.sensor_tree.header().saveState().toBase64()).decode("ascii")
        group_expansion = {
            key: item.isExpanded() for key, item in self.sensor_groups.items()
        }
        self._save_config({
            "sensor_header_state": header_state,
            "sensor_group_expansion": group_expansion,
            "sensor_update_ms": self.sensor_update_ms,
            "window_size": [self.width(), self.height()],
        })

    def _set_update_interval(self, value):
        self.sensor_update_ms = self._sanitize_update_interval(value)
        if hasattr(self, "timer"):
            self.timer.setInterval(self.sensor_update_ms)
        self._queue_sensor_preferences()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_preferences_timer") and hasattr(self, "sensor_tree"):
            self._queue_sensor_preferences()

    def closeEvent(self, event):
        self._save_sensor_preferences()
        super().closeEvent(event)

    def read_co_offsets(self):
        if not smu_writes_supported()[0]:
            # No RSMU query either: the readback path writes smu_args/rsmu_cmd.
            self._co_read_error = None
            return [None] * self.core_count
        try:
            offsets = read_curve_optimizer_offsets(self.profile)
            self._co_read_error = None
            return offsets
        except Exception as e:
            self._co_read_error = str(e)
            return [None] * self.core_count

    def refresh_co_values(self):
        try:
            self.current_co = read_curve_optimizer_offsets(self.profile)
            self._co_read_error = None
            return True
        except Exception as e:
            self._co_read_error = str(e)
            self.current_co = [None] * self.core_count
            return False

    def send_smu_cmd(self, msg_id, arg0=0):
        ok, why = smu_writes_supported()
        if not ok:
            self.log_msg(f"GUARDRAIL: SMU writes disabled — {why}", "ERROR", ACCENT_RED)
            return False
        # An ID has to clear both: the allowlist is what this profile is known to
        # accept, the never-send list what nothing may send on any part.
        if not smu_message_supported(self.profile, msg_id):
            self.log_msg(
                f"GUARDRAIL: MSG {hex(msg_id)} is not in the {self.profile.name} "
                "command allowlist",
                "ERROR", ACCENT_RED,
            )
            return False
        blocked, reason = msg_id_blocked(msg_id)
        if blocked:
            self.log_msg(f"GUARDRAIL: {reason}", "ERROR", ACCENT_RED)
            return False
        # The ID being allowed says nothing about the number riding with it, and the
        # arg0 & 0xFFFFFFFF below would happily turn a negative spinbox value into
        # four billion milliamps. The spinbox bounds are a convenience; this is the
        # check.
        ok, why = payload_allowed(self.profile, msg_id, arg0)
        if not ok:
            self.log_msg(f"GUARDRAIL: {why}", "ERROR", ACCENT_RED)
            return False

        SMU_ARGS = "/sys/kernel/ryzen_smu_drv/smu_args"
        SMU_CMD = "/sys/kernel/ryzen_smu_drv/mp1_smu_cmd"

        try:
            # 1) Write args: 6 x uint32 LE (arg0 in slot 0, rest = 0)
            args_bin = struct.pack("<6I", arg0 & 0xFFFFFFFF, 0, 0, 0, 0, 0)
            with open(SMU_ARGS, "wb") as f:
                f.write(args_bin)

            # 2) Write MSG ID as uint32 LE to trigger the command
            cmd_bin = struct.pack("<I", msg_id)
            with open(SMU_CMD, "wb") as f:
                f.write(cmd_bin)

            # 3) Read response
            with open(SMU_CMD, "rb") as f:
                rsp_data = f.read(4)
            rsp = struct.unpack("<I", rsp_data)[0] if len(rsp_data) == 4 else 0xFF

            rsp_str = {
                1: "OK",
                0xFD: "REJECTED",
                0xFE: "UNKNOWN_CMD",
                0xFF: "FAILED",
            }.get(rsp, f"0x{rsp:02X}")
            color = ACCENT_GREEN if rsp == 1 else ACCENT_RED
            self.log_msg(
                f"SMU MP1 -> MSG: {hex(msg_id)}, ARG0: {hex(arg0)} => RSP: {rsp_str}",
                "SMU",
                color,
            )
            return rsp == 1
        except Exception as e:
            self.log_msg(f"SMU write failed: {str(e)}", "ERROR", ACCENT_RED)
            return False

    def _smu_controls_available(self):
        ok, why = smu_writes_supported()
        if not ok:
            self.log_msg(
                f"GUARDRAIL: SMU controls disabled — {why}", "ERROR", ACCENT_RED
            )
        return ok

    def open_power_control(self):
        if not self._smu_controls_available():
            return
        if None in (self.current_ppt, self.current_tdc, self.current_edc):
            # _smu_controls_available() already covers this, but the dialog does
            # arithmetic on these and a None here would be a traceback in a window
            # that is about to write to the SMU.
            self.log_msg("Current limits unknown — refusing to open the write dialog "
                         "with no defensible defaults.", "ERROR", ACCENT_RED)
            return
        dlg = PowerControlDialog(
            self.current_ppt, self.current_tdc, self.current_edc, self
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            requested = {
                "PPT": dlg.inputs["PPT"].value(),
                "TDC": dlg.inputs["TDC"].value(),
                "EDC": dlg.inputs["EDC"].value(),
            }
            current = {"PPT": self.current_ppt, "TDC": self.current_tdc,
                       "EDC": self.current_edc}
            changed = {name: value for name, value in requested.items()
                       if abs(value - current[name]) >= 0.001}
            if not changed:
                self.log_msg("Power limits unchanged; nothing sent.", "STATUS")
                return
            commands = {
                "PPT": self.profile.ppt_msg,
                "TDC": self.profile.tdc_msg,
                "EDC": self.profile.edc_msg,
            }
            for name, value in changed.items():
                if self.send_smu_cmd(commands[name], int(value * 1000)):
                    setattr(self, f"current_{name.lower()}", value)

    def open_core_control(self):
        if not self._smu_controls_available():
            return
        if not self.refresh_co_values():
            self.log_msg(
                f"Curve Optimizer readback unavailable; refusing to prefill controls: "
                f"{getattr(self, '_co_read_error', 'unknown error')}",
                "ERROR", ACCENT_RED,
            )
            return
        dlg = CoreControlDialog(self.current_co, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            changed = [(i, spin.value()) for i, spin in enumerate(dlg.spins)
                       if spin.value() != self.current_co[i]]
            if not changed:
                self.log_msg("Curve Optimizer unchanged; nothing sent.", "STATUS")
                return
            applied = []
            for core, value in changed:
                msg_id, arg0 = curve_optimizer_command(self.profile, core, value)
                if self.send_smu_cmd(msg_id, arg0):
                    self.current_co[core] = value
                    applied.append(core)
            if applied:
                if self.refresh_co_values():
                    self.log_msg(
                        f"CO offsets applied and verified for cores {applied}: "
                        f"{self.current_co}", "STATUS", ACCENT_GREEN,
                    )
                else:
                    self.log_msg(
                        f"CO writes succeeded for cores {applied}, but readback failed: "
                        f"{self._co_read_error}", "ERROR", ACCENT_RED,
                    )

    def _read_pm_limits(self):
        # Fallback comes from the profile, not from a copy of the 9800X3D's numbers:
        # this feeds the write dialog's defaults, and handing a 9950X3D 162/120/180
        # because its table read failed is the kind of wrong default that gets
        # written back. Unvalidated hardware has no profile and so gets nothing.
        # Profiles without mapped limits (Vermeer) also get nothing: the dialog
        # refuses to open, so a wrong prefill can never reach the SMU.
        if not hardware_supported()[0] or self.profile is None:
            return None
        if (self.profile.gidx("ppt_limit") is None
                or self.profile.gidx("tdc_limit") is None
                or self.profile.gidx("edc_limit") is None):
            return None
        stock = (float(self.profile.stock_ppt), float(self.profile.stock_tdc),
                 float(self.profile.stock_edc))
        try:
            with open("/sys/kernel/ryzen_smu_drv/pm_table", "rb") as f:
                d = struct.unpack(f"<{self.profile.float_count}f",
                                  f.read(self.profile.table_size))
            # PPT, TDC (0x020) and EDC (0x0FC) limits from the profile map.
            # Corrected 2026-07-30: this used to return d[10] as TDC — that
            # offset is the thermal limit in °C (88), so the write dialog
            # pre-filled TDC with 88 A and EDC with 120 A (the real TDC limit).
            return (d[self.profile.gidx("ppt_limit")],
                    d[self.profile.gidx("tdc_limit")],
                    d[self.profile.gidx("edc_limit")])
        except Exception:
            return stock

    def _core_frequency_mhz(self, table, core):
        """Use the PM-table frequency where mapped, otherwise Linux cpufreq."""
        if self.profile.core_frequency is not None:
            return table[self.profile.lane(self.profile.core_frequency, core)] * 1000
        if core >= len(self.core_cpu_ids):
            return None
        path = (f"/sys/devices/system/cpu/cpu{self.core_cpu_ids[core]}/"
                "cpufreq/scaling_cur_freq")
        try:
            with open(path) as f:
                return float(f.read()) / 1000
        except (OSError, ValueError):
            return None

    def _g(self, d, name):
        """Global telemetry value by canonical map name, None when unmapped.

        Unmapped sensors stay "--" in the tree: unsupported is shown as
        missing, never filled from another part's offset.
        """
        idx = self.profile.gidx(name)
        return d[idx] if idx is not None else None

    def _block_tooltip(self, block):
        """Confidence note for a block/global name; "" unless high.

        Unmapped names ("--" sensors) get no tooltip: only an explicitly
        high-confidence mapping is marked.
        """
        if self.profile is not None and self.profile.confidence(block) == "high":
            return ("High-confidence mapping (load response + canonical layout "
                    "order), not independently cross-validated — see "
                    "docs/VERMEER_5600X.md.")
        return ""

    @staticmethod
    def _fmt_opt(value, fmt):
        return fmt.format(value) if value is not None else "--"

    def _update_sensor_tree(self, d):
        vcores = self.profile.lane_values(d, self.profile.core_voltage)
        tctl = self._g(d, "tctl")
        self._set_sensor("tctl", tctl)
        self._set_summary("cpu", f"{tctl:.1f} °C" if tctl is not None else "--")
        ppt = self._g(d, "ppt_value")
        ppt_limit = self._g(d, "ppt_limit")
        tdc = self._g(d, "tdc_value")
        tdc_limit = self._g(d, "tdc_limit")
        edc_limit = self._g(d, "edc_limit")
        self._set_sensor("ppt", ppt)
        self._set_sensor("ppt_limit", ppt_limit)
        self._set_sensor("tdc", tdc)
        self._set_sensor("tdc_limit", tdc_limit)
        self._set_sensor("edc_limit", edc_limit)
        self._set_sensor("thermal_limit", self._g(d, "thm_limit"))
        self._set_sensor("socket_power", self._g(d, "socket_power"))
        if self.profile.edc_value is not None:
            current_edc = d[self.profile.edc_value]
            self._set_sensor("edc", current_edc)
            self._set_summary(
                "limits",
                f"PPT {self._fmt_opt(ppt, '{:.0f} W')}/"
                f"{self._fmt_opt(ppt_limit, '{:.0f} W')} · "
                f"TDC {self._fmt_opt(tdc, '{:.0f} A')}/"
                f"{self._fmt_opt(tdc_limit, '{:.0f} A')} · "
                f"EDC {current_edc:.0f}/"
                f"{self._fmt_opt(edc_limit, '{:.0f} A')}",
            )
        else:
            self._set_summary(
                "limits",
                f"PPT {self._fmt_opt(ppt, '{:.0f} W')}/"
                f"{self._fmt_opt(ppt_limit, '{:.0f} W')} · "
                f"TDC {self._fmt_opt(tdc, '{:.0f} A')}/"
                f"{self._fmt_opt(tdc_limit, '{:.0f} A')} · "
                f"EDC {self._fmt_opt(edc_limit, '{:.0f} A')}",
            )
        self._set_sensor("cpu_power", self._g(d, "cpu_power"))
        self._set_sensor("core_power", sum(
            self.profile.lane_values(d, self.profile.core_power)))
        self._set_sensor("soc_power", self._g(d, "soc_power"))
        self._set_sensor("vddio_power", self._g(d, "vddio_power"))
        self._set_sensor("vdd18_power", self._g(d, "vdd18_power"))
        self._set_sensor("fclk", self._g(d, "fclk"))
        self._set_sensor("uclk", self._g(d, "uclk"))
        self._set_sensor("mclk", self._g(d, "mclk"))
        self._set_sensor("vcore_peak", max(vcores))
        self._set_sensor("vcore_avg", sum(vcores) / self.core_count)
        self._set_sensor("vsoc", self._g(d, "vsoc"))
        self._set_sensor("vdd_misc", self._g(d, "vdd_misc"))
        self._set_sensor("vddg_iod", self._g(d, "vddg_iod"))
        self._set_sensor("vddg_ccd", self._g(d, "vddg_ccd"))
        self._set_sensor("vddp", self._g(d, "vddp"))
        self._set_sensor("vid", self._g(d, "vid"))
        self._set_sensor("vid_limit", self._g(d, "vid_limit"))

        ccd_count = max(1, (self.core_count + 7) // 8)
        for ccd in range(ccd_count):
            ccd_temp = read_hwmon_temperature(f"Tccd{ccd + 1}")
            self._set_sensor(f"tccd{ccd}", ccd_temp)
            self._set_summary(
                f"ccd{ccd}", f"{ccd_temp:.1f} °C" if ccd_temp is not None else "--"
            )
            start = ccd * 8
            stop = min(self.core_count, start + 8)
            cc6_values = [d[self.profile.lane(self.profile.core_cc6, core)]
                          for core in range(start, stop)]
            if self.profile.core_c0 is not None:
                c0_values = [d[self.profile.lane(self.profile.core_c0, core)]
                             for core in range(start, stop)]
                cc1_values = [d[self.profile.lane(self.profile.core_cc1, core)]
                              for core in range(start, stop)]
                self._set_sensor(f"ccd_c0_{ccd}", sum(c0_values) / len(c0_values))
                self._set_sensor(f"ccd_cc1_{ccd}", sum(cc1_values) / len(cc1_values))
            else:
                self._set_sensor(f"ccd_c0_{ccd}", 100 - sum(cc6_values) / len(cc6_values))
            self._set_sensor(f"ccd_cc6_{ccd}", sum(cc6_values) / len(cc6_values))
        if self.profile.ccd_candidate_count:
            for ccd in range(self.profile.ccd_candidate_count):
                self._set_sensor(f"ccd_l3_temp_{ccd}", d[self.profile.ccd_l3_temperature + ccd])

        frequencies = []
        for core in range(self.core_count):
            freq = self._core_frequency_mhz(d, core)
            if freq is not None:
                frequencies.append(freq)
            self._set_sensor(f"core_temp_{core}",
                             d[self.profile.lane(self.profile.core_temp, core)])
            self._set_sensor(f"core_clock_{core}", freq)
            if self.profile.core_eff_frequency is not None:
                self._set_sensor(
                    f"core_efffreq_{core}",
                    d[self.profile.lane(self.profile.core_eff_frequency, core)]
                    * 1000)
            self._set_sensor(f"core_power_{core}",
                             d[self.profile.lane(self.profile.core_power, core)])
            self._set_sensor(f"core_voltage_{core}",
                             d[self.profile.lane(self.profile.core_voltage, core)])
            if self.profile.core_fit is not None:
                self._set_sensor(f"core_fit_{core}",
                                 d[self.profile.lane(self.profile.core_fit, core)])
            self._set_sensor(f"core_cc6_{core}",
                             d[self.profile.lane(self.profile.core_cc6, core)])
            self._set_sensor(f"co_{core}", self.current_co[core])
            if self.profile.core_c0 is not None:
                self._set_sensor(f"core_c0_{core}",
                                 d[self.profile.lane(self.profile.core_c0, core)])
                self._set_sensor(f"core_cc1_{core}",
                                 d[self.profile.lane(self.profile.core_cc1, core)])
            else:
                self._set_sensor(f"core_c0_{core}",
                                 100 - d[self.profile.lane(
                                     self.profile.core_cc6, core)])
        if frequencies:
            self._set_summary("frequency", f"{max(frequencies):.0f} MHz")
        else:
            self._set_summary("frequency", "--")

    def update_data(self):
        ok, why = hardware_supported()
        if not ok:
            # update_data runs on a timer; log the refusal once, not every tick.
            if not getattr(self, "_hw_warned", False):
                self._hw_warned = True
                self.log_msg(f"UNVALIDATED HARDWARE: {why}. Telemetry and SMU writes "
                             f"disabled — the offsets would be wrong, not missing.",
                             "ERROR", ACCENT_RED)
            return

        try:
            with open("/sys/kernel/ryzen_smu_drv/pm_table", "rb") as f:
                data = f.read(self.profile.table_size)
                if len(data) == self.profile.table_size:
                    d = struct.unpack(f"<{self.profile.float_count}f", data)
                    # Limit snapshots feed the write dialogs; unmapped limits
                    # stay None so the dialogs refuse to open with no defaults.
                    ppt_idx = self.profile.gidx("ppt_limit")
                    tdc_idx = self.profile.gidx("tdc_limit")
                    edc_idx = self.profile.gidx("edc_limit")
                    self.current_ppt = d[ppt_idx] if ppt_idx is not None else None
                    self.current_tdc = d[tdc_idx] if tdc_idx is not None else None
                    self.current_edc = d[edc_idx] if edc_idx is not None else None
                    self._update_sensor_tree(d)

        except FileNotFoundError:
            pass
        except Exception as e:
            pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = GNRMaster()
    w.show()
    sys.exit(app.exec())
