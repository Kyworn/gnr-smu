import sys
import struct
import collections
import subprocess
import json
import os
import pyqtgraph as pg
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

CONFIG_PATH = "/home/zorko/.config/gnr_master.json"

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

# --- MAGIC FUNCTION FOR LARGE ICONS ---
def create_text_icon(char, color, size=42):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.setPen(QColor(color))
    p.setFont(QFont("Segoe UI", int(size * 0.7)))
    p.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, char)
    p.end()
    return QIcon(pixmap)

# ================= THREAD : REAL-TIME KERNEL LOGS =================
class KernelLogWorker(QThread):
    log_signal = pyqtSignal(str)
    def run(self):
        try:
            process = subprocess.Popen(['dmesg', '-w'], stdout=subprocess.PIPE, text=True)
            for line in iter(process.stdout.readline, ''):
                if 'gnr_smu' in line or 'ryzen_smu' in line:
                    clean_line = line.split("] ", 1)[-1].strip() if "] " in line else line.strip()
                    self.log_signal.emit(clean_line)
        except Exception:
            pass

# ================= CONTROL DIALOGS =================
class PowerControlDialog(QDialog):
    def __init__(self, cur_ppt, cur_tdc, cur_edc, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Power & Thermal Controls")
        self.setStyleSheet(f"background-color: {BG_MAIN}; color: {TEXT_MAIN}; font-family: 'Segoe UI';")
        self.setFixedSize(300, 250)
        layout = QVBoxLayout(self)
        self.inputs = {}
        configs = [("PPT", 250, "W", cur_ppt), ("TDC", 200, "A", cur_tdc), ("EDC", 250, "A", cur_edc)]
        
        for name, max_val, unit, current_val in configs:
            row = QHBoxLayout()
            lbl = QLabel(name); lbl.setStyleSheet("font-weight: bold; width: 40px;")
            spin = QDoubleSpinBox(); spin.setRange(0, max_val); spin.setSuffix(f" {unit}")
            spin.setStyleSheet(f"background-color: {BG_PANEL}; border: 1px solid {BORDER}; padding: 5px;")
            spin.setValue(current_val)
            self.inputs[name] = spin
            row.addWidget(lbl); row.addWidget(spin); layout.addLayout(row)
            
        btn_apply = QPushButton("Apply Limits (MP1)")
        btn_apply.setStyleSheet(f"background-color: {ACCENT_RED}; color: white; border-radius: 4px; padding: 8px; font-weight: bold;")
        btn_apply.clicked.connect(self.accept)
        layout.addStretch(); layout.addWidget(btn_apply)

class CoreControlDialog(QDialog):
    def __init__(self, current_co_offsets, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Curve Optimizer (CO)")
        self.setStyleSheet(f"background-color: {BG_MAIN}; color: {TEXT_MAIN}; font-family: 'Segoe UI';")
        self.setFixedSize(350, 400)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Set Curve Optimizer Offsets per Core:"))
        self.spins = []
        grid = QGridLayout()
        for i in range(8):
            lbl = QLabel(f"Core {i}:")
            spin = QSpinBox(); spin.setRange(-50, 20)
            spin.setStyleSheet(f"background-color: {BG_PANEL}; border: 1px solid {BORDER}; padding: 3px;")
            spin.setValue(current_co_offsets[i])
            self.spins.append(spin)
            grid.addWidget(lbl, i//2, (i%2)*2)
            grid.addWidget(spin, i//2, (i%2)*2 + 1)
            
        layout.addLayout(grid)
        btn_apply = QPushButton("Apply Curve Optimizer")
        btn_apply.setStyleSheet(f"background-color: {ACCENT_ORANGE}; color: white; border-radius: 4px; padding: 8px; font-weight: bold;")
        btn_apply.clicked.connect(self.accept)
        layout.addStretch(); layout.addWidget(btn_apply)

# ================= COMPOSANTS UI =================
class Gauge(QWidget):
    def __init__(self, top_text, main_text, bottom_text, max_val, color):
        super().__init__(); self.val, self.max, self.color, self.top_text, self.main_text, self.bottom_text = 0, max_val, color, top_text, main_text, bottom_text; self.setFixedSize(130, 130)
    def setValue(self, val, main_text=None, bottom_text=None):
        self.val = val; 
        if main_text: self.main_text = main_text
        if bottom_text: self.bottom_text = bottom_text
        self.update()
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.setPen(QPen(QColor(BORDER), 6)); p.drawArc(15, 15, 100, 100, -30 * 16, 240 * 16)
        span_angle = int((min(self.val, self.max) / self.max) * 240 * 16) if self.max > 0 else 0
        p.setPen(QPen(QColor(self.color), 6)); p.drawArc(15, 15, 100, 100, 210 * 16, -span_angle)
        p.setFont(QFont("Segoe UI", 8)); p.setPen(QColor(TEXT_MAIN))
        if self.top_text: p.drawText(0, 35, 130, 20, Qt.AlignmentFlag.AlignCenter, self.top_text)
        p.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold)); p.setPen(QColor(self.color))
        p.drawText(0, 55, 130, 30, Qt.AlignmentFlag.AlignCenter, self.main_text)
        p.setFont(QFont("Segoe UI", 8)); p.setPen(QColor(TEXT_MUTED)); p.drawText(0, 90, 130, 20, Qt.AlignmentFlag.AlignCenter, self.bottom_text)

class CoreWidget(QFrame):
    def __init__(self, core_id):
        super().__init__(); self.setStyleSheet(f"background-color: {BG_PANEL}; border: 1px solid {BORDER}; border-radius: 6px;"); layout = QVBoxLayout(self); layout.setContentsMargins(10, 8, 10, 8); layout.setSpacing(0)
        title = QLabel(f"⛛ Core [{core_id}]"); title.setStyleSheet("color: #8b9bb4; border: none; font-size: 10px;"); layout.addWidget(title)
        self.freq_lbl = QLabel("0.00 MHz"); self.freq_lbl.setStyleSheet(f"color: {ACCENT_RED}; border: none; font-size: 18px; font-weight: bold; margin-top: 2px;"); layout.addWidget(self.freq_lbl)
        self.max_lbl = QLabel("Max: 0.00 MHz"); self.max_lbl.setStyleSheet("color: #8b9bb4; border: none; font-size: 10px;")
        self.co_lbl = QLabel("CO: 0"); self.co_lbl.setStyleSheet(f"color: {ACCENT_PURPLE}; border: none; font-size: 10px; font-weight: bold;")
        h_lyt = QHBoxLayout(); h_lyt.setContentsMargins(0,0,0,0); h_lyt.addWidget(self.max_lbl); h_lyt.addWidget(self.co_lbl, alignment=Qt.AlignmentFlag.AlignRight); layout.addLayout(h_lyt)
        vt_layout = QHBoxLayout(); vt_layout.setContentsMargins(0, 5, 0, 5); self.volt_lbl = QLabel("⚡ 0.000 V"); self.volt_lbl.setStyleSheet("color: #cbd5e1; border: none; font-size: 10px;"); self.temp_lbl = QLabel("🌡 0.00 C"); self.temp_lbl.setStyleSheet("color: #cbd5e1; border: none; font-size: 10px;")
        vt_layout.addWidget(self.volt_lbl); vt_layout.addWidget(self.temp_lbl); layout.addLayout(vt_layout)
        load_lbl = QLabel("Load"); load_lbl.setStyleSheet("color: #64748b; border: none; font-size: 8px;"); layout.addWidget(load_lbl)
        graph_layout = QHBoxLayout(); graph_layout.setContentsMargins(0,0,0,0); graph_layout.setSpacing(2); zero_lbl = QLabel("0%"); zero_lbl.setStyleSheet("color: #64748b; border: none; font-size: 8px;"); zero_lbl.setAlignment(Qt.AlignmentFlag.AlignBottom); graph_layout.addWidget(zero_lbl)
        self.bar_chart = pg.PlotWidget(); self.bar_chart.setFixedHeight(30); self.bar_chart.setBackground(None); self.bar_chart.hideAxis('left'); self.bar_chart.hideAxis('bottom'); self.bar_chart.setStyleSheet("border: none;"); self.bar_chart.hideButtons(); self.bar_chart.setYRange(0, 100)
        self.bg = pg.BarGraphItem(x=list(range(20)), height=[0]*20, width=0.8, brush=ACCENT_ORANGE, pen=None); self.bar_chart.addItem(self.bg); graph_layout.addWidget(self.bar_chart, 1); layout.addLayout(graph_layout)

# ================= APPLICATION PRINCIPALE =================
class GNRMaster(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GNR Master - AMD Ryzen 7 9800X3D Telemetry")
        self.setMinimumSize(1250, 720)
        self.setStyleSheet(f"background-color: {BG_MAIN}; color: {TEXT_MAIN}; font-family: 'Segoe UI';")
        
        self.current_ppt, self.current_tdc, self.current_edc = 162.0, 125.0, 180.0
        self.current_co = self.load_co_config()
        self.power_history = collections.deque([0.0]*100, maxlen=100)
        self.core_load_history = [collections.deque([0.0]*20, maxlen=20) for _ in range(8)]
        
        main_widget = QWidget(); main_layout = QHBoxLayout(main_widget); main_layout.setContentsMargins(0, 0, 0, 0); main_layout.setSpacing(0); self.setCentralWidget(main_widget)
        sidebar = QFrame(); sidebar.setFixedWidth(90); sidebar.setStyleSheet(f"background-color: {BG_MAIN}; border-right: 1px solid {BG_MAIN};"); sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 15, 0, 15)
        
        icons = ["⊞", "⚡", "⌡"] 
        labels = ["Dashboard", "Core Control", "Power/Thermal"]
        self.sidebar_btns = {}
        
        for ic, lbl in zip(icons, labels):
            btn = QToolButton()
            btn.setText(lbl)
            color = ACCENT_ORANGE if lbl == 'Dashboard' else TEXT_MUTED
            btn.setIcon(create_text_icon(ic, color, size=36)); btn.setIconSize(QSize(36, 36))
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setFixedSize(90, 80)
            btn.setStyleSheet(f"color: {color}; border: none; font-weight: {'bold' if lbl == 'Dashboard' else 'normal'}; font-size: 11px; padding-top: 5px;")
            self.sidebar_btns[lbl] = btn; sidebar_layout.addWidget(btn)
            
        self.sidebar_btns["Core Control"].clicked.connect(self.open_core_control)
        self.sidebar_btns["Power/Thermal"].clicked.connect(self.open_power_control)
        sidebar_layout.addStretch(); main_layout.addWidget(sidebar)
        
        content_widget = QWidget(); content_layout = QVBoxLayout(content_widget); content_layout.setContentsMargins(10, 10, 10, 10); content_layout.setSpacing(10); main_layout.addWidget(content_widget, 1)
        
        top_frame = QFrame(); top_frame.setStyleSheet(f"background-color: {BG_PANEL}; border: 1px solid {BORDER}; border-radius: 6px;"); top_frame.setFixedHeight(140); top_layout = QHBoxLayout(top_frame)
        plot_vbox = QVBoxLayout(); title_lbl = QLabel("⚡ Package Power Tracking"); title_lbl.setStyleSheet("color: #cbd5e1; border: none; font-weight: bold;"); plot_vbox.addWidget(title_lbl)
        self.main_plot = pg.PlotWidget(); self.main_plot.setBackground(None); self.main_plot.hideButtons(); self.main_plot.enableAutoRange(axis='y', enable=True); self.main_plot.setLimits(yMin=0)
        self.main_plot.getAxis('left').setPen(TEXT_MUTED); self.main_plot.getAxis('bottom').setPen(TEXT_MUTED); self.main_plot.showGrid(x=False, y=True, alpha=0.3); self.main_plot.setStyleSheet("border: none;")
        self.power_curve = self.main_plot.plot(list(range(100)), list(self.power_history), pen=pg.mkPen(ACCENT_RED, width=2), fillLevel=0, brush=(239, 68, 68, 60))
        plot_vbox.addWidget(self.main_plot); top_layout.addLayout(plot_vbox, 5)
        power_stats = QVBoxLayout(); self.power_lbl = QLabel("0.00 W / 162.00 W"); self.power_lbl.setStyleSheet(f"color: {ACCENT_RED}; font-size: 22px; border: none;")
        power_sub = QLabel("Package Power / PPT Limit"); power_sub.setStyleSheet("color: #8b9bb4; border: none; font-size: 11px;")
        power_stats.addStretch(); power_stats.addWidget(self.power_lbl, alignment=Qt.AlignmentFlag.AlignCenter); power_stats.addWidget(power_sub, alignment=Qt.AlignmentFlag.AlignCenter); power_stats.addStretch(); top_layout.addLayout(power_stats, 2)
        self.vcore_gauge = Gauge("Vcore\nPeak:", "0.000 V", "Avg: 0.000 V", 2.0, ACCENT_ORANGE); top_layout.addWidget(self.vcore_gauge); content_layout.addWidget(top_frame)
        
        middle_layout = QHBoxLayout()
        cores_frame = QFrame(); cores_frame.setStyleSheet(f"border: 1px solid {BORDER}; border-radius: 6px;"); cores_layout = QVBoxLayout(cores_frame)
        cores_title = QLabel("⌄ Core Telemetry"); cores_title.setStyleSheet("color: #cbd5e1; border: none;"); cores_layout.addWidget(cores_title)
        grid = QGridLayout(); grid.setSpacing(8); self.core_widgets = []
        for i in range(8):
            cw = CoreWidget(f"0-{i}"); self.core_widgets.append(cw); grid.addWidget(cw, i // 4, i % 4)
        cores_layout.addLayout(grid); middle_layout.addWidget(cores_frame, 3)
        
        status_frame = QFrame(); status_frame.setStyleSheet(f"border: 1px solid {BORDER}; border-radius: 6px; background-color: {BG_MAIN};"); status_layout = QVBoxLayout(status_frame); status_layout.setSpacing(0)
        status_title = QLabel("☷ System Status"); status_title.setStyleSheet("color: #cbd5e1; border: none; margin-bottom: 10px;"); status_layout.addWidget(status_title)
        gauges_layout = QHBoxLayout(); self.edc_gauge = Gauge("EDC:", "180 A", "/ 225 A", 225, ACCENT_ORANGE); self.edc_gauge.setValue(180)
        self.tdc_gauge = Gauge("TDC:", "125 A", "/ 160 A", 160, ACCENT_RED); self.tdc_gauge.setValue(125)
        gauges_layout.addWidget(self.edc_gauge); gauges_layout.addWidget(self.tdc_gauge); status_layout.addLayout(gauges_layout); status_layout.addStretch()
        fclk_container = QWidget(); fclk_container.setStyleSheet(f"border-top: 1px solid {BORDER};"); fclk_lay = QVBoxLayout(fclk_container)
        fabric_lbl = QLabel("Fabric Clock (FCLK):\n2000 MHz"); fabric_lbl.setStyleSheet("color: #f8fafc; font-size: 14px; border: none; padding: 5px 0;"); fclk_lay.addWidget(fabric_lbl); status_layout.addWidget(fclk_container)
        uclk_container = QWidget(); uclk_container.setStyleSheet(f"border-top: 1px solid {BORDER};"); uclk_lay = QVBoxLayout(uclk_container)
        mem_lbl = QLabel("Memory Clock (UCLK):\n3000 MHz"); mem_lbl.setStyleSheet("color: #f8fafc; font-size: 14px; border: none; padding: 5px 0;"); uclk_lay.addWidget(mem_lbl); status_layout.addWidget(uclk_container)
        middle_layout.addWidget(status_frame, 1); content_layout.addLayout(middle_layout)
        
        # --- PANNEAU DE LOGS MODIFIÉ ---
        self.log_frame = QFrame()
        self.log_frame.setStyleSheet(f"background-color: {BG_INNER}; border: 1px solid {BORDER}; border-radius: 6px;")
        self.log_frame.setFixedHeight(100) # Hauteur de base
        
        log_layout = QVBoxLayout(self.log_frame)
        log_layout.setContentsMargins(10, 5, 10, 5)
        
        log_header = QHBoxLayout()
        log_title = QLabel("Log")
        log_title.setStyleSheet("color: #f8fafc; font-weight: bold; border: none;")
        
        # Le nouveau vrai bouton !
        self.btn_toggle_log = QPushButton("🗖")
        self.btn_toggle_log.setStyleSheet("color: #8b9bb4; border: none; font-size: 16px; background: transparent;")
        self.btn_toggle_log.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_log.clicked.connect(self.toggle_log_size)
        
        log_header.addWidget(log_title)
        log_header.addStretch()
        log_header.addWidget(self.btn_toggle_log) # Ajout de notre bouton fonctionnel sans la croix
        log_layout.addLayout(log_header)
        
        text_row = QHBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background-color: transparent; border: none; color: #8b9bb4; font-family: Consolas; font-size: 11px;")
        text_row.addWidget(self.log_text)
        log_layout.addLayout(text_row)
        content_layout.addWidget(self.log_frame)

        self.log_msg("Dashboard initialized. Listening to kernel logs...", "STATUS", ACCENT_GREEN)

        self.log_worker = KernelLogWorker()
        self.log_worker.log_signal.connect(lambda msg: self.log_msg(msg, "KERNEL", ACCENT_PURPLE))
        self.log_worker.start()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(500)

    # --- LOGIQUE D'AGRANDISSEMENT DES LOGS ---
    def toggle_log_size(self):
        if self.log_frame.height() <= 100:
            self.log_frame.setFixedHeight(350)  # On déploie
            self.btn_toggle_log.setText("🗗")    # Icône fenêtre réduite
        else:
            self.log_frame.setFixedHeight(100)  # On rétracte
            self.btn_toggle_log.setText("🗖")    # Icône fenêtre max
            
    def log_msg(self, msg, level="INFO", color="#3b82f6"):
        self.log_text.append(f"<span style='color:{color};'>[{level}]</span> {msg}")
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def load_co_config(self):
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r") as f:
                    data = json.load(f)
                return data.get("co_offsets", [0] * 8)
        except Exception:
            pass
        return [0] * 8

    def save_co_config(self):
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w") as f:
                json.dump({"co_offsets": self.current_co}, f)
        except Exception:
            pass

    def send_smu_cmd(self, msg_id, arg0=0):
        if msg_id == 0x10:
            self.log_msg("FATAL GUARDRAIL: MSG 0x10 BLOCKED", "ERROR", ACCENT_RED)
            return False
        if 0x03 <= msg_id <= 0x0D:
            self.log_msg(f"GUARDRAIL: MSG {hex(msg_id)} BLOCKED", "WARNING", ACCENT_ORANGE)
            return False

        SMU_ARGS  = "/sys/kernel/ryzen_smu_drv/smu_args"
        SMU_CMD   = "/sys/kernel/ryzen_smu_drv/mp1_smu_cmd"

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

            rsp_str = {1: "OK", 0xFD: "REJECTED", 0xFE: "UNKNOWN_CMD", 0xFF: "FAILED"}.get(rsp, f"0x{rsp:02X}")
            color = ACCENT_GREEN if rsp == 1 else ACCENT_RED
            self.log_msg(f"SMU MP1 -> MSG: {hex(msg_id)}, ARG0: {hex(arg0)} => RSP: {rsp_str}", "SMU", color)
            return rsp == 1
        except Exception as e:
            self.log_msg(f"SMU write failed: {str(e)}", "ERROR", ACCENT_RED)
            return False

    def open_power_control(self):
        dlg = PowerControlDialog(self.current_ppt, self.current_tdc, self.current_edc, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.current_ppt = dlg.inputs["PPT"].value()
            self.current_tdc = dlg.inputs["TDC"].value()
            self.current_edc = dlg.inputs["EDC"].value()
            self.send_smu_cmd(0x3E, int(self.current_ppt * 1000))
            self.send_smu_cmd(0x3D, int(self.current_tdc * 1000))  # 0x3D = TDC!
            self.send_smu_cmd(0x3C, int(self.current_edc * 1000))  # 0x3C = EDC!

    def open_core_control(self):
        dlg = CoreControlDialog(self.current_co, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            for i, spin in enumerate(dlg.spins):
                val = spin.value()
                if val != self.current_co[i]:
                    self.current_co[i] = val
                    msg_id = 0x50 + i
                    arg0 = val & 0xFFFFFFFF
                    self.send_smu_cmd(msg_id, arg0)
            self.save_co_config()
            self.log_msg(f"CO offsets saved: {self.current_co}", "STATUS", ACCENT_GREEN)

    def update_data(self):
        try:
            with open("/sys/kernel/ryzen_smu_drv/pm_table_version", "rb") as f:
                ver = struct.unpack("<I", f.read(4))[0]
                if ver != 0x620105:
                    self.log_msg(f"PM TABLE VERSION MISMATCH: Expected 0x620105, got {hex(ver)}. Offsets corrupted!", "ERROR", ACCENT_RED)
                    return
        except Exception:
            pass

        try:
            with open("/sys/kernel/ryzen_smu_drv/pm_table", "rb") as f:
                data = f.read(1828)
                if len(data) == 1828:
                    d = struct.unpack("<457f", data)
                    self.current_ppt = d[2]
                    self.current_edc = d[8]
                    self.current_tdc = d[10]
                    pkg_pwr = d[20]
                    
                    self.power_lbl.setText(f"{pkg_pwr:.2f} W / {self.current_ppt:.2f} W")
                    self.edc_gauge.setValue(self.current_edc, main_text=f"{self.current_edc:.0f} A")
                    self.tdc_gauge.setValue(self.current_tdc, main_text=f"{self.current_tdc:.0f} A")
                    self.power_history.append(pkg_pwr)
                    self.power_curve.setData(list(range(100)), list(self.power_history))

                    vcores = [d[309+i] for i in range(8)]
                    vcore_peak, vcore_avg = max(vcores), sum(vcores) / 8
                    self.vcore_gauge.setValue(vcore_peak, f"{vcore_peak:.3f} V", f"Avg: {vcore_avg:.3f} V")

                    for i in range(8):
                        volt, temp = d[309+i], d[317+i]
                        freq, max_freq = d[325+i] * 1000, d[373+i] * 1000
                        cw = self.core_widgets[i]
                        cw.freq_lbl.setText(f"{freq:.2f} MHz"); cw.max_lbl.setText(f"Max: {max_freq:.2f} MHz")
                        cw.volt_lbl.setText(f"⚡ {volt:.3f} V"); cw.temp_lbl.setText(f"🌡 {temp:.2f} C")
                        cw.co_lbl.setText(f"CO: {self.current_co[i]}")
                        
                        load = min(100, max(0, (freq / max_freq * 100) if max_freq > 0 else 0))
                        self.core_load_history[i].append(load)
                        cw.bg.setOpts(height=list(self.core_load_history[i]))

        except FileNotFoundError:
            pass
        except Exception as e:
            pass

if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = GNRMaster()
    w.show()
    sys.exit(app.exec())
