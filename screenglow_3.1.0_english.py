#!/usr/bin/env python3
# ScreenGlow 3.1.0 - English Edition - Debian 13 / XFCE / X11
import os
import sys
import re
import signal
import ctypes
import ctypes.util
import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt, QProcess, QTimer, pyqtSignal, QObject, QSettings, QSize
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QFont, QDesktopServices, QIcon, QCursor,
    QRadialGradient, QPolygonF
)
from PyQt6.QtCore import QUrl, QPointF
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QGridLayout, QComboBox, QSlider, QCheckBox, QFileDialog,
    QMessageBox, QColorDialog, QFrame, QProgressBar, QSizePolicy
)

APP_NAME = "ScreenGlow"
APP_VERSION = "3.1.0"
CONFIG_ORG = "ScreenGlow"
CONFIG_APP = "ScreenGlow"


def run_text(args):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=3)
        return p.stdout.strip() if p.returncode == 0 else ""
    except Exception:
        return ""


def get_display_size():
    out = run_text(["xrandr"])
    # The active mode is marked with an asterisk, e.g. 1920x1080+0+0 60.00*
    m = re.search(r"^\s*(\d+)x(\d+)\+\d+\+\d+.*\*", out, re.M)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"^\s*(\d+)x(\d+)\s+\d", out, re.M)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 1920, 1080


def get_audio_sources():
    out = run_text(["pactl", "list", "short", "sources"])
    sources = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and not parts[1].endswith(".monitor"):
            sources.append((parts[1], parts[1]))
    if not sources:
        sources = [("default", "Default microphone")]
    return sources


class ClickBus(QObject):
    clicked = pyqtSignal(int, int, int)


class CursorOverlay(QWidget):
    def __init__(self, color="#ffd43b", diameter=42, intensity=70, speed=50):
        super().__init__()
        self.color = QColor(color)
        self.diameter = diameter
        self.intensity = intensity
        self.speed = speed
        self.clicks = []
        self.mouse_x = 0
        self.mouse_y = 0
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)
        self.hide()

    def set_options(self, color, diameter, intensity, speed):
        self.color = QColor(color)
        self.diameter = diameter
        self.intensity = intensity
        self.speed = speed
        self.update()

    def add_click(self, x, y, button):
        self.clicks.append({"x": x, "y": y, "button": button, "age": 0})
        self.clicks = self.clicks[-8:]
        self.update()

    def tick(self):
        try:
            pos = QCursor.pos()
            local_pos = self.mapFromGlobal(pos)
            self.mouse_x = local_pos.x()
            self.mouse_y = local_pos.y()
        except Exception:
            pass

        step = max(1, int(self.speed / 25))
        for c in self.clicks:
            c["age"] += step
        self.clicks = [c for c in self.clicks if c["age"] < 34]

        if self.isVisible():
            self.update()

    def show_overlay(self):
        self.setGeometry(QApplication.primaryScreen().geometry())
        self.show()
        self.raise_()
        self._make_x11_clickthrough()

    def _make_x11_clickthrough(self):
        # Empty X11 ShapeInput region: clicks pass through to windows underneath.
        try:
            x11_name = ctypes.util.find_library("X11")
            xext_name = ctypes.util.find_library("Xext")
            if not x11_name or not xext_name:
                return
            x11 = ctypes.CDLL(x11_name)
            xext = ctypes.CDLL(xext_name)
            x11.XOpenDisplay.restype = ctypes.c_void_p
            display = x11.XOpenDisplay(None)
            if not display:
                return
            x11.XFlush.argtypes = [ctypes.c_void_p]
            x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
            xext.XShapeCombineRectangles.argtypes = [
                ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int,
                ctypes.c_int, ctypes.c_int, ctypes.c_void_p,
                ctypes.c_int, ctypes.c_int, ctypes.c_int
            ]
            # ShapeInput=2, ShapeSet=0, Unsorted=0; zero rectangles = no input area.
            xext.XShapeCombineRectangles(
                display, int(self.winId()), 2, 0, 0, None, 0, 0, 0
            )
            x11.XFlush(display)
            x11.XCloseDisplay(display)
        except Exception:
            pass

    def paintEvent(self, event):
        if not self.isVisible():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        x, y = self.mouse_x, self.mouse_y
        d = self.diameter
        # Soft, semi-transparent shadow around the pointer (without a hard ring).
        radius = max(18.0, d * 0.90)
        shadow = QRadialGradient(QPointF(x, y), radius)
        center = QColor(self.color)
        center.setAlpha(62)
        middle = QColor(self.color)
        middle.setAlpha(30)
        edge = QColor(self.color)
        edge.setAlpha(0)
        shadow.setColorAt(0.0, center)
        shadow.setColorAt(0.48, middle)
        shadow.setColorAt(1.0, edge)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(shadow)
        p.drawEllipse(QPointF(x, y), radius, radius)

        # The click animation is drawn above the shadow.
        for c in self.clicks:
            age = c["age"]
            progress = age / 34.0
            click_radius = 8 + int(progress * (d * (0.8 + self.intensity / 100)))
            alpha = max(0, int((1.0 - progress) * (100 + self.intensity * 1.55)))
            click_color = QColor("#ff5a36" if c["button"] == 3 else self.color)
            click_color.setAlpha(min(255, alpha))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(click_color, max(1, 4 - int(progress * 3))))
            p.drawEllipse(c["x"] - click_radius, c["y"] - click_radius,
                          click_radius * 2, click_radius * 2)

        p.end()


class MouseCapture:
    def __init__(self, bus):
        self.bus = bus
        self.listener = None

    def start(self):
        try:
            from pynput import mouse
            def on_click(x, y, button, pressed):
                if pressed:
                    b = 3 if button == mouse.Button.right else 1
                    self.bus.clicked.emit(int(x), int(y), b)
            self.listener = mouse.Listener(on_click=on_click)
            self.listener.daemon = True
            self.listener.start()
            return True
        except Exception:
            return False

    def stop(self):
        if self.listener:
            try:
                self.listener.stop()
                self.listener.join(timeout=1)
            except Exception:
                pass
            self.listener = None


class ScreenGlow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings(CONFIG_ORG, CONFIG_APP)
        self.process = None
        self.recording = False
        self.paused = False
        self.allow_close = False
        self.closing_after_stop = False
        self.elapsed_seconds = 0
        self.output_file = ""
        self.stderr_buffer = ""
        self.bus = ClickBus()
        self.bus.clicked.connect(self.on_mouse_click)
        self.mouse_capture = MouseCapture(self.bus)

        self.overlay = CursorOverlay(
            self.settings.value("cursor/color", "#ffd43b"),
            int(self.settings.value("cursor/size", 42)),
            int(self.settings.value("cursor/intensity", 70)),
            int(self.settings.value("cursor/speed", 50))
        )

        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setMinimumSize(760, 600)
        self.resize(850, 680)
        self.setWindowIcon(QIcon.fromTheme("media-record"))
        self.build_ui()
        self.apply_theme()
        self.load_settings()
        self.clock = QTimer(self)
        self.clock.timeout.connect(self.update_clock)
        self.clock.start(1000)
        self.update_audio_sources()
        self.set_status("Ready to record", "#55d68b")

    def build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(26, 22, 26, 22)
        main.setSpacing(16)

        header = QHBoxLayout()
        brand = QVBoxLayout()
        title = QLabel("ScreenGlow")
        title.setObjectName("brand")
        subtitle = QLabel("SCREEN RECORDING • CURSOR EFFECTS • MICROPHONE")
        subtitle.setObjectName("subtitle")
        brand.addWidget(title)
        brand.addWidget(subtitle)
        header.addLayout(brand)
        header.addStretch()
        self.status_label = QLabel("● READY")
        self.status_label.setObjectName("status")
        header.addWidget(self.status_label)
        main.addLayout(header)

        self.timer_label = QLabel("00:00:00")
        self.timer_label.setObjectName("timer")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main.addWidget(self.timer_label)

        record_card = self.card()
        rec_layout = QVBoxLayout(record_card)
        rec_layout.setContentsMargins(18, 16, 18, 16)
        rec_title = QLabel("RECORDING")
        rec_title.setObjectName("section")
        rec_layout.addWidget(rec_title)

        row = QHBoxLayout()
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems([
            "Screen (native resolution)",
            "1920 × 1080",
            "1600 × 900",
            "1280 × 720",
            "1024 × 768"
        ])
        self.fps_combo = QComboBox()
        self.fps_combo.addItems(["15 FPS", "30 FPS", "60 FPS"])
        self.fps_combo.setCurrentText("30 FPS")
        row.addWidget(QLabel("Resolution"))
        row.addWidget(self.resolution_combo, 2)
        row.addSpacing(12)
        row.addWidget(QLabel("FPS"))
        row.addWidget(self.fps_combo, 1)
        rec_layout.addLayout(row)

        self.audio_check = QCheckBox("Record microphone audio")
        self.audio_check.setChecked(False)
        self.audio_combo = QComboBox()
        self.refresh_audio_btn = QPushButton("↻")
        self.refresh_audio_btn.setFixedWidth(42)
        self.refresh_audio_btn.clicked.connect(self.update_audio_sources)
        audio_row = QHBoxLayout()
        audio_row.addWidget(self.audio_check)
        audio_row.addWidget(self.audio_combo, 1)
        audio_row.addWidget(self.refresh_audio_btn)
        rec_layout.addLayout(audio_row)
        main.addWidget(record_card)

        cursor_card = self.card()
        cur_layout = QVBoxLayout(cursor_card)
        cur_layout.setContentsMargins(18, 16, 18, 16)
        cur_header = QHBoxLayout()
        cur_title = QLabel("CURSOR EFFECT")
        cur_title.setObjectName("section")
        cur_header.addWidget(cur_title)
        cur_header.addStretch()
        self.color_btn = QPushButton("●  Ring color")
        self.color_btn.clicked.connect(self.choose_color)
        cur_header.addWidget(self.color_btn)
        cur_layout.addLayout(cur_header)

        grid = QGridLayout()
        self.size_value = QLabel("42 px")
        self.intensity_value = QLabel("70%")
        self.speed_value = QLabel("50%")
        self.size_slider = self.make_slider(20, 100, 42)
        self.intensity_slider = self.make_slider(10, 100, 70)
        self.speed_slider = self.make_slider(10, 100, 50)
        for slider, label, key in [
            (self.size_slider, self.size_value, "size"),
            (self.intensity_slider, self.intensity_value, "intensity"),
            (self.speed_slider, self.speed_value, "speed")
        ]:
            slider.valueChanged.connect(lambda v, l=label, k=key: self.slider_changed(k, v, l))
        grid.addWidget(QLabel("Ring size"), 0, 0)
        grid.addWidget(self.size_slider, 0, 1)
        grid.addWidget(self.size_value, 0, 2)
        grid.addWidget(QLabel("Animation intensity"), 1, 0)
        grid.addWidget(self.intensity_slider, 1, 1)
        grid.addWidget(self.intensity_value, 1, 2)
        grid.addWidget(QLabel("Animation speed"), 2, 0)
        grid.addWidget(self.speed_slider, 2, 1)
        grid.addWidget(self.speed_value, 2, 2)
        cur_layout.addLayout(grid)
        main.addWidget(cursor_card)

        controls = QHBoxLayout()
        self.record_btn = QPushButton("●  START RECORDING")
        self.record_btn.setObjectName("record")
        self.pause_btn = QPushButton("Ⅱ  PAUSE")
        self.pause_btn.setEnabled(False)
        self.stop_btn = QPushButton("■  STOP")
        self.stop_btn.setObjectName("stop")
        self.stop_btn.setEnabled(False)
        self.record_btn.clicked.connect(self.start_recording)
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.stop_btn.clicked.connect(self.stop_recording)
        controls.addWidget(self.record_btn, 2)
        controls.addWidget(self.pause_btn, 1)
        controls.addWidget(self.stop_btn, 1)
        main.addLayout(controls)

        bottom = QHBoxLayout()
        self.preview_btn = QPushButton("▶  Preview last recording")
        self.preview_btn.clicked.connect(self.preview_last_recording)
        self.preview_btn.setEnabled(False)
        self.folder_btn = QPushButton("📁  Open recordings folder")
        self.folder_btn.clicked.connect(self.open_video_folder)
        bottom.addWidget(self.preview_btn)
        bottom.addWidget(self.folder_btn)
        main.addLayout(bottom)

        self.info_label = QLabel("Recordings are saved in the Videos folder.")
        self.info_label.setObjectName("info")
        main.addWidget(self.info_label)

    def card(self):
        frame = QFrame()
        frame.setObjectName("card")
        return frame

    def make_slider(self, low, high, value):
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(low, high)
        s.setValue(value)
        return s

    def apply_theme(self):
        self.setStyleSheet("""
            QWidget#root { background: #10141d; color: #e8edf5; font-family: 'DejaVu Sans'; font-size: 10pt; }
            QLabel#brand { color: #f5f7fb; font-size: 27pt; font-weight: 800; }
            QLabel#subtitle { color: #8491a5; font-size: 8pt; letter-spacing: 1px; }
            QLabel#status { color: #55d68b; font-weight: 700; padding: 9px 13px; background: #1b2930; border-radius: 10px; }
            QLabel#timer { color: #f5f7fb; font-size: 31pt; font-weight: 700; padding: 8px; }
            QLabel#section { color: #9eacc2; font-size: 9pt; font-weight: 800; letter-spacing: 1px; }
            QFrame#card { background: #191f2b; border: 1px solid #293345; border-radius: 14px; }
            QLabel { color: #dce3ee; }
            QLabel#info { color: #77859a; font-size: 8pt; }
            QComboBox { background: #222b3a; border: 1px solid #344158; border-radius: 8px; padding: 9px; color: #edf2fa; }
            QComboBox QAbstractItemView { background: #222b3a; selection-background-color: #365c91; }
            QSlider::groove:horizontal { height: 6px; background: #303b4e; border-radius: 3px; }
            QSlider::handle:horizontal { background: #62a4ff; width: 16px; margin: -5px 0; border-radius: 8px; }
            QCheckBox { spacing: 8px; color: #dce3ee; }
            QCheckBox::indicator { width: 17px; height: 17px; }
            QPushButton { background: #273246; color: #eaf0fa; border: 1px solid #394862; border-radius: 9px; padding: 11px 13px; font-weight: 700; }
            QPushButton:hover { background: #34445e; }
            QPushButton:disabled { color: #68758a; background: #202735; border-color: #2b3444; }
            QPushButton#record { background: #c7464f; border: 0; color: white; font-size: 11pt; padding: 15px; }
            QPushButton#record:hover { background: #df5660; }
            QPushButton#stop { background: #8d3440; border: 0; }
        """)

    def load_settings(self):
        self.size_slider.setValue(int(self.settings.value("cursor/size", 42)))
        self.intensity_slider.setValue(int(self.settings.value("cursor/intensity", 70)))
        self.speed_slider.setValue(int(self.settings.value("cursor/speed", 50)))
        self.resolution_combo.setCurrentIndex(int(self.settings.value("video/resolution", 0)))
        self.fps_combo.setCurrentText(self.settings.value("video/fps", "30 FPS"))
        self.audio_check.setChecked(self.settings.value("audio/enabled", False, type=bool))
        self.color = self.settings.value("cursor/color", "#ffd43b")
        self.update_overlay_options()
        self.update_slider_labels()

    def save_settings(self):
        self.settings.setValue("cursor/size", self.size_slider.value())
        self.settings.setValue("cursor/intensity", self.intensity_slider.value())
        self.settings.setValue("cursor/speed", self.speed_slider.value())
        self.settings.setValue("cursor/color", getattr(self, "color", "#ffd43b"))
        self.settings.setValue("video/resolution", self.resolution_combo.currentIndex())
        self.settings.setValue("video/fps", self.fps_combo.currentText())
        self.settings.setValue("audio/enabled", self.audio_check.isChecked())

    def update_slider_labels(self):
        self.size_value.setText(f"{self.size_slider.value()} px")
        self.intensity_value.setText(f"{self.intensity_slider.value()}%")
        self.speed_value.setText(f"{self.speed_slider.value()}%")

    def slider_changed(self, key, value, label):
        suffix = " px" if key == "size" else "%"
        label.setText(f"{value}{suffix}")
        self.update_overlay_options()

    def update_overlay_options(self):
        self.overlay.set_options(
            getattr(self, "color", "#ffd43b"),
            self.size_slider.value(),
            self.intensity_slider.value(),
            self.speed_slider.value()
        )

    def choose_color(self):
        c = QColorDialog.getColor(QColor(getattr(self, "color", "#ffd43b")), self, "Choose ring color")
        if c.isValid():
            self.color = c.name()
            self.color_btn.setStyleSheet(f"color: {self.color};")
            self.update_overlay_options()

    def update_audio_sources(self):
        current = self.audio_combo.currentData() if hasattr(self, "audio_combo") else None
        self.audio_combo.clear()
        for label, device in get_audio_sources():
            self.audio_combo.addItem(label, device)
        if current:
            idx = self.audio_combo.findData(current)
            if idx >= 0:
                self.audio_combo.setCurrentIndex(idx)

    def set_status(self, text, color):
        self.status_label.setText("● " + text.upper())
        self.status_label.setStyleSheet(
            f"color:{color};font-weight:700;padding:9px 13px;background:#1b2930;border-radius:10px;"
        )

    def build_ffmpeg_command(self, filename):
        display = os.environ.get("DISPLAY", ":0")
        sw, sh = get_display_size()
        choice = self.resolution_combo.currentIndex()
        sizes = [(sw, sh), (1920, 1080), (1600, 900), (1280, 720), (1024, 768)]
        w, h = sizes[choice]
        if w > sw or h > sh:
            w, h = sw, sh
            self.info_label.setText(f"The selected resolution is unavailable; using {sw} × {sh}.")
        fps = int(self.fps_combo.currentText().split()[0])
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
            "-thread_queue_size", "1024",
            "-f", "x11grab", "-draw_mouse", "1",
            "-framerate", str(fps), "-video_size", f"{w}x{h}",
            "-i", f"{display}+0,0"
        ]
        audio_enabled = self.audio_check.isChecked()
        if audio_enabled:
            device = self.audio_combo.currentData() or "default"
            cmd += ["-thread_queue_size", "1024", "-f", "pulse", "-i", str(device)]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
        if audio_enabled:
            cmd += ["-c:a", "aac", "-b:a", "160k"]
        else:
            cmd += ["-an"]
        cmd += ["-movflags", "+faststart", filename]
        return cmd

    def start_recording(self):
        if self.recording:
            return
        if not os.environ.get("DISPLAY"):
            QMessageBox.critical(self, "Error", "The DISPLAY environment variable was not found. Run the application in an X11 session.")
            return
        if not shutil_which("ffmpeg"):
            QMessageBox.critical(self, "FFmpeg is missing", "Install FFmpeg with the following command:\nsudo apt install ffmpeg")
            return
        if self.audio_check.isChecked() and not shutil_which("pactl"):
            QMessageBox.warning(self, "Audio", "The pactl utility was not found. Install pulseaudio-utils or disable microphone recording.")
            return
        folder = Path.home() / "Videos"
        folder.mkdir(parents=True, exist_ok=True)
        from datetime import datetime
        filename = folder / f"ScreenGlow_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.mp4"
        self.output_file = str(filename)
        self.stderr_buffer = ""
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.process.readyReadStandardError.connect(self.read_stderr)
        self.process.finished.connect(self.recording_finished)
        cmd = self.build_ffmpeg_command(self.output_file)
        self.process.start(cmd[0], cmd[1:])
        if not self.process.waitForStarted(2500):
            QMessageBox.critical(self, "Error", "FFmpeg nije uspeo da se pokrene.\n" + self.process.errorString())
            self.process = None
            return
        self.recording = True
        self.paused = False
        self.elapsed_seconds = 0
        self.clock.start(1000)
        self.overlay.show_overlay()
        self.mouse_capture.start()
        self.record_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.preview_btn.setEnabled(False)
        self.set_status("Recording in progress", "#ff737d")
        self.info_label.setText(f"Čuvanje: {self.output_file}")
        self.save_settings()

    def read_stderr(self):
        if self.process:
            try:
                self.stderr_buffer += bytes(self.process.readAllStandardError()).decode(errors="replace")
                self.stderr_buffer = self.stderr_buffer[-12000:]
            except Exception:
                pass

    def on_mouse_click(self, x, y, button):
        if self.recording and not self.paused:
            self.overlay.add_click(x, y, button)

    def toggle_pause(self):
        if not self.recording or not self.process:
            return
        pid = int(self.process.processId())
        try:
            if not self.paused:
                os.kill(pid, signal.SIGSTOP)
                self.paused = True
                self.pause_btn.setText("▶  RESUME")
                self.set_status("Paused", "#f2c45b")
                self.overlay.hide()
            else:
                os.kill(pid, signal.SIGCONT)
                self.paused = False
                self.pause_btn.setText("Ⅱ  PAUSE")
                self.set_status("Recording in progress", "#ff737d")
                self.overlay.show_overlay()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not change pause state:\n{e}")

    def stop_recording(self):
        if not self.recording or not self.process:
            return
        if self.paused:
            try:
                os.kill(int(self.process.processId()), signal.SIGCONT)
            except Exception:
                pass
            self.paused = False
        self.stop_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.set_status("Finalizing recording", "#f2c45b")
        self.mouse_capture.stop()
        self.overlay.hide()
        self.process.write(b"q\n")
        self.process.closeWriteChannel()
        QTimer.singleShot(5000, self.force_stop_if_needed)

    def force_stop_if_needed(self):
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.terminate()
            QTimer.singleShot(1500, self.kill_if_needed)

    def kill_if_needed(self):
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()

    def recording_finished(self, exit_code, exit_status):
        self.read_stderr()
        self.recording = False
        self.paused = False
        self.mouse_capture.stop()
        self.overlay.hide()
        self.record_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("Ⅱ  PAUSE")
        self.stop_btn.setEnabled(False)
        self.process = None
        self.clock.stop()
        self.set_status("Recording saved", "#55d68b")
        self.timer_label.setText(self.format_time(self.elapsed_seconds))
        good_file = self.output_file and Path(self.output_file).exists() and Path(self.output_file).stat().st_size > 1000
        self.preview_btn.setEnabled(bool(good_file))
        if not good_file and self.stderr_buffer:
            QMessageBox.warning(self, "FFmpeg error", self.stderr_buffer[-3500:])
            self.info_label.setText("Recording did not finish correctly. Check the FFmpeg message.")
        elif good_file:
            self.info_label.setText(f"Saved: {self.output_file}")
        if self.closing_after_stop:
            self.closing_after_stop = False
            self._really_close()
            self.allow_close = True
            self.close()

    def update_clock(self):
        if self.recording and not self.paused:
            self.elapsed_seconds += 1
            self.timer_label.setText(self.format_time(self.elapsed_seconds))

    @staticmethod
    def format_time(seconds):
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def preview_last_recording(self):
        if self.output_file and Path(self.output_file).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.output_file))
        else:
            QMessageBox.information(self, "Preview", "There is no recording to preview yet.")

    def open_video_folder(self):
        folder = Path.home() / "Videos"
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def closeEvent(self, event):
        if self.allow_close:
            event.accept()
            return
        if self.recording:
            answer = QMessageBox.question(
                self, "Close ScreenGlow",
                "Recording is in progress. Do you want to stop recording and close the application?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.closing_after_stop = True
            event.ignore()
            self.stop_recording()
            return
        self._really_close()
        event.accept()

    def _really_close(self):
        self.clock.stop()
        self.mouse_capture.stop()
        self.overlay.timer.stop()
        self.overlay.close()
        self.save_settings()


def shutil_which(command):
    from shutil import which
    return which(command) is not None


def main():
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
        print("ScreenGlow requires an X11 session. Log out and select XFCE on Xorg.")
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(CONFIG_ORG)
    window = ScreenGlow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
