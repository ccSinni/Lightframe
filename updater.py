#!/usr/bin/env python3
"""LightFrame Updater - handles installation and updates."""

import sys
import os
import argparse
import shutil
import json
import urllib.error
import urllib.request
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QLineEdit, QMessageBox, QProgressDialog, QWidget,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

GITHUB_REPO = 'ccSinni/Lightframe'
LATEST_RELEASE_API = f'https://api.github.com/repos/{GITHUB_REPO}/releases/latest'
HTTP_HEADERS = {
    'Accept': 'application/vnd.github+json',
    'User-Agent': 'LightFrameUpdater',
}
INSTALL_VERSION_FILE = '.lightframe_version'

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
    progress = pyqtSignal(int, str)  # (percent, message)
    done = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, asset_url=None, version=''):
        super().__init__()
        self.asset_url = asset_url
        self.version = version

    def run(self):
        try:
            asset_url = self.asset_url
            if not asset_url:
                self.progress.emit(0, 'Fetching latest release...')
                data = _fetch_json(LATEST_RELEASE_API)

                # Find lightframe.exe asset
                for asset in data.get('assets', []):
                    if asset.get('name') == 'lightframe.exe':
                        asset_url = asset.get('browser_download_url')
                        if not self.version:
                            self.version = data.get('tag_name') or ''
                        break

            if not asset_url:
                self.error.emit('lightframe.exe not found in latest release')
                return

            exe_path = os.path.join(os.environ['TEMP'], 'lightframe_download.exe')

            request = urllib.request.Request(asset_url, headers=HTTP_HEADERS)
            with urllib.request.urlopen(request, timeout=60) as response:
                total_size = int(response.headers.get('Content-Length', 0))
                downloaded = 0

                with open(exe_path, 'wb') as out:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        out.write(chunk)
                        downloaded += len(chunk)

                        if total_size > 0:
                            percent = int((downloaded / total_size) * 100)
                            size_mb = downloaded / 1024 / 1024
                            total_mb = total_size / 1024 / 1024
                            self.progress.emit(percent, f'Downloading... {size_mb:.1f}/{total_mb:.1f} MB')
                        else:
                            self.progress.emit(0, f'Downloading lightframe.exe...')

            self.done.emit(exe_path)
        except Exception as e:
            self.error.emit(f'Download failed: {e}')


class InstallerDialog(QDialog):
    """Main installer/updater dialog."""

    def __init__(self, install_dir=None, asset_url=None, version='', parent=None):
        super().__init__(parent)
        self.setWindowTitle('LightFrame Installer')
        self.setMinimumWidth(500)
        self.install_dir = install_dir
        self.asset_url = asset_url
        self.version = version
        self.downloaded_exe = None
        self.download_worker = None

        self.init_ui()
        if install_dir:
            self._apply_initial_install_dir(install_dir)

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

    def _apply_initial_install_dir(self, install_dir):
        """Select or display the install folder passed by the app."""
        for i in range(self.location_combo.count()):
            if os.path.normcase(os.path.abspath(self.location_combo.itemData(i))) == os.path.normcase(os.path.abspath(install_dir)):
                self.location_combo.setCurrentIndex(i)
                return
        self.location_combo.setCurrentIndex(self.location_combo.findData('custom'))
        self.custom_input.setText(install_dir)
        self.custom_widget.setVisible(True)

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
        self.progress_dialog = QProgressDialog('Downloading LightFrame...', None, 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.ApplicationModal)
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.setWindowTitle('LightFrame Installer')
        self.progress_dialog.show()

        self.download_worker = DownloadWorker(self.asset_url, self.version)
        self.download_worker.progress.connect(self.on_download_progress)
        self.download_worker.done.connect(self.on_download_done)
        self.download_worker.error.connect(self.on_download_error)
        self.download_worker.start()

    def on_download_progress(self, percent, message):
        """Update progress bar during download."""
        if self.progress_dialog:
            self.progress_dialog.setLabelText(message)
            self.progress_dialog.setValue(percent)

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

            # Show installation progress
            self.progress_dialog = QProgressDialog('Installing LightFrame...', None, 0, 3, self)
            self.progress_dialog.setWindowModality(Qt.ApplicationModal)
            self.progress_dialog.setCancelButton(None)
            self.progress_dialog.setWindowTitle('LightFrame Installer')
            self.progress_dialog.show()

            # Copy exe
            self.progress_dialog.setLabelText('Copying executable...')
            self.progress_dialog.setValue(1)
            target_exe = os.path.join(self.install_dir, 'lightframe.exe')

            # Remove old exe if it exists
            if os.path.exists(target_exe):
                os.remove(target_exe)

            shutil.copy2(self.downloaded_exe, target_exe)

            # Create .setup_done marker
            self.progress_dialog.setLabelText('Finalizing installation...')
            self.progress_dialog.setValue(2)
            marker = os.path.join(self.install_dir, '.lightedge_setup_done')
            Path(marker).touch()
            if self.version:
                version_marker = os.path.join(self.install_dir, INSTALL_VERSION_FILE)
                Path(version_marker).write_text(self.version.strip() + '\n', encoding='utf-8')

            # Clean up downloaded file
            try:
                os.remove(self.downloaded_exe)
            except:
                pass

            # Launch the installed exe
            self.progress_dialog.setLabelText('Launching LightFrame...')
            self.progress_dialog.setValue(3)
            import subprocess
            subprocess.Popen([target_exe])

            self.progress_dialog.close()
            self.accept()
        except Exception as e:
            if self.progress_dialog:
                self.progress_dialog.close()
            QMessageBox.critical(self, 'Installation Failed', str(e))


def parse_args(argv):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--install-dir')
    parser.add_argument('--asset-url')
    parser.add_argument('--version', default='')
    args, _ = parser.parse_known_args(argv)
    return args


def main():
    args = parse_args(sys.argv[1:])
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setApplicationName('LightFrame Installer')

    # Check for previous install
    prev_install = find_previous_install()

    dialog = InstallerDialog(
        install_dir=args.install_dir,
        asset_url=args.asset_url,
        version=args.version,
    )
    if prev_install:
        # Pre-select previous install location
        if not args.install_dir:
            dialog.location_combo.setCurrentIndex(0)  # AppData is default
            dialog.install_dir = prev_install

    dialog.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
