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
        self.current_co = self.load_co_config()
        self.core_cpu_ids = physical_core_cpu_ids()

        self._build_interface()
        self._restore_window_size()

        self.log_msg(
            "Dashboard initialized. Listening to kernel logs...", "STATUS", ACCENT_GREEN
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
        caption = QLabel(subtitle)
        caption.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED};")
        layout.addWidget(heading)
        layout.addWidget(caption)
        return page, layout

    def _build_overview_page(self):
        page, layout = self._page(
            "Sensors Status", f"{self.profile.name if self.profile else 'Unsupported CPU'} · live telemetry"
        )
        toolbar = QHBoxLayout()
        hint = QLabel("Values accumulate while this window stays open.  Experimental fields keep their PM-table index.")
        hint.setStyleSheet(f"font-size: 10px; color: {TEXT_MUTED};")
        self.reset_stats_button = QPushButton("Reset min/max")
        self.reset_stats_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_stats_button.setStyleSheet(self._control_button_style())
        self.reset_stats_button.clicked.connect(self._reset_sensor_stats)
        refresh_label = QLabel("Refresh")
        refresh_label.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED};")
        self.update_rate_input = QSpinBox()
        self.update_rate_input.setRange(100, 10000)
        self.update_rate_input.setSingleStep(100)
        self.update_rate_input.setSuffix(" ms")
        self.update_rate_input.setValue(self.sensor_update_ms)
        self.update_rate_input.setToolTip("Telemetry refresh interval. Saved in the GUI configuration.")
        self.update_rate_input.setStyleSheet(
            f"background: {BG_PANEL}; border: 1px solid {BORDER}; padding: 4px 6px;"
        )
        self.update_rate_input.valueChanged.connect(self._set_update_interval)
        toolbar.addWidget(hint)
        toolbar.addStretch()
        toolbar.addWidget(refresh_label)
        toolbar.addWidget(self.update_rate_input)
        toolbar.addWidget(self.reset_stats_button)
        layout.addLayout(toolbar)

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
        header.sectionMoved.connect(self._queue_sensor_preferences)
        header.sectionResized.connect(self._queue_sensor_preferences)
        self.sensor_items = {}
        self.sensor_units = {}
        self.sensor_stats = {}
        self._build_sensor_tree()
        layout.addWidget(self.sensor_tree)
        return page

    def _add_sensor_group(self, parent, label, expanded=True):
        item = QTreeWidgetItem([label, "", "", "", ""])
        item.setFirstColumnSpanned(True)
        item.setExpanded(expanded)
        item.setForeground(0, QColor("#f8fafc"))
        font = item.font(0)
        font.setBold(True)
        item.setFont(0, font)
        parent.addChild(item)
        return item

    def _add_sensor(self, parent, key, label, unit, tooltip=""):
        item = QTreeWidgetItem([label, "--", "--", "--", "--"])
        for column in range(1, 5):
            item.setTextAlignment(
                column,
                int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
            )
        item.setBackground(1, QColor(BG_TREE_CURRENT))
        item.setForeground(1, QColor("#d6e6ff"))
        if tooltip:
            item.setToolTip(0, tooltip)
        parent.addChild(item)
        self.sensor_items[key] = item
        self.sensor_units[key] = unit

    def _build_sensor_tree(self):
        cpu_name = self.profile.name if self.profile else "Unsupported CPU"
        root = QTreeWidgetItem([f"CPU [#0]: {cpu_name} · Enhanced", "", "", "", ""])
        root.setFirstColumnSpanned(True)
        root.setExpanded(True)
        root.setForeground(0, QColor("#ffffff"))
        root_font = root.font(0)
        root_font.setBold(True)
        root.setFont(0, root_font)
        self.sensor_tree.addTopLevelItem(root)

        temperatures = self._add_sensor_group(root, "Temperatures")
        self._add_sensor(temperatures, "tctl", "CPU (Tctl/Tdie)", "°C")
        for ccd in range(max(1, (self.core_count + 7) // 8)):
            self._add_sensor(temperatures, f"tccd{ccd}", f"CPU CCD{ccd + 1} (k10temp)", "°C")
        core_temps = self._add_sensor_group(temperatures, "Core Temperatures")
        for core in range(self.core_count):
            self._add_sensor(core_temps, f"core_temp_{core}",
                             f"Core {core} (CCD{core // 8 + 1})", "°C")

        l3 = self._add_sensor_group(root, "Experimental L3 / CCD candidates")
        l3.setToolTip(0, "Low-confidence PM-table candidates; raw index remains visible.")
        if self.profile and self.profile.l3_count:
            for ccd in range(self.profile.l3_count):
                self._add_sensor(l3, f"l3_temp_{ccd}",
                                 f"L3 temperature? (CCD{ccd + 1}) · d[{self.profile.l3_temperature + ccd}]",
                                 "°C", "Experimental PM-table candidate")
                self._add_sensor(l3, f"l3_logic_{ccd}",
                                 f"L3 logic power? (CCD{ccd + 1}) · d[{self.profile.l3_logic_power + ccd}]",
                                 "W", "Experimental PM-table candidate")
                self._add_sensor(l3, f"l3_vddm_{ccd}",
                                 f"L3 VDDM power? (CCD{ccd + 1}) · d[{self.profile.l3_vddm_power + ccd}]",
                                 "W", "Experimental PM-table candidate")
        else:
            l3.setText(0, "Experimental L3 / CCD candidates (not mapped for this profile)")

        limits = self._add_sensor_group(root, "Limits & current")
        self._add_sensor(limits, "ppt", "CPU PPT", "W")
        self._add_sensor(limits, "ppt_limit", "CPU PPT Limit", "W")
        self._add_sensor(limits, "tdc", "CPU TDC", "A")
        self._add_sensor(limits, "tdc_limit", "CPU TDC Limit", "A")
        self._add_sensor(limits, "edc_limit", "CPU EDC Limit", "A")
        self._add_sensor(limits, "thermal_limit", "Thermal Limit", "°C")

        power = self._add_sensor_group(root, "Power")
        for key, label in (
            ("socket_power", "CPU Socket Power"), ("cpu_power", "CPU Core Power"),
            ("core_power", "Core Power Sum"), ("soc_power", "CPU SoC Power"),
            ("vddio_power", "VDDIO MEM Power"), ("vdd18_power", "VDD18 Power"),
        ):
            self._add_sensor(power, key, label, "W")
        core_power = self._add_sensor_group(power, "Core Powers")
        for core in range(self.core_count):
            self._add_sensor(core_power, f"core_power_{core}",
                             f"Core {core} (CCD{core // 8 + 1})", "W")

        clocks = self._add_sensor_group(root, "Clocks")
        for key, label in (("fclk", "Infinity Fabric Clock (FCLK)"),
                           ("uclk", "Memory Controller Clock (UCLK)"),
                           ("mclk", "Memory Clock (MCLK)")):
            self._add_sensor(clocks, key, label, "MHz")
        core_clocks = self._add_sensor_group(clocks, "Core Clocks", expanded=True)
        for core in range(self.core_count):
            self._add_sensor(core_clocks, f"core_clock_{core}",
                             f"Core {core} (CCD{core // 8 + 1})", "MHz",
                             "Live frequency from Linux cpufreq on the 9950X3D")

        voltages = self._add_sensor_group(root, "Voltages")
        for key, label in (("vcore_peak", "Vcore Peak"), ("vcore_avg", "Vcore Average"),
                           ("vsoc", "VDDCR_SOC"), ("vdd_misc", "VDD_MISC"),
                           ("vddg_iod", "CLDO_VDDG_IOD"), ("vddg_ccd", "CLDO_VDDG_CCD"),
                           ("vddp", "CLDO_VDDP"), ("vid", "CPU VID"),
                           ("vid_limit", "VID Limit")):
            self._add_sensor(voltages, key, label, "V")
        core_voltages = self._add_sensor_group(voltages, "Core Voltages")
        for core in range(self.core_count):
            self._add_sensor(core_voltages, f"core_voltage_{core}",
                             f"Core {core} (CCD{core // 8 + 1})", "V")

        residency = self._add_sensor_group(root, "Core residency & FIT")
        for core in range(self.core_count):
            ccd = core // 8 + 1
            self._add_sensor(residency, f"core_fit_{core}", f"Core {core} FIT (CCD{ccd})", "")
            self._add_sensor(residency, f"core_c0_{core}", f"Core {core} C0 residency (CCD{ccd})", "%")
            self._add_sensor(residency, f"core_cc1_{core}", f"Core {core} CC1 residency (CCD{ccd})", "%")
            self._add_sensor(residency, f"core_cc6_{core}", f"Core {core} CC6 residency (CCD{ccd})", "%")
        co_config = self._add_sensor_group(root, "Configured Curve Optimizer")
        for core in range(self.core_count):
            self._add_sensor(co_config, f"co_{core}", f"Core {core} (CCD{core // 8 + 1})", "int")
        for item in (root, temperatures, core_temps, l3, limits, power, core_power,
                     clocks, core_clocks, voltages, core_voltages, residency, co_config):
            self.sensor_tree.expandItem(item)

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
            return data if isinstance(data, dict) else {}
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
        self._save_config({
            "sensor_header_state": header_state,
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

    def load_co_config(self):
        try:
            offsets = self.config.get("co_offsets", [])
            return (offsets + [0] * self.core_count)[:self.core_count]
        except Exception:
            pass
        return [0] * self.core_count

    def save_co_config(self):
        self._save_config({"co_offsets": self.current_co})

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
                self.save_co_config()
                self.log_msg(
                    f"CO offsets applied and cached for cores {applied}: "
                    f"{self.current_co}", "STATUS", ACCENT_GREEN,
                )

    def _read_pm_limits(self):
        # Fallback comes from the profile, not from a copy of the 9800X3D's numbers:
        # this feeds the write dialog's defaults, and handing a 9950X3D 162/120/180
        # because its table read failed is the kind of wrong default that gets
        # written back. Unvalidated hardware has no profile and so gets nothing.
        if not hardware_supported()[0] or self.profile is None:
            return None
        stock = (float(self.profile.stock_ppt), float(self.profile.stock_tdc),
                 float(self.profile.stock_edc))
        try:
            with open("/sys/kernel/ryzen_smu_drv/pm_table", "rb") as f:
                d = struct.unpack(f"<{self.profile.float_count}f",
                                  f.read(self.profile.table_size))
            # PPT=d[2], TDC=d[8] (0x020), EDC=d[63] (0x0FC). Corrected 2026-07-30:
            # this used to return d[10] as TDC — that offset is the thermal limit
            # in °C (88), so the write dialog pre-filled TDC with 88 A and EDC
            # with 120 A (the real TDC limit).
            return d[2], d[8], d[63]
        except Exception:
            return stock

    def _core_frequency_mhz(self, table, core):
        """Use the PM-table frequency where mapped, otherwise Linux cpufreq."""
        if self.profile.core_frequency is not None:
            return table[self.profile.core_frequency + core] * 1000
        if core >= len(self.core_cpu_ids):
            return None
        path = (f"/sys/devices/system/cpu/cpu{self.core_cpu_ids[core]}/"
                "cpufreq/scaling_cur_freq")
        try:
            with open(path) as f:
                return float(f.read()) / 1000
        except (OSError, ValueError):
            return None

    def _update_sensor_tree(self, d):
        vcores = [d[self.profile.core_voltage + i] for i in range(self.core_count)]
        self._set_sensor("tctl", d[11])
        self._set_sensor("ppt", d[3])
        self._set_sensor("ppt_limit", d[2])
        self._set_sensor("tdc", d[9])
        self._set_sensor("tdc_limit", d[8])
        self._set_sensor("edc_limit", d[63])
        self._set_sensor("thermal_limit", d[10])
        self._set_sensor("socket_power", d[26] if self.profile.pm_version == 0x620205 else d[20])
        self._set_sensor("cpu_power", d[20])
        self._set_sensor("core_power", sum(d[self.profile.core_power + i]
                                            for i in range(self.core_count)))
        self._set_sensor("soc_power", d[21])
        self._set_sensor("vddio_power", d[22])
        self._set_sensor("vdd18_power", d[23])
        self._set_sensor("fclk", d[71])
        self._set_sensor("uclk", d[75])
        self._set_sensor("mclk", d[79])
        self._set_sensor("vcore_peak", max(vcores))
        self._set_sensor("vcore_avg", sum(vcores) / self.core_count)
        self._set_sensor("vsoc", d[83])
        self._set_sensor("vdd_misc", d[58])
        self._set_sensor("vddg_iod", d[259])
        self._set_sensor("vddg_ccd", d[261])
        self._set_sensor("vddp", d[269])
        self._set_sensor("vid", d[19])
        self._set_sensor("vid_limit", d[18])

        ccd_count = max(1, (self.core_count + 7) // 8)
        for ccd in range(ccd_count):
            self._set_sensor(f"tccd{ccd}", read_hwmon_temperature(f"Tccd{ccd + 1}"))
        if self.profile.l3_count:
            for ccd in range(self.profile.l3_count):
                self._set_sensor(f"l3_temp_{ccd}", d[self.profile.l3_temperature + ccd])
                self._set_sensor(f"l3_logic_{ccd}", d[self.profile.l3_logic_power + ccd])
                self._set_sensor(f"l3_vddm_{ccd}", d[self.profile.l3_vddm_power + ccd])

        for core in range(self.core_count):
            freq = self._core_frequency_mhz(d, core)
            self._set_sensor(f"core_temp_{core}", d[self.profile.core_temp + core])
            self._set_sensor(f"core_clock_{core}", freq)
            self._set_sensor(f"core_power_{core}", d[self.profile.core_power + core])
            self._set_sensor(f"core_voltage_{core}", d[self.profile.core_voltage + core])
            self._set_sensor(f"core_fit_{core}", d[self.profile.core_fit + core])
            self._set_sensor(f"core_cc6_{core}", d[self.profile.core_cc6 + core])
            self._set_sensor(f"co_{core}", self.current_co[core])
            if self.profile.core_c0 is not None:
                self._set_sensor(f"core_c0_{core}", d[self.profile.core_c0 + core])
                self._set_sensor(f"core_cc1_{core}", d[self.profile.core_cc1 + core])
            else:
                self._set_sensor(f"core_c0_{core}", None)
                self._set_sensor(f"core_cc1_{core}", None)

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
                    # Zone 0x000 is the Zen (LIMIT, VALUE) pair layout — corrected
                    # 2026-07-30. d[8] is TDC (not EDC), d[10] is the thermal limit
                    # in °C (not TDC in A), and EDC's limit lives at d[63].
                    self.current_ppt = d[2]
                    self.current_edc = d[63]
                    self.current_tdc = d[8]
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
