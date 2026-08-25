import sys
import struct
import collections
import subprocess
import json
import os
import glob
import pyqtgraph as pg
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
BG_MAIN = "#121826"
BG_PANEL = "#1a2332"
BG_INNER = "#232d3f"
BORDER = "#3b4758"
TEXT_MAIN = "#f8fafc"
TEXT_MUTED = "#8b9bb4"
ACCENT_RED = "#ef4444"
ACCENT_ORANGE = "#f97316"
ACCENT_GREEN = "#22c55e"
ACCENT_PURPLE = "#a855f7"
ACCENT_CYAN = "#22d3ee"


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


# ================= COMPOSANTS UI =================
class Gauge(QWidget):
    def __init__(self, top_text, main_text, bottom_text, max_val, color):
        super().__init__()
        (
            self.val,
            self.max,
            self.color,
            self.top_text,
            self.main_text,
            self.bottom_text,
        ) = 0, max_val, color, top_text, main_text, bottom_text
        self.setFixedSize(130, 130)

    def setValue(self, val, main_text=None, bottom_text=None):
        self.val = val
        if main_text:
            self.main_text = main_text
        if bottom_text:
            self.bottom_text = bottom_text
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(BORDER), 6))
        p.drawArc(15, 15, 100, 100, -30 * 16, 240 * 16)
        span_angle = (
            int((min(self.val, self.max) / self.max) * 240 * 16) if self.max > 0 else 0
        )
        p.setPen(QPen(QColor(self.color), 6))
        p.drawArc(15, 15, 100, 100, 210 * 16, -span_angle)
        p.setFont(QFont("Segoe UI", 8))
        p.setPen(QColor(TEXT_MAIN))
        if self.top_text:
            p.drawText(0, 35, 130, 20, Qt.AlignmentFlag.AlignCenter, self.top_text)
        p.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        p.setPen(QColor(self.color))
        p.drawText(0, 55, 130, 30, Qt.AlignmentFlag.AlignCenter, self.main_text)
        p.setFont(QFont("Segoe UI", 8))
        p.setPen(QColor(TEXT_MUTED))
        p.drawText(0, 90, 130, 20, Qt.AlignmentFlag.AlignCenter, self.bottom_text)


class MetricCard(QFrame):
    def __init__(self, title, value="--", detail="", color=ACCENT_ORANGE):
        super().__init__()
        self.setObjectName("metricCard")
        self.setMinimumHeight(112)
        self.setStyleSheet(
            f"QFrame#metricCard {{ background: {BG_PANEL}; border: 1px solid {BORDER}; "
            "border-radius: 9px; } QLabel { border: none; background: transparent; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 11)
        layout.setSpacing(4)
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; font-weight: 600;"
        )
        self.value_lbl = QLabel(value)
        self.value_lbl.setStyleSheet(
            f"color: {color}; font-size: 23px; font-weight: 700;"
        )
        self.detail_lbl = QLabel(detail)
        self.detail_lbl.setWordWrap(True)
        self.detail_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        layout.addWidget(self.title_lbl)
        layout.addWidget(self.value_lbl)
        layout.addWidget(self.detail_lbl)
        layout.addStretch()

    def set_value(self, value, detail=None):
        self.value_lbl.setText(value)
        if detail is not None:
            self.detail_lbl.setText(detail)


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


class CoreWidget(QFrame):
    def __init__(self, core_id):
        super().__init__()
        self.setStyleSheet(
            f"background-color: {BG_PANEL}; border: 1px solid {BORDER}; border-radius: 6px;"
        )
        self.setMinimumHeight(205)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(0)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title = QLabel(f"⛛ Core [{core_id}]")
        title.setStyleSheet("color: #8b9bb4; border: none; font-size: 10px;")
        self.co_lbl = QLabel("CO: 0")
        self.co_lbl.setStyleSheet(
            f"color: {ACCENT_PURPLE}; border: none; font-size: 9px; font-weight: bold;"
        )
        title_row.addWidget(title)
        title_row.addWidget(self.co_lbl, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(title_row)
        self.freq_lbl = QLabel("0.00 MHz")
        self.freq_lbl.setStyleSheet(
            f"color: {ACCENT_RED}; border: none; font-size: 18px; font-weight: bold; margin-top: 2px;"
        )
        layout.addWidget(self.freq_lbl)
        self.max_lbl = QLabel("Max: 0.00 MHz")
        self.max_lbl.setStyleSheet("color: #8b9bb4; border: none; font-size: 10px;")
        layout.addWidget(self.max_lbl)
        vt_layout = QHBoxLayout()
        vt_layout.setContentsMargins(0, 5, 0, 5)
        self.volt_lbl = QLabel("⚡ 0.000 V")
        self.volt_lbl.setStyleSheet("color: #cbd5e1; border: none; font-size: 11px;")
        self.temp_lbl = QLabel("🌡 0.00 C")
        self.temp_lbl.setStyleSheet("color: #cbd5e1; border: none; font-size: 11px;")
        vt_layout.addWidget(self.volt_lbl)
        vt_layout.addWidget(self.temp_lbl)
        layout.addLayout(vt_layout)
        self.pwr_lbl = QLabel("0.00 W")
        self.pwr_lbl.setStyleSheet("color: #fbbf24; border: none; font-size: 11px;")
        layout.addWidget(self.pwr_lbl)
        self.state_lbl = QLabel("FIT -- · C-state --")
        self.state_lbl.setStyleSheet("color: #94a3b8; border: none; font-size: 9px;")
        self.state_lbl.setWordWrap(True)
        layout.addWidget(self.state_lbl)
        load_lbl = QLabel("Load")
        load_lbl.setStyleSheet("color: #64748b; border: none; font-size: 8px;")
        layout.addWidget(load_lbl)
        graph_layout = QHBoxLayout()
        graph_layout.setContentsMargins(0, 0, 0, 0)
        graph_layout.setSpacing(2)
        zero_lbl = QLabel("0%")
        zero_lbl.setStyleSheet("color: #64748b; border: none; font-size: 8px;")
        zero_lbl.setAlignment(Qt.AlignmentFlag.AlignBottom)
        graph_layout.addWidget(zero_lbl)
        self.bar_chart = pg.PlotWidget()
        self.bar_chart.setFixedHeight(30)
        self.bar_chart.setBackground(None)
        self.bar_chart.hideAxis("left")
        self.bar_chart.hideAxis("bottom")
        self.bar_chart.setStyleSheet("border: none;")
        self.bar_chart.hideButtons()
        self.bar_chart.setYRange(0, 100)
        self.bg = pg.BarGraphItem(
            x=list(range(20)), height=[0] * 20, width=0.8, brush=ACCENT_ORANGE, pen=None
        )
        self.bar_chart.addItem(self.bg)
        graph_layout.addWidget(self.bar_chart, 1)
        layout.addLayout(graph_layout)


# ================= APPLICATION PRINCIPALE =================
class GNRMaster(QMainWindow):
    def __init__(self):
        super().__init__()
        self.profile, self.profile_reason = get_hardware_profile()
        self.core_count = self.profile.cores if self.profile else 8
        cpu_name = self.profile.name if self.profile else "Unsupported CPU"
        self.setWindowTitle(f"GNR Master - {cpu_name} Telemetry")
        self.setMinimumSize(1500 if self.core_count > 8 else 1250, 720)
        self.setStyleSheet(
            f"background-color: {BG_MAIN}; color: {TEXT_MAIN}; font-family: 'Segoe UI';"
        )

        # None on unvalidated hardware: no profile means no defensible default, and
        # the write dialog must not be pre-filled with another part's numbers. The
        # guardrails already block writes there, so this only affects what is shown.
        limits = self._read_pm_limits()
        self.current_ppt, self.current_tdc, self.current_edc = limits or (None, None, None)
        self.current_co = self.load_co_config()
        self.core_cpu_ids = physical_core_cpu_ids()
        self.power_history = collections.deque([0.0] * 100, maxlen=100)
        self.temp_history = collections.deque([40.0] * 100, maxlen=100)
        self.core_load_history = [
            collections.deque([0.0] * 20, maxlen=20)
            for _ in range(self.core_count)
        ]
        # d[270] hotspot is very spiky (single reads jump +14 °C at idle) — smooth it
        self.hotspot_history = collections.deque([40.0] * 8, maxlen=8)

        self._build_interface()

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
        self.timer.start(500)

    def _build_interface(self):
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setCentralWidget(root)

        sidebar = QFrame()
        sidebar.setFixedWidth(138)
        sidebar.setStyleSheet(f"background: #0e1420; border-right: 1px solid {BORDER};")
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
            ("Overview", "◫", self._build_overview_page),
            ("Cores", "▦", self._build_cores_page),
            ("System + L3", "◉", self._build_system_page),
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
            "Overview", f"{self.profile.name if self.profile else 'Unsupported CPU'} · live telemetry"
        )
        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.ppt_card = MetricCard("PPT", color=ACCENT_RED)
        self.temp_card = MetricCard("MAX CORE TEMPERATURE", color=ACCENT_ORANGE)
        self.socket_card = MetricCard("SOCKET POWER", color=ACCENT_CYAN)
        self.vcore_card = MetricCard("VCORE", color=ACCENT_PURPLE)
        self.tdc_card = MetricCard("TDC", color=ACCENT_GREEN)
        for card in (self.ppt_card, self.temp_card, self.socket_card,
                     self.vcore_card, self.tdc_card):
            cards.addWidget(card)
        layout.addLayout(cards)

        charts = QHBoxLayout()
        charts.setSpacing(10)
        power_panel, self.main_plot = self._plot_panel("PPT POWER HISTORY")
        self.power_curve = self.main_plot.plot(
            list(range(100)), list(self.power_history),
            pen=pg.mkPen(ACCENT_RED, width=2), fillLevel=0,
            brush=(239, 68, 68, 55),
        )
        temp_panel, self.temp_plot = self._plot_panel("MAX CORE TEMPERATURE")
        self.temp_curve = self.temp_plot.plot(
            list(range(100)), list(self.temp_history),
            pen=pg.mkPen(ACCENT_ORANGE, width=2), fillLevel=0,
            brush=(249, 115, 22, 55),
        )
        charts.addWidget(power_panel)
        charts.addWidget(temp_panel)
        layout.addLayout(charts, 2)

        ccd_row = QHBoxLayout()
        self.ccd_cards = []
        ccd_count = max(1, (self.core_count + 7) // 8)
        for ccd in range(ccd_count):
            card = MetricCard(f"CCD {ccd}", "--", "Waiting for core telemetry", ACCENT_CYAN)
            self.ccd_cards.append(card)
            ccd_row.addWidget(card)
        layout.addLayout(ccd_row)
        return page

    def _plot_panel(self, title):
        panel = TelemetryPanel(title)
        plot = pg.PlotWidget()
        plot.setBackground(None)
        plot.hideButtons()
        plot.enableAutoRange(axis="y", enable=True)
        plot.setLimits(yMin=0)
        plot.getAxis("left").setPen(TEXT_MUTED)
        plot.getAxis("bottom").setPen(TEXT_MUTED)
        plot.showGrid(x=False, y=True, alpha=0.25)
        plot.setStyleSheet("border: none;")
        panel.layout_box.addWidget(plot)
        return panel, plot

    def _build_cores_page(self):
        page, layout = self._page(
            "Core Telemetry", "Per-core frequency, voltage, temperature, power and C-state residency"
        )
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 5, 0)
        body_layout.setSpacing(14)
        self.core_widgets = []
        for ccd in range(max(1, (self.core_count + 7) // 8)):
            section = TelemetryPanel(f"CCD {ccd}", f"Physical cores {ccd * 8}–{min(self.core_count - 1, ccd * 8 + 7)}")
            grid = QGridLayout()
            grid.setSpacing(9)
            start = ccd * 8
            stop = min(self.core_count, start + 8)
            for core in range(start, stop):
                widget = CoreWidget(f"{ccd}-{core - start}")
                self.core_widgets.append(widget)
                local = core - start
                grid.addWidget(widget, local // 4, local % 4)
            section.layout_box.addLayout(grid)
            body_layout.addWidget(section)
        body_layout.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll)
        return page

    def _build_system_page(self):
        page, layout = self._page(
            "System & L3", "Power limits, clocks, rails and experimental CCD/L3 candidates"
        )
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        grid = QGridLayout(body)
        grid.setContentsMargins(0, 0, 5, 0)
        grid.setSpacing(12)

        limits = TelemetryPanel("POWER LIMITS")
        gauge_row = QHBoxLayout()
        stock_tdc = self.profile.stock_tdc if self.profile else 160
        stock_edc = self.profile.stock_edc if self.profile else 225
        self.edc_gauge = Gauge("EDC Limit", "-- A", f"Stock: {stock_edc} A",
                               stock_edc, ACCENT_ORANGE)
        self.tdc_gauge = Gauge("TDC", "-- A", f"Limit: {stock_tdc} A",
                               stock_tdc, ACCENT_RED)
        gauge_row.addWidget(self.edc_gauge)
        gauge_row.addWidget(self.tdc_gauge)
        limits.layout_box.addLayout(gauge_row)
        self.thermal_lbl = limits.add_row("Thermal: --")

        system = TelemetryPanel("CLOCKS & POWER DOMAINS")
        self.clocks_lbl = system.add_row("Clocks: --")
        self.domain_power_lbl = system.add_row("Power domains: --")
        self.misc_lbl = system.add_row("Additional telemetry: --", ACCENT_CYAN)

        rails = TelemetryPanel("VOLTAGE RAILS & FIT")
        self.rail_primary_lbl = rails.add_row("Voltage rails: --")
        self.rail_secondary_lbl = rails.add_row("CLDO rails: --")
        self.fit_vid_lbl = rails.add_row("FIT / VID: --")

        l3 = TelemetryPanel(
            "EXPERIMENTAL L3 / CCD CANDIDATES",
            "Low-confidence PM-table candidates. The d[index] is shown deliberately; "
            "k10temp is an independent reference, not the same measurement.",
        )
        warning = QLabel("⚠  These fields are not yet validated as official L3 telemetry.")
        warning.setWordWrap(True)
        warning.setStyleSheet(
            "color: #fbbf24; background: #3a2a16; border: 1px solid #854d0e; "
            "border-radius: 5px; padding: 8px; font-size: 11px;"
        )
        l3_count = self.profile.l3_count if self.profile else 0
        warning.setVisible(bool(l3_count))
        l3.layout_box.addWidget(warning)
        self.l3_labels = []
        for ccd in range(max(1, l3_count)):
            self.l3_labels.append(l3.add_row(f"CCD {ccd}: unavailable", ACCENT_CYAN))
        if not l3_count:
            self.l3_labels[0].setText("No L3 candidates mapped for this hardware profile")

        grid.addWidget(limits, 0, 0)
        grid.addWidget(system, 0, 1)
        grid.addWidget(rails, 1, 0)
        grid.addWidget(l3, 1, 1)
        grid.setRowStretch(2, 1)
        scroll.setWidget(body)
        layout.addWidget(scroll)
        return page

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
            f"QPushButton:checked {{ background: #2b211d; color: {ACCENT_ORANGE}; "
            "font-weight: 700; border-left: 3px solid #f97316; }}"
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

    def load_co_config(self):
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r") as f:
                    data = json.load(f)
                offsets = data.get("co_offsets", [])
                return (offsets + [0] * self.core_count)[:self.core_count]
        except Exception:
            pass
        return [0] * self.core_count

    def save_co_config(self):
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w") as f:
                json.dump({"co_offsets": self.current_co}, f)
        except Exception:
            pass

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

    def _update_status_panel(self, d):
        self.clocks_lbl.setText(
            f"Clocks  FCLK {d[71]:.0f} · UCLK {d[75]:.0f} · MCLK {d[79]:.0f} MHz"
        )
        if self.profile.pm_version == 0x620205:
            self.thermal_lbl.setText(
                f"Thermal  Tctl {d[11]:.1f} °C · Limit {d[10]:.0f} °C"
            )
            self.domain_power_lbl.setText(
                f"Power  CPU {d[20]:.1f} · SoC {d[21]:.1f} · "
                f"VDDIO {d[22]:.1f} · VDD18 {d[23]:.1f} W"
            )
            self.rail_primary_lbl.setText(
                f"Rails  VSOC {d[83]:.3f} · VDD_MISC {d[58]:.3f} V"
            )
            self.rail_secondary_lbl.setText(
                f"CLDO  VDDG IOD {d[259]:.3f} · CCD {d[261]:.3f} · "
                f"VDDP {d[269]:.3f} V"
            )
            self.fit_vid_lbl.setText(
                f"FIT / VID  FIT {d[16]:.1f} · VID {d[19]:.3f} / "
                f"{d[18]:.3f} V max"
            )
            self.misc_lbl.setText(f"Socket power  {d[26]:.1f} W")
        else:
            self.hotspot_history.append(d[270])
            hotspot = sum(self.hotspot_history) / len(self.hotspot_history)
            self.thermal_lbl.setText(
                f"Thermal  Tctl {d[11]:.1f} °C · Hotspot {hotspot:.1f} °C · "
                f"Limit {d[10]:.0f} °C"
            )
            self.domain_power_lbl.setText(
                f"Power  Package {d[20]:.1f} · SoC {d[21]:.1f} · "
                f"CPU telem {d[22]:.1f} · VDDIO {d[23]:.1f} W"
            )
            self.rail_primary_lbl.setText(
                f"Rails  VSOC {d[83]:.3f} · VDDIO {d[58]:.3f} · "
                f"SoC VID {d[271]:.3f} V"
            )
            self.rail_secondary_lbl.setText(
                f"SoC rails  {d[259]:.3f} / {d[261]:.3f} · "
                f"CPU VID {d[269]:.3f} V"
            )
            self.fit_vid_lbl.setText(
                f"Vcore  Peak {d[18]:.3f} · Avg {d[19]:.3f} V · "
                f"Max boost {d[272]:.3f} GHz"
            )
            self.misc_lbl.setText(
                f"iGPU  {d[107]:.1f} W · {d[108]:.0f} MHz · {d[109]:.0f}%"
            )

    def _update_l3_panel(self, d):
        if not self.profile.l3_count:
            return
        for ccd in range(self.profile.l3_count):
            logic_index = self.profile.l3_logic_power + ccd
            vddm_index = self.profile.l3_vddm_power + ccd
            temp_index = self.profile.l3_temperature + ccd
            sensor = read_hwmon_temperature(f"Tccd{ccd + 1}")
            sensor_text = f"{sensor:.1f} °C" if sensor is not None else "unavailable"
            self.l3_labels[ccd].setText(
                f"CCD {ccd}\n"
                f"L3 temperature?  {d[temp_index]:.2f} °C  · d[{temp_index}]\n"
                f"L3 logic power?  {d[logic_index]:.3f} W  · d[{logic_index}]\n"
                f"L3 VDDM power?  {d[vddm_index]:.3f} W  · d[{vddm_index}]\n"
                f"Independent k10temp Tccd{ccd + 1}:  {sensor_text}"
            )

    def _update_ccd_cards(self, d, frequencies, loads):
        for ccd, card in enumerate(self.ccd_cards):
            start = ccd * 8
            stop = min(self.core_count, start + 8)
            temps = [d[self.profile.core_temp + i] for i in range(start, stop)]
            powers = [d[self.profile.core_power + i] for i in range(start, stop)]
            valid_freqs = [value for value in frequencies[start:stop]
                           if value is not None]
            avg_freq = sum(valid_freqs) / len(valid_freqs) if valid_freqs else 0
            avg_load = sum(loads[start:stop]) / max(1, stop - start)
            card.set_value(
                f"{max(temps):.1f} °C · {avg_freq:.0f} MHz",
                f"Σ core power {sum(powers):.2f} W  ·  average C0/load {avg_load:.0f}%",
            )

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
                    pkg_pwr = d[3]  # PPT value: the figure the PPT limit applies to

                    ppt_percent = (pkg_pwr / self.current_ppt * 100
                                   if self.current_ppt > 0 else 0)
                    self.ppt_card.set_value(
                        f"{pkg_pwr:.1f} / {self.current_ppt:.0f} W",
                        f"{ppt_percent:.0f}% of configured PPT",
                    )
                    self.edc_gauge.setValue(
                        self.current_edc,
                        main_text=f"{self.current_edc:.0f} A",
                        bottom_text=f"Stock: {self.profile.stock_edc} A",
                    )
                    self.tdc_gauge.setValue(
                        d[9],
                        main_text=f"{d[9]:.1f} A",
                        bottom_text=f"Limit: {self.current_tdc:.0f} A",
                    )
                    self.power_history.append(pkg_pwr)
                    self.power_curve.setData(list(range(100)), list(self.power_history))

                    vcores = [d[self.profile.core_voltage + i]
                              for i in range(self.core_count)]
                    vcore_peak = max(vcores)
                    vcore_avg = sum(vcores) / self.core_count
                    self.vcore_card.set_value(
                        f"{vcore_peak:.3f} V", f"Peak · average {vcore_avg:.3f} V"
                    )

                    self._update_status_panel(d)
                    self._update_l3_panel(d)
                    # Max core temp history
                    max_temp = max(d[self.profile.core_temp + i]
                                   for i in range(self.core_count))
                    self.temp_card.set_value(
                        f"{max_temp:.1f} °C", f"Tctl {d[11]:.1f} °C · limit {d[10]:.0f} °C"
                    )
                    socket_power = d[26] if self.profile.pm_version == 0x620205 else d[20]
                    self.socket_card.set_value(
                        f"{socket_power:.1f} W", "PM-table package/socket reading"
                    )
                    tdc_percent = (d[9] / self.current_tdc * 100
                                   if self.current_tdc > 0 else 0)
                    self.tdc_card.set_value(
                        f"{d[9]:.1f} / {self.current_tdc:.0f} A",
                        f"{tdc_percent:.0f}% of configured TDC",
                    )
                    self.temp_history.append(max_temp)
                    self.temp_curve.setData(list(range(100)), list(self.temp_history))

                    frequencies = []
                    loads = []
                    for i in range(self.core_count):
                        volt = d[self.profile.core_voltage + i]
                        temp = d[self.profile.core_temp + i]
                        freq = self._core_frequency_mhz(d, i)
                        max_freq = d[self.profile.core_boost_limit + i] * 1000
                        power = d[self.profile.core_power + i]
                        fit = d[self.profile.core_fit + i]
                        cc6 = d[self.profile.core_cc6 + i]
                        if self.profile.core_c0 is not None:
                            c0 = d[self.profile.core_c0 + i]
                            cc1 = d[self.profile.core_cc1 + i]
                            load = max(0, min(100, c0))
                            activity = d[self.profile.core_activity + i]
                            states = (f"FIT {fit:.1f} · Act? {activity:.2f}\n"
                                      f"C0 {c0:.0f}% · C1 {cc1:.0f}% · C6 {cc6:.0f}%")
                        else:
                            load = max(0, min(100, 100 - cc6))
                            activity = d[self.profile.core_activity + i]
                            states = (f"FIT {fit:.1f} · Light? {activity:.2f} · "
                                      f"C6 {cc6:.0f}%")
                        frequencies.append(freq)
                        loads.append(load)
                        cw = self.core_widgets[i]
                        cw.freq_lbl.setText(
                            f"{freq:.0f} MHz" if freq is not None else "-- MHz"
                        )
                        if self.profile.core_frequency is None:
                            cw.freq_lbl.setToolTip("Live frequency from Linux cpufreq")
                        limit_label = ("Limit" if self.profile.boost_limit_confident
                                       else "Boost?")
                        cw.max_lbl.setText(f"{limit_label}: {max_freq:.0f} MHz")
                        if not self.profile.boost_limit_confident:
                            cw.max_lbl.setToolTip(
                                "PM-table boost-limit candidate; not independently confirmed"
                            )
                        cw.volt_lbl.setText(f"⚡ {volt:.3f} V")
                        cw.temp_lbl.setText(f"🌡 {temp:.1f} °C")
                        cw.co_lbl.setText(f"CO: {self.current_co[i]}")
                        cw.pwr_lbl.setText(f"Power: {power:.2f} W")
                        cw.state_lbl.setText(states)
                        cw.state_lbl.setToolTip(
                            "Act?/Light? marks a lower-confidence PM-table metric"
                        )

                        self.core_load_history[i].append(load)
                        cw.bg.setOpts(height=list(self.core_load_history[i]))

                    self._update_ccd_cards(d, frequencies, loads)

        except FileNotFoundError:
            pass
        except Exception as e:
            pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = GNRMaster()
    w.show()
    sys.exit(app.exec())
