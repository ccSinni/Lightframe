#!/usr/bin/env python3
"""LightFrame Updater - handles installation and updates."""

import sys
import os
import shutil
import json
import urllib.error
import urllib.request
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QLineEdit, QMessageBox, QProgressDialog,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

GITHUB_REPO = 'ccSinni/Lightframe'
LATEST_RELEASE_API = f'https://api.github.com/repos/{GITHUB_REPO}/releases/latest'
HTTP_HEADERS = {
    'Accept': 'application/vnd.github+json',
    'User-Agent': 'LightFrameUpdater',
}

_DEFAULT_INSTALL_DIR = os.path.join(
    os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'LightFrame')


def _fetch_json(url):
    """Fetch JSON from URL."""
    request = urllib.request.Request(url, headers=HTTP_HEADERS)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def find_previous_install():
    """Check if LightFrame is already installed."""
    lightframe_exe = os.path.join(_DEFAULT_INSTALL_DIR, 'lightframe.exe')
    if os.path.isfile(lightframe_exe):
        return _DEFAULT_INSTALL_DIR
    return None


class DownloadWorker(QThread):
    """Download lightframe.exe from GitHub in background."""
    progress = pyqtSignal(str)
    done = pyqtSignal(str)
    error = pyqtSignal(str)

    def run(self):
        try:
            self.progress.emit('Fetching latest release...')
            data = _fetch_json(LATEST_RELEASE_API)

            # Find lightframe.exe asset
            asset_url = None
            for asset in data.get('assets', []):
                if asset.get('name') == 'lightframe.exe':
                    asset_url = asset.get('browser_download_url')
                    break

            if not asset_url:
                self.error.emit('lightframe.exe not found in latest release')
                return

            self.progress.emit('Downloading lightframe.exe...')
            exe_path = os.path.join(os.environ['TEMP'], 'lightframe_download.exe')

            request = urllib.request.Request(asset_url, headers=HTTP_HEADERS)
            with urllib.request.urlopen(request, timeout=60) as response:
                with open(exe_path, 'wb') as out:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        out.write(chunk)

            self.done.emit(exe_path)
        except Exception as e:
            self.error.emit(f'Download failed: {e}')


class InstallerDialog(QDialog):
    """Main installer/updater dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('LightFrame Installer')
        self.setMinimumWidth(500)
        self.install_dir = None
        self.downloaded_exe = None
        self.download_worker = None

        self.init_ui()

    def init_ui(self):
        """Build the installer UI."""
        layout = QVBoxLayout()

        # Title
        title = QLabel('Install LightFrame')
        title.setStyleSheet('font-size: 14pt; font-weight: bold;')
        layout.addWidget(title)

        # Subtitle
        subtitle = QLabel('Choose where to install LightFrame')
        layout.addWidget(subtitle)

        # Install location section
        loc_layout = QHBoxLayout()
        loc_layout.addWidget(QLabel('Install location:'))

        self.location_combo = QComboBox()
        self.location_combo.addItem('AppData (Recommended)', _DEFAULT_INSTALL_DIR)

        prog_files = os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), 'LightFrame')
        self.location_combo.addItem('Program Files', prog_files)
        self.location_combo.addItem('Custom...', 'custom')

        self.location_combo.currentIndexChanged.connect(self.on_location_changed)
        loc_layout.addWidget(self.location_combo)
        layout.addLayout(loc_layout)

        # Custom path input (hidden initially)
        self.custom_widget = QWidget()
        self.custom_layout = QHBoxLayout()
        self.custom_layout.addWidget(QLabel('Custom path:'))
        self.custom_input = QLineEdit()
        self.custom_input.setText(_DEFAULT_INSTALL_DIR)
        self.custom_layout.addWidget(self.custom_input)
        browse_btn = QPushButton('Browse...')
        browse_btn.clicked.connect(self.browse_folder)
        self.custom_layout.addWidget(browse_btn)
        self.custom_widget.setLayout(self.custom_layout)
        layout.addWidget(self.custom_widget)
        self.custom_widget.setVisible(False)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        install_btn = QPushButton('Install')
        install_btn.clicked.connect(self.install)
        btn_layout.addWidget(install_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def on_location_changed(self):
        """Show/hide custom path input."""
        if self.location_combo.currentData() == 'custom':
            self.custom_widget.setVisible(True)
        else:
            self.custom_widget.setVisible(False)

    def browse_folder(self):
        """Browse for custom install folder."""
        from PyQt5.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(self, 'Choose Install Location')
        if folder:
            self.custom_input.setText(folder)

    def install(self):
        """Start installation."""
        if self.location_combo.currentData() == 'custom':
            self.install_dir = self.custom_input.text()
        else:
            self.install_dir = self.location_combo.currentData()

        if not self.install_dir:
            QMessageBox.warning(self, 'Error', 'Please select an install location')
            return

        # Show progress and download
        self.show_progress()

    def show_progress(self):
        """Show progress dialog and start download."""
        self.progress_dialog = QProgressDialog('Downloading LightFrame...', None, 0, 0, self)
        self.progress_dialog.setWindowModality(Qt.ApplicationModal)
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.show()

        self.download_worker = DownloadWorker()
        self.download_worker.progress.connect(self.progress_dialog.setLabelText)
        self.download_worker.done.connect(self.on_download_done)
        self.download_worker.error.connect(self.on_download_error)
        self.download_worker.start()

    def on_download_done(self, exe_path):
        """Download finished, now install."""
        self.downloaded_exe = exe_path
        self.progress_dialog.close()
        self.apply_install()

    def on_download_error(self, error):
        """Download failed."""
        self.progress_dialog.close()
        QMessageBox.critical(self, 'Download Failed', error)

    def apply_install(self):
        """Copy exe to install location and create shortcuts."""
        try:
            os.makedirs(self.install_dir, exist_ok=True)

            # Copy exe
            target_exe = os.path.join(self.install_dir, 'lightframe.exe')
            shutil.copy2(self.downloaded_exe, target_exe)

            # Create .setup_done marker
            marker = os.path.join(self.install_dir, '.lightedge_setup_done')
            Path(marker).touch()

            # Clean up downloaded file
            try:
                os.remove(self.downloaded_exe)
            except:
                pass

            # Launch the installed exe
            import subprocess
            subprocess.Popen([target_exe])

            self.accept()
        except Exception as e:
            QMessageBox.critical(self, 'Installation Failed', str(e))


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setApplicationName('LightFrame Installer')

    # Check for previous install
    prev_install = find_previous_install()

    dialog = InstallerDialog()
    if prev_install:
        # Pre-select previous install location
        dialog.location_combo.setCurrentIndex(0)  # AppData is default
        dialog.install_dir = prev_install

    dialog.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
