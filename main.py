#!/usr/bin/env python3
"""
LightFrame — Lightweight Video Player for Windows
  • Multiple simultaneous audio tracks (mixed via MPV lavfi)
  • Clip trimming / export (FFmpeg)
  • Drag-and-drop file loading
  • Keyboard shortcuts: Space, I/O, ←/→, Shift+←/→, ↑/↓ (volume)
"""

import sys
import os
import base64
import json
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request

# python-mpv searches %PATH% for the DLL. Prepend the project folder so
# that mpv-2.dll placed next to main.py is found without PATH changes.
_here = os.path.dirname(os.path.abspath(__file__))
os.environ["PATH"] = _here + os.pathsep + os.environ.get("PATH", "")
if sys.platform == 'win32' and hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(_here)

# Dedicated install folder — all user-facing files live here
_DEFAULT_INSTALL_DIR = os.path.join(
    os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'LightFrame')

def get_install_dir() -> str:
    """Return the active install directory from QSettings, or the default."""
    from PyQt5.QtCore import QSettings
    s = QSettings("LightFrame", "LightFrame")
    return s.value("install_dir", _DEFAULT_INSTALL_DIR)

def _save_install_prefs(install_dir: str, create_desktop_shortcut: bool):
    """Save install directory and shortcut preference to QSettings."""
    s = QSettings("LightFrame", "LightFrame")
    s.setValue("install_dir", install_dir)
    s.setValue("create_desktop_shortcut", create_desktop_shortcut)
    s.sync()

def _want_desktop_shortcut() -> bool:
    """Read desktop shortcut preference from QSettings; default True."""
    s = QSettings("LightFrame", "LightFrame")
    return bool(s.value("create_desktop_shortcut", True))

# Backward-compat alias; use get_install_dir() in code
INSTALL_DIR = _DEFAULT_INSTALL_DIR

APP_VERSION = 'v.2.2'
GITHUB_REPO = 'ccSinni/Lightframe'
APP_EXE_NAME = 'lightframe.exe'
LEGACY_APP_EXE_NAME = 'LightFrame.exe'
UPDATE_ASSET_NAME = 'LightframeUpdate.exe'
LATEST_RELEASE_API = f'https://api.github.com/repos/{GITHUB_REPO}/releases/latest'
HTTP_HEADERS = {
    'Accept': 'application/vnd.github+json',
    'User-Agent': f'LightFrame/{APP_VERSION}',
}

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QLabel, QFileDialog, QCheckBox, QGroupBox,
    QMessageBox, QSizePolicy, QStatusBar, QAction, QShortcut, QProgressDialog,
    QComboBox, QLineEdit,
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QSettings, QPoint
from PyQt5.QtGui import QFont, QKeySequence, QColor, QPainter, QPen, QPixmap

try:
    import mpv
    MPV_AVAILABLE = True
except ImportError:
    MPV_AVAILABLE = False


# ── Stylesheet ────────────────────────────────────────────────────────────────

DARK_STYLE = """
QMainWindow, QWidget {
    background: #12161d;
    color: #e7edf7;
    font-family: "Segoe UI", sans-serif;
    font-size: 9pt;
}
QPushButton {
    background: #263241;
    color: #edf3fb;
    border: 1px solid #3a4b61;
    border-radius: 5px;
    padding: 6px 14px;
    min-height: 24px;
}
QPushButton:hover   { background: #304156; border-color: #4aa3ff; }
QPushButton:pressed { background: #1f6fbe; border-color: #68b6ff; }
QPushButton:disabled { color: #677489; border-color: #2a3442; background: #1a2029; }
QPushButton:checked {
    background: #2c86e8;
    border-color: #68b6ff;
}

QSlider::groove:horizontal {
    background: #25303c; height: 6px; border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #d7e8ff;
    width: 13px; height: 13px;
    margin: -4px 0; border-radius: 6px;
    border: 1px solid #4aa3ff;
}
QSlider::sub-page:horizontal { background: #4aa3ff; border-radius: 3px; }

QGroupBox {
    background: #1a2029;
    border: 1px solid #313c4c;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 8px;
    font-weight: bold;
    color: #d4e4fa;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #9fbfe5;
}

QMenuBar {
    background: #10141a;
    color: #dfe8f4;
    border-bottom: 1px solid #212a35;
}
QMenuBar::item { background: transparent; padding: 4px 10px; }
QMenuBar::item:selected { background: #1e2935; }
QMenu {
    background: #171d26;
    border: 1px solid #313c4c;
    color: #e7edf7;
}
QMenu::item { padding: 6px 20px; }
QMenu::item:selected { background: #243445; }

QStatusBar {
    background: #10141a;
    color: #93a1b7;
    font-size: 8pt;
    border-top: 1px solid #212a35;
}
QStatusBar::item { border: none; }

QCheckBox { color: #dce6f3; spacing: 6px; }
QCheckBox::indicator {
    width: 14px; height: 14px;
    background: #131922;
    border: 1px solid #4d6078;
    border-radius: 3px;
}
QCheckBox::indicator:checked { background: #4aa3ff; border-color: #68b6ff; }

QLabel { background: transparent; }

QProgressDialog {
    background: #171d26;
    border: 1px solid #313c4c;
}

QProgressDialog QLabel {
    color: #e7edf7;
    min-width: 320px;
}

QToolTip {
    color: #edf3fb;
    background: #1a2029;
    border: 1px solid #313c4c;
    padding: 4px 6px;
}
"""

LIGHT_STYLE = """
QMainWindow, QWidget {
    background: #f5f5f5;
    color: #1a1a1a;
    font-family: "Segoe UI", sans-serif;
    font-size: 9pt;
}
QPushButton {
    background: #e8e8e8;
    color: #1a1a1a;
    border: 1px solid #cccccc;
    border-radius: 5px;
    padding: 6px 14px;
    min-height: 24px;
}
QPushButton:hover   { background: #d9d9d9; border-color: #2196F3; }
QPushButton:pressed { background: #1976D2; border-color: #1565C0; color: #ffffff; }
QPushButton:disabled { color: #999999; border-color: #e0e0e0; background: #fafafa; }
QPushButton:checked {
    background: #2196F3;
    border-color: #1565C0;
    color: #ffffff;
}

QSlider::groove:horizontal {
    background: #d0d0d0; height: 6px; border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #ffffff;
    width: 13px; height: 13px;
    margin: -4px 0; border-radius: 6px;
    border: 1px solid #2196F3;
}
QSlider::sub-page:horizontal { background: #2196F3; border-radius: 3px; }

QGroupBox {
    background: #fafafa;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 8px;
    font-weight: bold;
    color: #1a1a1a;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #2196F3;
}

QMenuBar {
    background: #ffffff;
    color: #1a1a1a;
    border-bottom: 1px solid #e0e0e0;
}
QMenuBar::item { background: transparent; padding: 4px 10px; }
QMenuBar::item:selected { background: #f0f0f0; }
QMenu {
    background: #ffffff;
    border: 1px solid #e0e0e0;
    color: #1a1a1a;
}
QMenu::item { padding: 6px 20px; }
QMenu::item:selected { background: #f0f0f0; }

QStatusBar {
    background: #ffffff;
    color: #666666;
    font-size: 8pt;
    border-top: 1px solid #e0e0e0;
}
QStatusBar::item { border: none; }

QCheckBox { color: #333333; spacing: 6px; }
QCheckBox::indicator {
    width: 14px; height: 14px;
    background: #ffffff;
    border: 1px solid #999999;
    border-radius: 3px;
}
QCheckBox::indicator:checked { background: #2196F3; border-color: #1565C0; }

QLabel { background: transparent; }

QProgressDialog {
    background: #ffffff;
    border: 1px solid #e0e0e0;
}

QProgressDialog QLabel {
    color: #1a1a1a;
    min-width: 320px;
}

QToolTip {
    color: #1a1a1a;
    background: #fffacd;
    border: 1px solid #e0e0e0;
    padding: 4px 6px;
}
"""

def get_theme() -> str:
    """Get current theme preference (dark or light)."""
    s = QSettings("LightFrame", "LightFrame")
    return s.value("theme", "dark")

def get_style() -> str:
    """Get the current stylesheet based on theme preference."""
    return DARK_STYLE if get_theme() == "dark" else LIGHT_STYLE

def set_theme(app, window, theme: str):
    """Change theme and apply to application."""
    s = QSettings("LightFrame", "LightFrame")
    s.setValue("theme", theme)
    s.sync()
    style = DARK_STYLE if theme == "dark" else LIGHT_STYLE
    app.setStyleSheet(style)
    if window:
        window.setStyleSheet(style)

# Default to DARK_STYLE for now
STYLE = DARK_STYLE


# ── FFmpeg export worker ──────────────────────────────────────────────────────

class TrimWorker(QThread):
    done  = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, src, dst, t_in, t_out, audio_tracks):
        super().__init__()
        self.src    = src
        self.dst    = dst
        self.t_in   = t_in
        self.t_out  = t_out
        self.tracks = audio_tracks   # list of dicts with key 'ffmpeg_index'

    def run(self):
        try:
            ffmpeg_cmd = ffmpeg_exe()
            if not ffmpeg_cmd:
                raise RuntimeError('FFmpeg is not available in an approved location.')
            dur = self.t_out - self.t_in
            n   = len(self.tracks)

            cmd = [ffmpeg_cmd, '-y', '-ss', str(self.t_in), '-i', self.src, '-t', str(dur)]

            if n >= 1:
                # Keep each selected track as a separate audio stream.
                # This preserves multi-track on the exported clip.
                cmd += ['-map', '0:v:0']
                for t in self.tracks:
                    cmd += ['-map', f'0:a:{t["ffmpeg_index"]}']
                cmd += ['-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k']
            else:
                cmd += ['-map', '0:v:0', '-an', '-c:v', 'copy']

            cmd.append(self.dst)

            flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            r = subprocess.run(cmd, capture_output=True, text=True,
                               creationflags=flags, timeout=3600)

            if r.returncode == 0:
                self.done.emit(self.dst)
            else:
                self.error.emit(r.stderr[-2000:])

        except Exception as exc:
            self.error.emit(str(exc))


class ThumbnailWorker(QThread):
    done = pyqtSignal(str, str, float, str)
    error = pyqtSignal(str, str, str)

    def __init__(self, src, dst, t_pos, cache_key):
        super().__init__()
        self.src = src
        self.dst = dst
        self.t_pos = t_pos
        self.cache_key = cache_key

    def run(self):
        try:
            ffmpeg_cmd = ffmpeg_exe()
            if not ffmpeg_cmd:
                raise RuntimeError('FFmpeg is not available in an approved location.')
            os.makedirs(os.path.dirname(self.dst), exist_ok=True)
            cmd = [
                ffmpeg_cmd,
                '-y',
                '-loglevel', 'error',
                '-ss', f'{self.t_pos:.3f}',
                '-i', self.src,
                '-frames:v', '1',
                '-vf', 'scale=240:-1:force_original_aspect_ratio=decrease',
                self.dst,
            ]
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=flags,
                timeout=30,
            )
            if result.returncode == 0 and os.path.isfile(self.dst):
                self.done.emit(self.cache_key, self.dst, self.t_pos, self.src)
            else:
                msg = (result.stderr or 'Thumbnail generation failed.').strip()
                self.error.emit(self.cache_key, msg[-500:], self.src)
        except Exception as exc:
            self.error.emit(self.cache_key, str(exc), self.src)


class ThumbnailPopup(QWidget):

    def __init__(self):
        super().__init__(None, Qt.ToolTip)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setObjectName('ThumbnailPopup')
        self.setStyleSheet(
            '#ThumbnailPopup {'
            'background: #171d26;'
            'border: 1px solid #313c4c;'
            'border-radius: 6px;'
            '}'
            '#ThumbnailImage {'
            'background: #050608;'
            'border: 1px solid #202833;'
            'padding: 2px;'
            '}'
            '#ThumbnailTime {'
            'color: #e7edf7;'
            'font: 9pt "Consolas";'
            'padding-top: 2px;'
            '}'
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self.image_label = QLabel()
        self.image_label.setObjectName('ThumbnailImage')
        self.image_label.setFixedSize(224, 128)
        self.image_label.setAlignment(Qt.AlignCenter)

        self.time_label = QLabel('0:00:00')
        self.time_label.setObjectName('ThumbnailTime')
        self.time_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.image_label)
        layout.addWidget(self.time_label)

    def set_thumbnail(self, path, time_text):
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.image_label.clear()
        else:
            self.image_label.setPixmap(
                pixmap.scaled(
                    self.image_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
        self.time_label.setText(time_text)
        self.adjustSize()

    def move_above(self, global_pos):
        self.adjustSize()
        self.move(global_pos.x() - self.width() // 2, global_pos.y() - self.height() - 18)


# ── Custom seek slider with trim markers ──────────────────────────────────────

class SeekSlider(QWidget):
    """
    Custom seek bar with DaVinci-style zoom.
    All signals emit full-video positions (0–10000 = 0–100%).
    """
    scrubbing    = pyqtSignal(int)   # live update while dragging
    seek_to      = pyqtSignal(int)   # committed seek on mouse release
    drag_start   = pyqtSignal()
    zoom_changed = pyqtSignal(float)
    drag_preview = pyqtSignal(float, QPoint)
    preview_hidden = pyqtSignal()

    _GH  = 10   # groove height (px)
    _RH  = 15   # ruler height (px)
    _BH  = 6    # mini overview bar height (px)
    _PAD = 4    # left/right padding

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(self._GH + self._RH + self._BH + 8)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._pos_frac   = 0.0
        self._duration   = 0.0
        self._in         = None
        self._out        = None
        self._dragging   = False
        self._zoom       = 1.0
        self._view_start = 0.0

    # ── Public API ────────────────────────────────────────────────────────────

    def set_pos_frac(self, frac):
        self._pos_frac = max(0.0, min(1.0, frac))
        self.update()

    def set_duration(self, dur):
        if dur != self._duration:
            self._duration = dur
            self.update()

    def set_markers(self, in_frac, out_frac):
        self._in  = in_frac
        self._out = out_frac
        self.update()

    def clear_markers(self):
        self._in = self._out = None
        self.update()

    # ── Zoom helpers ──────────────────────────────────────────────────────────

    @property
    def _window(self):
        return 1.0 / self._zoom

    def set_view(self, view_start):
        self._view_start = max(0.0, min(1.0 - self._window, view_start))
        self.update()

    def reset_zoom(self):
        self._zoom       = 1.0
        self._view_start = 0.0
        self.update()
        self.zoom_changed.emit(1.0)

    def zoom_step(self, factor):
        center   = self._view_start + self._window / 2
        new_zoom = max(1.0, min(200.0, self._zoom * factor))
        if abs(new_zoom - self._zoom) < 0.001:
            return
        nw = 1.0 / new_zoom
        self._view_start = max(0.0, min(1.0 - nw, center - nw / 2))
        self._zoom       = new_zoom
        self.update()
        self.zoom_changed.emit(new_zoom)

    # ── Coordinate helpers ────────────────────────────────────────────────────

    def _uw(self):
        return self.width() - self._PAD * 2

    def _x_from_frac(self, frac):
        """Full-video fraction → pixel x."""
        in_win = (frac - self._view_start) / self._window
        return self._PAD + in_win * self._uw()

    def _frac_from_x(self, x):
        """Pixel x → full-video fraction (may exceed 0-1)."""
        in_win = (x - self._PAD) / max(1, self._uw())
        return self._view_start + in_win * self._window

    def _val_from_x(self, x):
        return max(0, min(10000, int(self._frac_from_x(x) * 10000)))

    def _in_overview(self, y):
        return y >= self.height() - self._BH - 6

    # ── Mouse ─────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        self.preview_hidden.emit()
        if event.button() != Qt.LeftButton:
            return
        if self._in_overview(event.y()) and self._zoom > 1.001:
            # Click on overview bar: pan the view to that position
            frac = max(0.0, min(1.0, (event.x() - self._PAD) / max(1, self._uw())))
            self.set_view(frac - self._window / 2)
        else:
            self._dragging = True
            self.drag_start.emit()
            val = self._val_from_x(event.x())
            self._pos_frac = val / 10000
            self.update()
            self.scrubbing.emit(val)
            if self._duration > 0:
                self.drag_preview.emit(
                    (val / 10000) * self._duration,
                    self.mapToGlobal(QPoint(event.x(), 0)),
                )
        event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & Qt.LeftButton:
            val = self._val_from_x(event.x())
            self._pos_frac = val / 10000
            self.update()
            self.scrubbing.emit(val)
            if self._duration > 0:
                self.drag_preview.emit(
                    (val / 10000) * self._duration,
                    self.mapToGlobal(QPoint(event.x(), 0)),
                )
            event.accept()

    def leaveEvent(self, event):
        self.preview_hidden.emit()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._dragging:
            self._dragging = False
            val = self._val_from_x(event.x())
            self._pos_frac = val / 10000
            self.update()
            self.seek_to.emit(val)
            self.preview_hidden.emit()
            event.accept()

    def wheelEvent(self, event):
        delta    = event.angleDelta().y()
        factor   = 1.35 if delta > 0 else (1 / 1.35)
        new_zoom = max(1.0, min(200.0, self._zoom * factor))
        if abs(new_zoom - self._zoom) < 0.001:
            return
        # Keep the time fraction under the mouse cursor fixed
        pivot     = self._frac_from_x(event.x())
        new_win   = 1.0 / new_zoom
        local_f   = (pivot - self._view_start) / self._window
        new_start = pivot - local_f * new_win
        self._view_start = max(0.0, min(1.0 - new_win, new_start))
        self._zoom       = new_zoom
        self.update()
        self.zoom_changed.emit(new_zoom)
        event.accept()

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        from PyQt5.QtGui import QPainter, QColor, QPen, QFont
        p  = QPainter(self)
        uw = self._uw()
        pl = self._PAD

        groove_y = 2
        ruler_y  = groove_y + self._GH + 2
        bar_y    = self.height() - self._BH - 2

        # ── Groove ────────────────────────────────────────────────────────
        p.fillRect(pl, groove_y, uw, self._GH, QColor('#25303c'))

        # Trim region highlight
        if self._in is not None and self._out is not None:
            xi = max(pl, min(pl + uw, self._x_from_frac(self._in)))
            xo = max(pl, min(pl + uw, self._x_from_frac(self._out)))
            if xo > xi:
                p.setOpacity(0.35)
                p.fillRect(int(xi), groove_y, int(xo - xi), self._GH, QColor('#4aa3ff'))
                p.setOpacity(1.0)

        # Played region (left of playhead), clipped to groove
        px = max(float(pl), min(float(pl + uw), self._x_from_frac(self._pos_frac)))
        p.fillRect(pl, groove_y, int(px - pl), self._GH, QColor('#2c86e8'))

        # Trim markers
        for frac, col in ((self._in, '#38d27d'), (self._out, '#ff9f43')):
            if frac is None:
                continue
            x = self._x_from_frac(frac)
            if pl - 3 <= x <= pl + uw + 3:
                p.fillRect(int(x) - 1, groove_y, 3, self._GH, QColor(col))

        # Playhead line
        p.setPen(QPen(QColor('#f6fbff'), 2))
        p.drawLine(int(px), groove_y, int(px), groove_y + self._GH - 1)

        # ── Time ruler ────────────────────────────────────────────────────
        p.fillRect(pl, ruler_y, uw, self._RH, QColor('#171d26'))
        if self._duration > 0:
            view_dur = self._duration * self._window
            # Pick the largest "nice" interval that gives 4–12 ticks
            NICE = [0.04, 0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60,
                    120, 300, 600, 1800, 3600]
            interval = NICE[0]
            for n in NICE:
                if view_dur / n <= 12:
                    interval = n
                    break

            start_s = self._view_start * self._duration
            end_s   = (self._view_start + self._window) * self._duration
            t = int(start_s / interval) * interval

            font = QFont("Consolas", 7)
            p.setFont(font)
            p.setPen(QPen(QColor('#435066'), 1))
            while t <= end_s + interval * 0.5:
                if t >= 0:
                    x = int(self._x_from_frac(t / self._duration))
                    if pl <= x <= pl + uw:
                        p.drawLine(x, ruler_y, x, ruler_y + 4)
                        p.setPen(QPen(QColor('#93a1b7'), 1))
                        p.drawText(x + 2, ruler_y + self._RH - 2,
                                   self._fmt_t(t))
                        p.setPen(QPen(QColor('#435066'), 1))
                t += interval

        # ── Mini overview bar ─────────────────────────────────────────────
        p.setOpacity(0.4)
        p.fillRect(pl, bar_y, uw, self._BH, QColor('#25303c'))
        p.setOpacity(1.0)

        # Trim region on overview
        if self._in is not None and self._out is not None:
            p.setOpacity(0.5)
            xi = int(pl + self._in * uw)
            xo = int(pl + self._out * uw)
            p.fillRect(xi, bar_y, max(1, xo - xi), self._BH, QColor('#2c86e8'))
            p.setOpacity(1.0)

        # Viewport window (when zoomed)
        if self._zoom > 1.001:
            vx = int(pl + self._view_start * uw)
            vw = max(3, int(self._window * uw))
            p.setOpacity(0.5)
            p.fillRect(vx, bar_y, vw, self._BH, QColor('#4aa3ff'))
            p.setOpacity(1.0)
            p.setPen(QPen(QColor('#68b6ff'), 1))
            p.drawRect(vx, bar_y, vw, self._BH - 1)

        # Playhead on overview
        ox = int(pl + self._pos_frac * uw)
        p.setPen(QPen(QColor('#f6fbff'), 1))
        p.drawLine(ox, bar_y, ox, bar_y + self._BH - 1)

        p.end()

    @staticmethod
    def _fmt_t(t):
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = t % 60
        if h:
            return f"{h}:{m:02d}:{int(s):02d}"
        if m:
            return f"{m}:{int(s):02d}"
        if s >= 1:
            return f"{int(s)}s"
        return f".{int(s * 100):02d}"


# ── Audio track panel ─────────────────────────────────────────────────────────

class AudioPanel(QGroupBox):
    changed = pyqtSignal(list)

    def __init__(self):
        super().__init__("Audio Tracks")
        self._tracks = []
        self._checks = []
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 12, 8, 8)
        self._layout.setSpacing(6)
        self._empty_label = QLabel("Open a video to inspect available audio tracks.")
        self._empty_label.setStyleSheet("color: #93a1b7;")
        self._empty_label.setWordWrap(True)
        self._layout.addWidget(self._empty_label)

    def load_tracks(self, tracks):
        self._tracks = [dict(track) for track in tracks]
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._checks = []

        if not self._tracks:
            self._empty_label = QLabel("Open a video to inspect available audio tracks.")
            self._empty_label.setStyleSheet("color: #93a1b7;")
            self._empty_label.setWordWrap(True)
            self._layout.addWidget(self._empty_label)
            return

        for index, track in enumerate(self._tracks, start=1):
            parts = [f"Track {index}"]
            if track.get("title"):
                parts.append(track["title"])
            if track.get("lang"):
                parts.append(f'[{track["lang"]}]')
            checkbox = QCheckBox("  ".join(parts))
            checkbox.setChecked(index == 1)
            checkbox.toggled.connect(self._emit_changed)
            self._checks.append((checkbox, track))
            self._layout.addWidget(checkbox)

        self._emit_changed()

    def enabled_tracks(self):
        enabled = [dict(track) for checkbox, track in self._checks if checkbox.isChecked()]
        if enabled:
            return enabled
        if self._checks:
            checkbox, track = self._checks[0]
            checkbox.setChecked(True)
            return [dict(track)]
        return []

    def _emit_changed(self):
        self.changed.emit(self.enabled_tracks())


# ── Trim panel ────────────────────────────────────────────────────────────────

class TrimPanel(QGroupBox):

    def __init__(self):
        super().__init__("Trim")
        self.in_pt = None
        self.out_pt = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 12, 8, 8)
        lay.setSpacing(8)

        self.lbl_in = QLabel("In:  --:--.--")
        self.lbl_out = QLabel("Out: --:--.--")
        mono = QFont("Consolas", 9)
        self.lbl_in.setFont(mono)
        self.lbl_out.setFont(mono)
        self.lbl_in.setMinimumWidth(110)
        self.lbl_out.setMinimumWidth(110)
        self.lbl_in.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.lbl_out.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.btn_exp = QPushButton("Export Trim…")
        self.btn_exp.setEnabled(False)

        lay.addWidget(self.lbl_in)
        lay.addWidget(self.lbl_out)
        lay.addStretch()
        lay.addWidget(self.btn_exp)

    @staticmethod
    def fmt(s):
        if s is None:
            return "--:--.--"
        return f"{int(s // 60):02d}:{int(s % 60):02d}.{int((s % 1) * 100):02d}"

    def set_in(self, t):
        self.in_pt = t
        self.lbl_in.setText(f"In:  {self.fmt(t)}")
        self._refresh()

    def set_out(self, t):
        self.out_pt = t
        self.lbl_out.setText(f"Out: {self.fmt(t)}")
        self._refresh()

    def _refresh(self):
        ok = (self.in_pt is not None
              and self.out_pt is not None
              and self.out_pt > self.in_pt)
        self.btn_exp.setEnabled(ok)

    def reset(self):
        self.in_pt = self.out_pt = None
        self.lbl_in.setText("In:  --:--.--")
        self.lbl_out.setText("Out: --:--.--")
        self._refresh()
# ── Helpers ───────────────────────────────────────────────────────────────────

def fmt_time(s):
    if s is None:
        return "0:00:00"
    return f"{int(s // 3600)}:{int((s % 3600) // 60):02d}:{int(s % 60):02d}"


def ffmpeg_exe():
    """
    Return the path to ffmpeg to use.
    Priority:
      1. install_dir\ffmpeg.exe  (normal installed location)
            2. next to the packaged app executable (portable / dev)
      3. resolved absolute ffmpeg.exe from PATH, excluding cwd and temp dirs
    """
    exe_dir = os.path.dirname(sys.executable if getattr(sys, 'frozen', False)
                              else os.path.abspath(__file__))
    for d in (get_install_dir(), exe_dir):
        f = os.path.join(d, 'ffmpeg.exe')
        if os.path.isfile(f):
            return f

    resolved = shutil.which('ffmpeg')
    if not resolved:
        return None
    resolved = os.path.abspath(resolved)
    blocked_roots = []
    try:
        blocked_roots.append(os.path.abspath(os.getcwd()))
    except Exception:
        pass
    try:
        blocked_roots.append(os.path.abspath(tempfile.gettempdir()))
    except Exception:
        pass
    for root in blocked_roots:
        try:
            if os.path.commonpath([resolved, root]) == root:
                return None
        except ValueError:
            continue
    if os.path.isfile(resolved):
        return resolved
    return None


def ffmpeg_available():
    try:
        exe = ffmpeg_exe()
        if not exe:
            return False
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        subprocess.run([exe, '-version'], capture_output=True,
                       creationflags=flags, timeout=5)
        return True
    except Exception:
        return False


def _normalize_release_tag(tag):
    cleaned = (tag or '').strip()
    if not cleaned:
        return ''
    if cleaned[0] in ('v', 'V'):
        cleaned = cleaned[1:]
    cleaned = cleaned.lstrip('.')
    return cleaned.lower()


def _is_newer_release(latest_tag, current_tag):
    latest_normalized = _normalize_release_tag(latest_tag)
    current_normalized = _normalize_release_tag(current_tag)
    return bool(latest_normalized) and latest_normalized != current_normalized


def _fetch_json(url):
    request = urllib.request.Request(url, headers=HTTP_HEADERS)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def latest_release_info():
    data = _fetch_json(LATEST_RELEASE_API)
    asset = None
    for item in data.get('assets', []):
        if item.get('name') == UPDATE_ASSET_NAME:
            asset = item
            break
    return {
        'tag_name': data.get('tag_name') or '',
        'name': data.get('name') or data.get('tag_name') or 'Latest Release',
        'body': data.get('body') or '',
        'html_url': data.get('html_url') or '',
        'published_at': data.get('published_at') or '',
        'asset_url': asset.get('browser_download_url') if asset else '',
    }


def runtime_executable_path():
    if getattr(sys, 'frozen', False):
        return os.path.abspath(sys.executable)
    return os.path.abspath(__file__)


def update_target_executables():
    """Get list of exe targets to update during installation.

    Note: We do NOT include sys.executable (the currently running exe)
    because Windows locks it while the process is running. Instead, we
    copy to lightframe.exe in the install dir, and let that exe handle
    the migration on next startup via _refresh_install().
    """
    install_dir = get_install_dir()
    targets = [
        os.path.abspath(os.path.join(install_dir, APP_EXE_NAME)),
        os.path.abspath(os.path.join(install_dir, LEGACY_APP_EXE_NAME)),
    ]
    # NOTE: Intentionally do NOT add runtime_executable_path() here
    # because it's currently locked and can't be overwritten.
    # Instead, we launch the new exe from install_dir, and on next
    # startup _refresh_install() will sync all copies.

    unique_targets = []
    seen = set()
    for target in targets:
        norm = os.path.normcase(os.path.abspath(target))
        if norm in seen:
            continue
        seen.add(norm)
        unique_targets.append(os.path.abspath(target))
    return unique_targets


class UpdateCheckWorker(QThread):
    done = pyqtSignal(object)
    error = pyqtSignal(str)

    def run(self):
        try:
            self.done.emit(latest_release_info())
        except urllib.error.HTTPError as exc:
            self.error.emit(f'GitHub update check failed: HTTP {exc.code}')
        except urllib.error.URLError as exc:
            self.error.emit(f'GitHub update check failed: {exc.reason}')
        except Exception as exc:
            self.error.emit(f'GitHub update check failed: {exc}')


class UpdateDownloadWorker(QThread):
    progress = pyqtSignal(int, str)
    done = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, release_info):
        super().__init__()
        self.release_info = dict(release_info)

    def run(self):
        asset_url = self.release_info.get('asset_url')
        if not asset_url:
            self.error.emit(f'The latest release does not include a {UPDATE_ASSET_NAME} asset.')
            return

        temp_path = None
        try:
            fd, temp_path = tempfile.mkstemp(prefix='lightframe_update_', suffix='.exe')
            os.close(fd)

            request = urllib.request.Request(asset_url, headers=HTTP_HEADERS)
            with urllib.request.urlopen(request, timeout=60) as response, \
                    open(temp_path, 'wb') as target:
                total_size = int(response.headers.get('Content-Length') or 0)
                downloaded = 0
                while True:
                    chunk = response.read(1024 * 256)
                    if not chunk:
                        break
                    target.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = min(100, int(downloaded * 100 / total_size))
                        self.progress.emit(percent, f'Downloading update… {percent}%')
                    else:
                        self.progress.emit(0, 'Downloading update…')

            if not os.path.isfile(temp_path) or os.path.getsize(temp_path) == 0:
                raise RuntimeError('Downloaded update is empty.')

            self.progress.emit(100, 'Download complete. Installing update…')
            self.done.emit(temp_path)
        except urllib.error.HTTPError as exc:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
            self.error.emit(f'Update download failed: HTTP {exc.code}')
        except urllib.error.URLError as exc:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
            self.error.emit(f'Update download failed: {exc.reason}')
        except Exception as exc:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
            self.error.emit(f'Update download failed: {exc}')


# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("LightFrame (Test Update v.1.10)")
        self.resize(980, 660)
        self.setMinimumSize(700, 480)
        self.setAcceptDrops(True)

        self.src_file      = None
        self.duration      = 0.0
        self.seeking       = False
        self._seek_target  = None   # expected position after seek (seconds)
        self._worker       = None
        self._tracks_file  = None   # which file the track panel is populated for
        self._thumbs_available = ffmpeg_available()
        self._thumbnail_cache_owner = tempfile.TemporaryDirectory(prefix='lightframe-thumbs-')
        self._thumbnail_cache_dir = self._thumbnail_cache_owner.name
        self._thumbnail_cache = {}
        self._thumbnail_cache_prefix = 'empty'
        self._thumbnail_request = None
        self._thumbnail_active_key = None
        self._thumbnail_worker = None
        self._thumbnail_popup = ThumbnailPopup()
        self._update_check_worker = None
        self._update_download_worker = None
        self._update_progress = None
        self._pending_update_release = None

        self._build_ui()
        self._build_menu()
        self._build_shortcuts()
        self._setup_player()

        self._timer = QTimer(self)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        self._mix_timer = QTimer(self)
        self._mix_timer.setSingleShot(True)
        self._mix_timer.setInterval(250)   # debounce audio mix changes
        self._mix_timer.timeout.connect(self._apply_audio_mix_now)
        self._pending_mix = []

        self._thumbnail_timer = QTimer(self)
        self._thumbnail_timer.setSingleShot(True)
        self._thumbnail_timer.setInterval(120)
        self._thumbnail_timer.timeout.connect(self._process_thumbnail_request)

        self.setStyleSheet(get_style())

        # Restore window geometry from last session
        settings = QSettings("Anthropic", "LightFrame")
        if settings.contains("window_geometry"):
            self.restoreGeometry(settings.value("window_geometry"))
        if settings.contains("window_state"):
            self.restoreState(settings.value("window_state"))

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setSpacing(5)
        outer.setContentsMargins(6, 6, 6, 6)

        center = QWidget()
        vbox = QVBoxLayout(center)
        vbox.setSpacing(5)
        vbox.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(center, 1)

        # Video area
        self.video_widget = QWidget()
        self.video_widget.setStyleSheet("background: #050608; border: 1px solid #202833;")
        self.video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_widget.setMinimumSize(480, 270)
        self.video_widget.setAttribute(Qt.WA_NativeWindow)   # ensure HWND exists
        vbox.addWidget(self.video_widget, 1)

        # Seek bar
        row_seek = QHBoxLayout()
        row_seek.setSpacing(8)
        mono9 = QFont("Consolas", 9)
        self.lbl_pos = QLabel("0:00:00"); self.lbl_pos.setFont(mono9); self.lbl_pos.setMinimumWidth(64)
        self.lbl_pos.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_dur = QLabel("0:00:00"); self.lbl_dur.setFont(mono9); self.lbl_dur.setMinimumWidth(64)
        self.lbl_dur.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.seek = SeekSlider()
        self.seek.drag_start.connect(self._seek_pressed)
        self.seek.scrubbing.connect(self._seek_scrubbing)
        self.seek.seek_to.connect(self._seek_released)
        self.seek.zoom_changed.connect(self._on_zoom_changed)
        self.seek.drag_preview.connect(self._queue_seek_thumbnail)
        self.seek.preview_hidden.connect(self._hide_seek_thumbnail)
        self.lbl_zoom = QLabel("1×")
        self.lbl_zoom.setFont(mono9)
        self.lbl_zoom.setMinimumWidth(38)
        self.lbl_zoom.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_zoom.setStyleSheet("color: #93a1b7;")
        self.btn_zoom_reset = QPushButton("⊙")
        self.btn_zoom_reset.setMaximumWidth(28)
        self.btn_zoom_reset.setToolTip("Reset zoom  (scroll wheel on the seek bar to zoom)")
        self.btn_zoom_reset.clicked.connect(lambda: self.seek.reset_zoom())
        row_seek.addWidget(self.lbl_pos)
        row_seek.addWidget(self.seek)
        row_seek.addWidget(self.lbl_dur)
        row_seek.addWidget(self.lbl_zoom)
        row_seek.addWidget(self.btn_zoom_reset)
        vbox.addLayout(row_seek)

        # Playback controls
        row_ctrl = QHBoxLayout()
        row_ctrl.setSpacing(8)
        self.btn_open = QPushButton("Open…");  self.btn_open.clicked.connect(self.open_file)
        self.btn_play = QPushButton("Play");   self.btn_play.clicked.connect(self.toggle_play);  self.btn_play.setEnabled(False)
        self.btn_stop = QPushButton("Stop");   self.btn_stop.clicked.connect(self.stop);         self.btn_stop.setEnabled(False)
        self.sld_vol  = QSlider(Qt.Horizontal); self.sld_vol.setRange(0, 150); self.sld_vol.setValue(100); self.sld_vol.setMaximumWidth(110)
        self.sld_vol.valueChanged.connect(self._set_volume)
        self.lbl_vol  = QLabel("Volume:");
        self.lbl_vol.setMinimumWidth(58)
        self.lbl_vol.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.btn_in = QPushButton("Set In")
        self.btn_out = QPushButton("Set Out")
        self.btn_in.setMinimumWidth(72)
        self.btn_out.setMinimumWidth(72)
        self.lbl_volpct = QLabel("100%"); self.lbl_volpct.setMinimumWidth(44)
        self.lbl_volpct.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        for w in (self.btn_open, self.btn_play, self.btn_stop):
            row_ctrl.addWidget(w)
        row_ctrl.addStretch()
        row_ctrl.addWidget(self.lbl_vol)
        row_ctrl.addWidget(self.sld_vol)
        row_ctrl.addWidget(self.btn_in)
        row_ctrl.addWidget(self.btn_out)
        row_ctrl.addWidget(self.lbl_volpct)
        vbox.addLayout(row_ctrl)

        # Audio tracks
        self.audio_panel = AudioPanel()
        self.audio_panel.setMaximumHeight(130)
        self.audio_panel.changed.connect(self._apply_audio_mix)
        vbox.addWidget(self.audio_panel)

        # Trim
        self.trim_panel = TrimPanel()
        self.trim_panel.btn_exp.clicked.connect(self._export)
        self.btn_in.clicked.connect(self._set_in)
        self.btn_out.clicked.connect(self._set_out)
        vbox.addWidget(self.trim_panel)

        # Status bar
        self.sb = QStatusBar()
        self.setStatusBar(self.sb)
        self.sb.showMessage(
            "Open a video  —  Space: play/pause  |  I / O: set trim points  |  ← →: seek  |  ↑ ↓: volume"
        )
        self.lbl_build = QLabel(APP_VERSION)
        self.lbl_build.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_build.setStyleSheet("color: #93a1b7;")
        self.lbl_build.setToolTip(runtime_executable_path())
        self.sb.addPermanentWidget(self.lbl_build)

    def _build_menu(self):
        mb = self.menuBar()
        fm = mb.addMenu("File")
        fm.addAction(QAction("Open…", self, shortcut="Ctrl+O", triggered=self.open_file))
        fm.addSeparator()
        fm.addAction(QAction("Quit",  self, shortcut="Ctrl+Q", triggered=self.close))

        hm = mb.addMenu("Help")
        hm.addAction(QAction("Check for Updates…", self, triggered=self._check_for_updates))
        hm.addSeparator()

        # Theme toggle
        current_theme = get_theme()
        self._theme_action = QAction(
            "☀ Light Mode" if current_theme == "dark" else "🌙 Dark Mode",
            self,
            triggered=self._toggle_theme
        )
        hm.addAction(self._theme_action)
        hm.addSeparator()

        hm.addAction(QAction("Uninstall LightFrame…", self, triggered=self._uninstall))

    def _check_for_updates(self):
        if self._update_check_worker and self._update_check_worker.isRunning():
            return
        self.sb.showMessage('Checking GitHub for updates…')
        self._update_check_worker = UpdateCheckWorker()
        self._update_check_worker.done.connect(self._update_check_done)
        self._update_check_worker.error.connect(self._update_check_failed)
        self._update_check_worker.start()

    def _update_check_done(self, release_info):
        self._update_check_worker = None
        latest_tag = release_info.get('tag_name') or ''
        asset_url = release_info.get('asset_url') or ''

        if not latest_tag:
            self.sb.showMessage('Update check failed.')
            QMessageBox.warning(self, 'Check for Updates',
                                'GitHub did not return a valid latest release tag.')
            return

        if not _is_newer_release(latest_tag, APP_VERSION):
            self.sb.showMessage('LightFrame is up to date.')
            QMessageBox.information(
                self,
                'Check for Updates',
                f'You already have the newest version.\n\nCurrent version: {APP_VERSION}',
            )
            return

        if not asset_url:
            self.sb.showMessage(f'Latest release is missing {UPDATE_ASSET_NAME}.')
            QMessageBox.warning(
                self,
                'Check for Updates',
                f'A newer release exists ({latest_tag}), but it does not include {UPDATE_ASSET_NAME}.',
            )
            return

        if not getattr(sys, 'frozen', False) or sys.platform != 'win32':
            self.sb.showMessage(f'Update available: {latest_tag}')
            QMessageBox.information(
                self,
                'Update Available',
                f'A newer release is available.\n\nCurrent version: {APP_VERSION}\nLatest version: {latest_tag}\n\n'
                'Self-update is only available in the packaged Windows build.',
            )
            return

        reply = QMessageBox.question(
            self,
            'Update Available',
            f'A newer release is available.\n\nCurrent version: {APP_VERSION}\n'
            f'Latest version: {latest_tag}\n\nDownload and install it now?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            self.sb.showMessage('Update cancelled.')
            return

        self._pending_update_release = dict(release_info)
        self._start_update_download()

    def _update_check_failed(self, message):
        self._update_check_worker = None
        self.sb.showMessage('Update check failed.')
        QMessageBox.warning(self, 'Check for Updates', message)

    def _show_update_progress(self, message):
        self._close_update_progress()
        self._update_progress = QProgressDialog(message, '', 0, 0, self)
        self._update_progress.setWindowTitle('LightFrame Update')
        self._update_progress.setWindowModality(Qt.ApplicationModal)
        self._update_progress.setCancelButton(None)
        self._update_progress.setMinimumDuration(0)
        self._update_progress.setAutoClose(False)
        self._update_progress.setAutoReset(False)
        self._update_progress.setStyleSheet(get_style())
        self._update_progress.show()

    def _close_update_progress(self):
        if self._update_progress is not None:
            self._update_progress.close()
            self._update_progress.deleteLater()
            self._update_progress = None

    def _start_update_download(self):
        if self._update_download_worker and self._update_download_worker.isRunning():
            return
        self._show_update_progress('Downloading update…')
        self._update_download_worker = UpdateDownloadWorker(self._pending_update_release)
        self._update_download_worker.progress.connect(self._update_download_progress)
        self._update_download_worker.done.connect(self._update_download_done)
        self._update_download_worker.error.connect(self._update_download_failed)
        self._update_download_worker.start()

    def _update_download_progress(self, percent, message):
        if self._update_progress is None:
            return
        self._update_progress.setLabelText(message)
        if percent > 0 and self._update_progress.maximum() == 0:
            self._update_progress.setRange(0, 100)
        if self._update_progress.maximum() > 0:
            self._update_progress.setValue(percent)

    def _update_download_done(self, downloaded_exe):
        self._update_download_worker = None
        self._close_update_progress()
        try:
            self._apply_downloaded_update(downloaded_exe)
        except Exception as exc:
            if os.path.exists(downloaded_exe):
                os.unlink(downloaded_exe)
            self.sb.showMessage('Update install failed.')
            QMessageBox.critical(self, 'Update Failed', f'Could not install the update.\n\n{exc}')

    def _update_download_failed(self, message):
        self._update_download_worker = None
        self._close_update_progress()
        self.sb.showMessage('Update download failed.')
        QMessageBox.warning(self, 'Update Failed', message)

    def _apply_downloaded_update(self, downloaded_exe):
        if not os.path.isfile(downloaded_exe):
            raise RuntimeError('Downloaded update file was not found.')

        # Launch the updater exe (LightframeUpdate.exe)
        # It will handle the installation/update process
        subprocess.Popen([downloaded_exe])

        self.sb.showMessage('Update installer launched.')
        self.close()  # Close the app so updater can replace it

    def _uninstall(self):
        reply = QMessageBox.question(
            self, "Uninstall LightFrame",
            "This will:\n"
            "  • Remove the right-click menu entries\n"
            "  • Delete the Desktop shortcut\n"
            "  • Delete ffmpeg.exe, the setup marker, and this exe\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        cur_exe = os.path.abspath(sys.executable)

        # 1. Remove registry context-menu entries + App Paths
        if sys.platform == 'win32':
            try:
                import winreg
                VIDEO_EXTS = [
                    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv',
                    '.webm', '.m4v', '.mpg', '.mpeg', '.ts', '.m2ts',
                    '.3gp', '.mxf', '.vob', '.ogv',
                ]
                for ext in VIDEO_EXTS:
                    key_path = rf'Software\Classes\{ext}\shell\Open with LightFrame'
                    for sub in (r'\command', ''):
                        try:
                            winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                                             key_path + sub)
                        except OSError:
                            pass
                # Remove App Paths entry
                try:
                    winreg.DeleteKey(
                        winreg.HKEY_CURRENT_USER,
                        r'Software\Microsoft\Windows\CurrentVersion'
                        fr'\App Paths\{APP_EXE_NAME}')
                except OSError:
                    pass
                try:
                    winreg.DeleteKey(
                        winreg.HKEY_CURRENT_USER,
                        r'Software\Microsoft\Windows\CurrentVersion'
                        fr'\App Paths\{LEGACY_APP_EXE_NAME}')
                except OSError:
                    pass
            except Exception:
                pass

        # 2. Delete Desktop + Start Menu shortcuts
        try:
            desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
            for lnk in [os.path.join(desktop, 'LightFrame.lnk'),
                        os.path.join(os.environ.get('APPDATA', ''),
                                     r'Microsoft\Windows\Start Menu\Programs',
                                     'LightFrame.lnk')]:
                if os.path.isfile(lnk):
                    os.unlink(lnk)
        except Exception:
            pass

        # 3. Write a %TEMP% cleanup script; use cmd.exe (no execution-policy
        #    issues) to wait then delete only app-owned files.
        if sys.platform == 'win32':
            install_dir = os.path.abspath(get_install_dir())
            inst_exe = os.path.abspath(os.path.join(install_dir, APP_EXE_NAME))
            legacy_inst_exe = os.path.abspath(os.path.join(install_dir, LEGACY_APP_EXE_NAME))

            if (os.path.basename(install_dir).lower() == 'lightframe'
                    and os.path.commonpath([inst_exe, install_dir]) == install_dir):
                fd, tmp_bat = tempfile.mkstemp(prefix='lightedge_uninstall_', suffix='.bat')
                os.close(fd)
                bat_lines = ['@echo off', 'ping 127.0.0.1 -n 4 >nul']

                exe_esc = inst_exe.replace('"', '')
                bat_lines += [
                    ':retry_exe',
                    f'del /f /q "{exe_esc}" >nul 2>&1',
                    f'if exist "{exe_esc}" (',
                    '  ping 127.0.0.1 -n 2 >nul',
                    '  goto retry_exe',
                    ')',
                ]

                legacy_exe_esc = legacy_inst_exe.replace('"', '')
                if legacy_inst_exe.lower() != inst_exe.lower():
                    bat_lines.append(f'del /f /q "{legacy_exe_esc}" >nul 2>&1')

                for file_path in (
                    os.path.join(install_dir, 'ffmpeg.exe'),
                    os.path.join(install_dir, 'icon.png'),
                    os.path.join(install_dir, '.lightedge_setup_done'),
                ):
                    file_esc = file_path.replace('"', '')
                    bat_lines.append(f'del /f /q "{file_esc}" >nul 2>&1')

                dir_esc = install_dir.replace('"', '')
                # Remove the entire LightFrame directory and all its contents
                bat_lines.append(f'rd /s /q "{dir_esc}" >nul 2>&1')

                if cur_exe.lower() != inst_exe.lower() and os.path.isfile(cur_exe):
                    cur_esc = cur_exe.replace('"', '')
                    bat_lines.append(f'del /f /q "{cur_esc}" >nul 2>&1')

                bat_lines.append('del /f /q "%~f0" >nul 2>&1')

                with open(tmp_bat, 'w', encoding='utf-8', newline='\r\n') as f:
                    f.write('\r\n'.join(bat_lines))

                subprocess.Popen(
                    ['cmd.exe', '/c', tmp_bat],
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
                )

        QMessageBox.information(self, "Uninstall LightFrame",
                                "LightFrame has been uninstalled.")
        self.close()

    def _toggle_theme(self):
        current = get_theme()
        new_theme = "light" if current == "dark" else "dark"
        set_theme(QApplication.instance(), self, new_theme)
        self._theme_action.setText(
            "🌙 Dark Mode" if new_theme == "light" else "☀ Light Mode"
        )

    def _build_shortcuts(self):
        def sc(key, fn):
            QShortcut(QKeySequence(key), self, fn)
        sc("Space",       self.toggle_play)
        sc("I",           self._set_in)
        sc("O",           self._set_out)
        sc("Left",        lambda: self._seek_rel(-5))
        sc("Right",       lambda: self._seek_rel(5))
        sc("Shift+Left",  lambda: self._seek_rel(-1 / 30))
        sc("Shift+Right", lambda: self._seek_rel(1 / 30))
        sc("Up",          lambda: self._adj_vol(5))
        sc("Down",        lambda: self._adj_vol(-5))
        sc("=",           lambda: self.seek.zoom_step(1.25))
        sc("+",           lambda: self.seek.zoom_step(1.25))
        sc("-",           lambda: self.seek.zoom_step(1 / 1.25))
        sc("0",           lambda: self.seek.reset_zoom())

    # ── MPV setup ─────────────────────────────────────────────────────────────

    def _setup_player(self):
        self.player = None
        if not MPV_AVAILABLE:
            return
        try:
            wid = str(int(self.video_widget.winId()))
            self.player = mpv.MPV(
                wid=wid,
                keep_open='yes',
                keep_open_pause='yes',
                idle='yes',
                osc='no',
                input_default_bindings='no',
                input_vo_keyboard='no',
            )
            self.player.observe_property('track-list', self._cb_tracks)
        except Exception as exc:
            self.player = None
            self.sb.showMessage(f"MPV init failed: {exc}")

    # ── MPV property callback (runs on MPV thread — post to UI thread) ─────────

    def _cb_tracks(self, _name, tracks):
        # Only act if this is a new file — ignore track-list updates triggered
        # by lavfi-complex changes during normal playback (that caused the loop).
        if not tracks or self._tracks_file == self.src_file:
            return
        QTimer.singleShot(0, self._read_tracks)

    def _read_tracks(self):
        """Read track-list and populate the panel. Runs at most once per file."""
        if not self.player or not self.src_file:
            return
        if self._tracks_file == self.src_file:
            return   # already loaded for this file
        try:
            raw = self.player.track_list
        except Exception:
            return
        if not raw:
            return
        audio, ai = [], 0
        for t in raw:
            if t.get('type') == 'audio':
                audio.append({
                    'mpv_id':       t.get('id'),
                    'ffmpeg_index': ai,
                    'title':        t.get('title', ''),
                    'lang':         t.get('lang',  ''),
                })
                ai += 1
        if audio:
            self._tracks_file = self.src_file   # mark as loaded BEFORE applying mix
            self.audio_panel.load_tracks(audio)
            # Apply initial default selection after a short delay
            QTimer.singleShot(300, lambda: self._apply_audio_mix(
                self.audio_panel.enabled_tracks()))

    # ── Polling timer ──────────────────────────────────────────────────────────

    def _tick(self):
        if not self.player:
            return
        try:
            pos    = self.player.time_pos
            dur    = self.player.duration
            paused = self.player.pause
            if dur:
                self.duration = dur
            self.lbl_pos.setText(fmt_time(pos))
            self.lbl_dur.setText(fmt_time(dur))
            if dur and pos is not None:
                if self.seeking:
                    # Auto-clear seeking once MPV has reached the target
                    if (self._seek_target is not None
                            and abs(pos - self._seek_target) < 0.5):
                        self._clear_seeking()
                else:
                    frac = pos / dur
                    # Auto-scroll: keep playhead inside the visible window
                    if self.seek._zoom > 1.001:
                        vs = self.seek._view_start
                        vw = self.seek._window
                        if not (vs <= frac <= vs + vw):
                            self.seek.set_view(frac - vw / 2)
                    self.seek.set_pos_frac(frac)
                    self.seek.set_duration(dur)
            self.btn_play.setText("Pause" if not paused else "Play")
        except Exception:
            pass

    # ── File loading ───────────────────────────────────────────────────────────

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Video", "",
            "Video files (*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm "
            "*.ts *.m2ts *.mts *.m4v);;All files (*)",
        )
        if path:
            self._load(path)

    def _load(self, path):
        if not self.player:
            QMessageBox.warning(
                self, "Player unavailable",
                "MPV is not initialised.\n"
                "Make sure python-mpv is installed and mpv-2.dll is present.",
            )
            return
        self.src_file     = path
        self._tracks_file = None   # reset so tracks reload for the new file
        self._thumbnail_cache_prefix = str(abs(hash(os.path.abspath(path))))
        self._thumbnail_cache.clear()
        self._hide_seek_thumbnail()
        self.trim_panel.reset()
        self.seek.clear_markers()
        self.audio_panel.load_tracks([])   # clear old tracks immediately
        self.player.play(path)
        self.btn_play.setEnabled(True)
        self.btn_stop.setEnabled(True)
        self.setWindowTitle(f"LightFrame — {os.path.basename(path)}")
        self.sb.showMessage(path)
        # Give MPV time to open & parse the file, then read the track list.
        QTimer.singleShot(800, self._read_tracks)
        QTimer.singleShot(2000, self._read_tracks)  # second attempt for slow files

    # ── Playback ───────────────────────────────────────────────────────────────

    def toggle_play(self):
        if self.player:
            self.player.pause = not self.player.pause

    def stop(self):
        if not self.player:
            return
        self.player.stop()
        self.seek.set_pos_frac(0.0)
        self.lbl_pos.setText("0:00:00")
        self.btn_play.setText("Play")

    def _seek_pressed(self):
        """Called on mouse-down: lock slider so _tick can't overwrite it."""
        self._hide_seek_thumbnail()
        self.seeking = True
        self._seek_target = None

    def _seek_scrubbing(self, v):
        """Live label update while dragging — no MPV seek yet."""
        if self.duration:
            self.lbl_pos.setText(fmt_time(v / 10000 * self.duration))

    def _seek_released(self, v):
        """Mouse released — send seek to MPV, wait for convergence in _tick."""
        if not self.player or not self.duration:
            self.seeking = False
            return
        self._seek_target = max(0.0, min(v / 10000 * self.duration, self.duration))
        try:
            # Set time_pos directly — most reliable in python-mpv
            self.player.time_pos = self._seek_target
        except Exception:
            pass
        # Hard timeout: clear seeking after 2s no matter what
        QTimer.singleShot(2000, self._clear_seeking)

    def _clear_seeking(self):
        self.seeking = False
        self._seek_target = None

    def _seek_rel(self, dt):
        if self.player:
            try:
                cur = self.player.time_pos or 0.0
                self.player.time_pos = max(0.0, min(cur + dt, self.duration))
            except Exception:
                pass

    def _set_volume(self, v):
        if self.player:
            self.player.volume = v
        self.lbl_volpct.setText(f"{v}%")

    def _adj_vol(self, dv):
        self.sld_vol.setValue(max(0, min(150, self.sld_vol.value() + dv)))

    def _on_zoom_changed(self, zoom):
        self.lbl_zoom.setText("1×" if zoom <= 1.001 else f"{zoom:.1f}×")

    def _queue_seek_thumbnail(self, seconds, global_pos):
        if not self._thumbs_available or not self.src_file or not self.duration:
            return
        self._thumbnail_request = (seconds, global_pos)
        cache_key, rounded = self._thumbnail_key(seconds)
        cached_path = self._thumbnail_cache.get(cache_key)
        if cached_path and os.path.isfile(cached_path):
            self._show_seek_thumbnail(cached_path, rounded, global_pos)
            return
        self._thumbnail_timer.start()

    def _thumbnail_key(self, seconds):
        rounded = round(max(0.0, min(seconds, self.duration)) * 2.0) / 2.0
        return f'{self._thumbnail_cache_prefix}_{rounded:.1f}', rounded

    def _process_thumbnail_request(self):
        if not self._thumbnail_request or not self.src_file:
            return
        seconds, global_pos = self._thumbnail_request
        cache_key, rounded = self._thumbnail_key(seconds)
        cached_path = self._thumbnail_cache.get(cache_key)
        if cached_path and os.path.isfile(cached_path):
            self._show_seek_thumbnail(cached_path, rounded, global_pos)
            return
        if self._thumbnail_active_key == cache_key:
            return
        if self._thumbnail_worker and self._thumbnail_worker.isRunning():
            return

        out_path = os.path.join(
            self._thumbnail_cache_dir,
            f'{cache_key.replace(".", "_")}.png',
        )
        self._thumbnail_active_key = cache_key
        self._thumbnail_worker = ThumbnailWorker(self.src_file, out_path, rounded, cache_key)
        self._thumbnail_worker.done.connect(self._thumbnail_ready)
        self._thumbnail_worker.error.connect(self._thumbnail_failed)
        self._thumbnail_worker.start()

    def _thumbnail_ready(self, cache_key, path, seconds, src_path):
        self._thumbnail_active_key = None
        if src_path != self.src_file:
            return
        self._thumbnail_cache[cache_key] = path
        if self._thumbnail_request is not None:
            req_seconds, req_pos = self._thumbnail_request
            req_key, req_rounded = self._thumbnail_key(req_seconds)
            if req_key == cache_key:
                self._show_seek_thumbnail(path, req_rounded, req_pos)
            else:
                self._thumbnail_timer.start()

    def _thumbnail_failed(self, cache_key, _msg, src_path):
        self._thumbnail_active_key = None
        if src_path == self.src_file and self._thumbnail_request is not None:
            req_seconds, _req_pos = self._thumbnail_request
            req_key, _ = self._thumbnail_key(req_seconds)
            if req_key != cache_key:
                self._thumbnail_timer.start()

    def _show_seek_thumbnail(self, path, seconds, global_pos):
        self._thumbnail_popup.set_thumbnail(path, fmt_time(seconds))
        self._thumbnail_popup.move_above(global_pos)
        self._thumbnail_popup.show()

    def _hide_seek_thumbnail(self):
        self._thumbnail_timer.stop()
        self._thumbnail_request = None
        self._thumbnail_popup.hide()

    # ── Multi-audio mixing ─────────────────────────────────────────────────────

    def _apply_audio_mix(self, enabled):
        """Debounce: store the pending selection and restart the timer."""
        self._pending_mix = enabled
        self._mix_timer.start()   # restarts if already running

    def _apply_audio_mix_now(self):
        """
        Commit the audio mix to MPV.
        Single track  -> anull passthrough (avoids amix=inputs=1 quirks).
        Multiple tracks -> amix.
        Always clears the filter first so MPV re-builds the graph cleanly.
        """
        enabled = self._pending_mix
        if not self.player or not enabled:
            return
        # Don't touch the filter while the file is still opening
        try:
            if self.player.time_pos is None and not self.player.pause:
                self._mix_timer.start()   # retry shortly
                return
        except Exception:
            return
        try:
            n = len(enabled)
            if n == 1:
                filt = f'[aid{enabled[0]["mpv_id"]}]anull[ao]'
            else:
                aids = ''.join(f'[aid{t["mpv_id"]}]' for t in enabled)
                filt = f'{aids}amix=inputs={n}:normalize=0:duration=longest[ao]'
            # Clear the old graph first so MPV doesn't try to patch it
            self.player['lavfi-complex'] = ''
            self.player['lavfi-complex'] = filt
        except Exception as exc:
            self.sb.showMessage(f"Audio mix error: {exc}")

    # ── Trim ───────────────────────────────────────────────────────────────────

    def _cur_pos(self):
        if not self.player:
            return None
        try:
            return self.player.time_pos
        except Exception:
            return None

    def _set_in(self):
        t = self._cur_pos()
        if t is None:
            return
        self.trim_panel.set_in(t)
        self._refresh_markers()
        self.sb.showMessage(f"In point:  {TrimPanel.fmt(t)}")

    def _set_out(self):
        t = self._cur_pos()
        if t is None:
            return
        self.trim_panel.set_out(t)
        self._refresh_markers()
        self.sb.showMessage(f"Out point: {TrimPanel.fmt(t)}")

    def _refresh_markers(self):
        if not self.duration:
            return
        ip = self.trim_panel.in_pt
        op = self.trim_panel.out_pt
        self.seek.set_markers(
            ip / self.duration if ip is not None else None,
            op / self.duration if op is not None else None,
        )

    def _export(self):
        if not self.src_file:
            return
        ip = self.trim_panel.in_pt
        op = self.trim_panel.out_pt
        if ip is None or op is None or op <= ip:
            QMessageBox.warning(self, "Invalid trim", "Set valid In / Out points first.")
            return

        base, _ext = os.path.splitext(self.src_file)
        default_dst = f"{base}_trim.mp4"
        dst, _ = QFileDialog.getSaveFileName(
            self, "Save trimmed clip", default_dst,
            "MP4 (*.mp4);;MKV (*.mkv);;All files (*)",
        )
        if not dst:
            return

        enabled = self.audio_panel.enabled_tracks()
        self.trim_panel.btn_exp.setEnabled(False)
        self.sb.showMessage("Exporting…")
        self._show_export_progress(dst)

        self._worker = TrimWorker(self.src_file, dst, ip, op, enabled)
        self._worker.done.connect(self._export_done)
        self._worker.error.connect(self._export_error)
        self._worker.start()

    def _show_export_progress(self, path):
        self._export_progress = QProgressDialog(
            "Exporting your clip. Do not close the app until this finishes.",
            "",
            0,
            0,
            self,
        )
        self._export_progress.setWindowTitle("Export in progress")
        self._export_progress.setWindowModality(Qt.ApplicationModal)
        self._export_progress.setCancelButton(None)
        self._export_progress.setMinimumDuration(0)
        self._export_progress.setAutoClose(False)
        self._export_progress.setAutoReset(False)
        self._export_progress.setStyleSheet(STYLE)
        self._export_progress.setValue(0)
        self._export_progress.setLabelText(
            f"Exporting to:\n{path}\n\nDo not close the app until the export is complete."
        )
        self._export_progress.show()

    def _close_export_progress(self):
        dialog = getattr(self, "_export_progress", None)
        if dialog is not None:
            dialog.close()
            dialog.deleteLater()
            self._export_progress = None

    def _export_done(self, path):
        self._close_export_progress()
        self.trim_panel.btn_exp.setEnabled(True)
        self.sb.showMessage(f"Exported → {path}")
        QMessageBox.information(self, "Export complete", f"Saved:\n{path}")

    def _export_error(self, msg):
        self._close_export_progress()
        self.trim_panel.btn_exp.setEnabled(True)
        self.sb.showMessage("Export failed.")
        QMessageBox.critical(self, "Export error", msg)

    # ── Drag & drop ───────────────────────────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            self._load(urls[0].toLocalFile())

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        # Save window geometry and state
        settings = QSettings("Anthropic", "LightFrame")
        settings.setValue("window_geometry", self.saveGeometry())
        settings.setValue("window_state", self.saveState())
        self._hide_seek_thumbnail()
        try:
            self._thumbnail_cache_owner.cleanup()
        except Exception:
            pass
        if self.player:
            try:
                self.player.terminate()
            except Exception:
                pass
        event.accept()


# ── First-run setup ───────────────────────────────────────────────────────────

class SetupDialog(QWidget):
    """Two-phase installer: location picker, then FFmpeg download."""
    finished = pyqtSignal()

    _APPDATA_ITEM = "AppData (recommended)"
    _PROGFILES_ITEM = r"C:\Program Files\LightFrame"
    _CUSTOM_ITEM = "Custom…"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("LightFrame — Setup")
        self.setFixedSize(480, 310)
        self.setStyleSheet(get_style())
        self._install_dir = None
        self._want_shortcut = True
        self._thread = None
        self._worker = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Phase 0: Picker page
        self._picker_page = QWidget()
        self._build_picker_ui()
        outer.addWidget(self._picker_page)

        # Phase 1: Progress page
        self._progress_page = QWidget()
        self._build_progress_ui()
        outer.addWidget(self._progress_page)
        self._progress_page.setVisible(False)

    def _build_picker_ui(self):
        lay = QVBoxLayout(self._picker_page)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(10)

        title = QLabel("Install LightFrame")
        title.setStyleSheet("font-size: 11pt; font-weight: bold; color: #e7edf7;")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        subtitle = QLabel("Choose where to install LightFrame.")
        subtitle.setStyleSheet("color: #93a1b7;")
        subtitle.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        loc_label = QLabel("Install location")
        loc_label.setStyleSheet("font-weight: bold; color: #d4e4fa;")

        self._combo = QComboBox()
        self._combo.addItems([
            self._APPDATA_ITEM,
            self._PROGFILES_ITEM,
            self._CUSTOM_ITEM,
        ])
        self._combo.currentIndexChanged.connect(self._on_combo_changed)

        # Custom path row (hidden initially)
        custom_lay = QHBoxLayout()
        self._custom_edit = QLineEdit()
        self._custom_edit.setText(_DEFAULT_INSTALL_DIR)
        browse_btn = QPushButton("Browse…")
        browse_btn.setMaximumWidth(100)
        browse_btn.clicked.connect(self._on_browse)
        custom_lay.addWidget(self._custom_edit)
        custom_lay.addWidget(browse_btn)
        self._custom_row = QWidget()
        self._custom_row.setLayout(custom_lay)
        self._custom_row.setVisible(False)

        # Warning label for Program Files
        self._warning_lbl = QLabel("Note: Program Files may require administrator rights.")
        self._warning_lbl.setStyleSheet("color: #ff9f43; font-size: 8pt;")
        self._warning_lbl.setVisible(False)

        # Desktop shortcut checkbox
        self._shortcut_cb = QCheckBox("Create Desktop shortcut")
        self._shortcut_cb.setChecked(True)

        # Install button
        self._install_btn = QPushButton("Install")
        self._install_btn.setMinimumWidth(100)
        self._install_btn.clicked.connect(self._on_install_clicked)

        lay.addWidget(title)
        lay.addWidget(subtitle)
        lay.addSpacing(10)
        lay.addWidget(loc_label)
        lay.addWidget(self._combo)
        lay.addWidget(self._custom_row)
        lay.addWidget(self._warning_lbl)
        lay.addSpacing(5)
        lay.addWidget(self._shortcut_cb)
        lay.addStretch()
        lay.addWidget(self._install_btn, alignment=Qt.AlignRight)

    def _on_combo_changed(self):
        idx = self._combo.currentIndex()
        if idx == 2:  # Custom
            self._custom_row.setVisible(True)
            self._warning_lbl.setVisible(False)
        elif idx == 1:  # Program Files
            self._custom_row.setVisible(False)
            self._warning_lbl.setVisible(True)
        else:  # AppData
            self._custom_row.setVisible(False)
            self._warning_lbl.setVisible(False)

    def _on_browse(self):
        path = QFileDialog.getExistingDirectory(self, "Choose install location")
        if path:
            self._custom_edit.setText(path)

    def _on_install_clicked(self):
        idx = self._combo.currentIndex()
        if idx == 0:
            chosen = _DEFAULT_INSTALL_DIR
        elif idx == 1:
            chosen = self._PROGFILES_ITEM
        else:
            chosen = self._custom_edit.text().strip()
            if not chosen:
                QMessageBox.warning(self, "Setup", "Please enter or browse to an install location.")
                return

        # Check if Program Files is selected and needs elevation
        if idx == 1:
            reply = QMessageBox.question(
                self,
                "Administrator Access Required",
                f"Installing to Program Files requires administrator privileges.\n\n"
                f"LightFrame will request elevated permissions to proceed.\n\n"
                f"Click 'OK' to continue with the administrator prompt.",
                QMessageBox.Ok | QMessageBox.Cancel,
                QMessageBox.Ok
            )
            if reply != QMessageBox.Ok:
                return

        # Test writability
        try:
            os.makedirs(chosen, exist_ok=True)
            probe = os.path.join(chosen, '.write_test')
            with open(probe, 'w') as f:
                f.write('test')
            os.unlink(probe)
        except OSError as e:
            # If Program Files and no write access, suggest elevation
            if idx == 1:
                QMessageBox.critical(
                    self, "Access Denied",
                    f"Unable to write to Program Files.\n\n"
                    f"Please run this installer as Administrator and try again.\n\n"
                    f"Error: {e}")
            else:
                QMessageBox.warning(
                    self, "Cannot write to that location",
                    f"LightFrame cannot write to:\n  {chosen}\n\n"
                    f"Choose a different location or check permissions.\n\n{e}")
            return

        self._install_dir = chosen
        self._want_shortcut = self._shortcut_cb.isChecked()
        _save_install_prefs(chosen, self._want_shortcut)

        # Switch to progress page
        self._picker_page.setVisible(False)
        self._progress_page.setVisible(True)
        self.setFixedSize(440, 180)

        # Start worker
        self._thread = QThread()
        self._worker = _SetupWorker(chosen)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_setup_done)
        self._worker.error.connect(self._on_error)
        self._thread.start()

    def _build_progress_ui(self):
        lay = QVBoxLayout(self._progress_page)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(10)

        self._lbl = QLabel("Setting up LightFrame…")
        self._lbl.setStyleSheet("font-size: 11pt; font-weight: bold; color: #e7edf7;")
        self._lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self._sub = QLabel("Downloading FFmpeg for trim/export support…")
        self._sub.setStyleSheet("color: #93a1b7;")
        self._sub.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self._bar = QSlider(Qt.Horizontal)
        self._bar.setRange(0, 100)
        self._bar.setEnabled(False)
        self._bar.setStyleSheet("""
            QSlider::groove:horizontal { background:#25303c; height:8px; border-radius:4px; }
            QSlider::sub-page:horizontal { background:#4aa3ff; border-radius:4px; }
            QSlider::handle:horizontal { width:0px; }
        """)

        lay.addWidget(self._lbl)
        lay.addWidget(self._sub)
        lay.addWidget(self._bar)
        lay.addStretch()

    def _on_progress(self, pct, msg):
        self._bar.setValue(pct)
        self._sub.setText(msg)

    def _on_setup_done(self):
        self._thread.quit()
        self._bar.setValue(100)
        self._sub.setText("Done!")
        # Call _refresh_install with the chosen path
        _refresh_install(self._install_dir)
        QTimer.singleShot(600, self._finish)

    def _on_error(self, msg):
        self._thread.quit()
        self._sub.setText(f"Warning: {msg}")
        QTimer.singleShot(1500, self._finish)

    def _finish(self):
        self.close()
        self.finished.emit()


class _SetupWorker(QThread):
    progress = pyqtSignal(int, str)
    done     = pyqtSignal()
    error    = pyqtSignal(str)

    def __init__(self, install_dir: str):
        super().__init__()
        self.install_dir = install_dir

    def run(self):
        install_dir = self.install_dir
        installed_exe = os.path.join(install_dir, APP_EXE_NAME)

        # 1. Download FFmpeg if not present
        ffmpeg_dst = os.path.join(install_dir, 'ffmpeg.exe')
        if not os.path.isfile(ffmpeg_dst):
            try:
                import urllib.request, zipfile
                url = ('https://www.gyan.dev/ffmpeg/builds/'
                       'ffmpeg-release-essentials.zip')
                self.progress.emit(5, 'Downloading FFmpeg…')

                def _reporthook(count, block, total):
                    if total > 0:
                        pct = min(int(count * block / total * 70), 70)
                        self.progress.emit(5 + pct, f'Downloading FFmpeg… {5+pct}%')

                tmp, _ = urllib.request.urlretrieve(url, reporthook=_reporthook)
                self.progress.emit(76, 'Extracting FFmpeg…')

                with zipfile.ZipFile(tmp, 'r') as z:
                    for name in z.namelist():
                        if name.endswith('/bin/ffmpeg.exe'):
                            with z.open(name) as src, \
                                 open(ffmpeg_dst, 'wb') as dst:
                                dst.write(src.read())
                            break

                os.unlink(tmp)
                self.progress.emit(85, 'FFmpeg installed.')
            except Exception as exc:
                self.error.emit(f'FFmpeg download failed: {exc}')
                return

        # 2. Mark setup complete
        try:
            marker = os.path.join(install_dir, '.lightedge_setup_done')
            open(marker, 'w').close()
        except Exception:
            pass

        self.progress.emit(100, 'Done!')
        self.done.emit()


def _refresh_install(install_dir: str = None):
    """
    Run on EVERY frozen startup:
            1. Copy this exe to install_dir/lightframe.exe if it is different/newer.
      2. Re-register the right-click context menu pointing to that exe.
    This is fast (pure file copy + registry writes) and ensures both the
    installed exe and the registry are always up-to-date regardless of whether
    first-run setup has or hasn't executed before.
    """
    if not getattr(sys, 'frozen', False):
        return
    if install_dir is None:
        install_dir = get_install_dir()
    import shutil

    cur_exe = os.path.abspath(sys.executable)
    inst_exe = os.path.join(install_dir, APP_EXE_NAME)
    legacy_inst_exe = os.path.join(install_dir, LEGACY_APP_EXE_NAME)

    try:
        os.makedirs(install_dir, exist_ok=True)
    except Exception:
        pass

    # Sync exe to install dir (skip if already running from there)
    if cur_exe.lower() != os.path.abspath(inst_exe).lower():
        try:
            # Only overwrite if different size or newer timestamp
            do_copy = True
            if os.path.isfile(inst_exe):
                cur_stat  = os.stat(cur_exe)
                inst_stat = os.stat(inst_exe)
                if (cur_stat.st_size == inst_stat.st_size and
                        cur_stat.st_mtime <= inst_stat.st_mtime):
                    do_copy = False
            if do_copy:
                shutil.copy2(cur_exe, inst_exe)
        except Exception:
            inst_exe = cur_exe   # fall back: register current location

    if cur_exe.lower() != os.path.abspath(legacy_inst_exe).lower():
        try:
            do_copy = True
            if os.path.isfile(legacy_inst_exe):
                cur_stat = os.stat(cur_exe)
                legacy_stat = os.stat(legacy_inst_exe)
                if (cur_stat.st_size == legacy_stat.st_size and
                        cur_stat.st_mtime <= legacy_stat.st_mtime):
                    do_copy = False
            if do_copy:
                shutil.copy2(cur_exe, legacy_inst_exe)
        except Exception:
            pass

    if sys.platform != 'win32':
        return

    # Always re-register the right-click menu
    try:
        import winreg
        VIDEO_EXTS = [
            '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv',
            '.webm', '.m4v', '.mpg', '.mpeg', '.ts', '.m2ts',
            '.3gp', '.mxf', '.vob', '.ogv',
        ]
        cmd_value = f'"{inst_exe}" "%1"'
        for ext in VIDEO_EXTS:
            key_path = (rf'Software\Classes\{ext}'
                        rf'\shell\Open with LightFrame\command')
            with winreg.CreateKeyEx(
                    winreg.HKEY_CURRENT_USER, key_path,
                    0, winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, '', 0, winreg.REG_SZ, cmd_value)
            icon_key = (rf'Software\Classes\{ext}'
                        rf'\shell\Open with LightFrame')
            with winreg.CreateKeyEx(
                    winreg.HKEY_CURRENT_USER, icon_key,
                    0, winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(
                    k, 'Icon', 0, winreg.REG_SZ, inst_exe)
    except Exception:
        pass

    # Always create/update Desktop shortcut + Start Menu entry
    def _make_shortcut(lnk_path):
        def _ps_quote(value):
            return value.replace("'", "''")

        # Ensure directory exists
        lnk_dir = os.path.dirname(lnk_path)
        try:
            os.makedirs(lnk_dir, exist_ok=True)
        except Exception:
            return

        ps = (
            "$ErrorActionPreference = 'Stop'; "
            "$ws = New-Object -ComObject WScript.Shell; "
            f"$s = $ws.CreateShortcut('{_ps_quote(lnk_path)}'); "
            f"$s.TargetPath = '{_ps_quote(inst_exe)}'; "
            f"$s.WorkingDirectory = '{_ps_quote(install_dir)}'; "
            f"$s.IconLocation = '{_ps_quote(inst_exe)},0'; "
            "$s.Description = 'LightFrame Video Player'; "
            "$s.Save(); "
            "exit 0"
        )
        encoded = base64.b64encode(ps.encode('utf-16le')).decode('ascii')
        try:
            result = subprocess.run(
                ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                 '-EncodedCommand', encoded],
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=10, capture_output=True, text=True,
            )
            # Log errors if shortcut creation failed
            if result.returncode != 0 and result.stderr:
                pass  # Silent fail, but at least tried
        except Exception:
            pass

    if _want_desktop_shortcut():
        desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
        _make_shortcut(os.path.join(desktop, 'LightFrame.lnk'))

    start_menu = os.path.join(
        os.environ.get('APPDATA', ''),
        r'Microsoft\Windows\Start Menu\Programs')
    if os.path.isdir(start_menu):
        _make_shortcut(os.path.join(start_menu, 'LightFrame.lnk'))

    # Register in HKCU App Paths so Windows Search finds it
    try:
        import winreg
        app_key = fr'Software\Microsoft\Windows\CurrentVersion\App Paths\{APP_EXE_NAME}'
        with winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER, app_key,
                0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, '',     0, winreg.REG_SZ, inst_exe)
            winreg.SetValueEx(k, 'Path', 0, winreg.REG_SZ, install_dir)
        legacy_app_key = fr'Software\Microsoft\Windows\CurrentVersion\App Paths\{LEGACY_APP_EXE_NAME}'
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, legacy_app_key,
            0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, '',     0, winreg.REG_SZ, inst_exe)
            winreg.SetValueEx(k, 'Path', 0, winreg.REG_SZ, install_dir)
    except Exception:
        pass


def _needs_setup(install_dir: str = None):
    if not getattr(sys, 'frozen', False):
        return False
    if install_dir is None:
        install_dir = get_install_dir()
    marker = os.path.join(install_dir, '.lightedge_setup_done')
    return not os.path.isfile(marker)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("LightFrame")

    # Set window icon
    if getattr(sys, 'frozen', False):
        _icon_dir = sys._MEIPASS
    else:
        _icon_dir = os.path.dirname(os.path.abspath(__file__))
    _icon_path = os.path.join(_icon_dir, 'icon.png')
    if os.path.exists(_icon_path):
        from PyQt5.QtGui import QIcon
        app.setWindowIcon(QIcon(_icon_path))

    # File passed via right-click "Open with" or double-click
    open_path = sys.argv[1] if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]) else None

    # First-run setup (frozen exe only)
    if _needs_setup():
        setup = SetupDialog()
        setup.show()
        # Launch main window once setup finishes
        def _launch():
            global win
            win = MainWindow()
            win.show()
            if open_path:
                win._load(open_path)
        setup.finished.connect(_launch)
        sys.exit(app.exec_())

    # Subsequent runs: sync installed exe + re-register right-click menu (fast, uses stored path)
    _refresh_install()
    win = MainWindow()
    win.show()
    if open_path:
        win._load(open_path)
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
