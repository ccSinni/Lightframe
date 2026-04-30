# Changelog

All notable changes to LightFrame are documented here.

## 1.1.2 - 2026-04-29

- polished timeline zoom interaction with smoother zoom steps and reset animation
- added draggable panning on the zoom overview bar
- improved zoom readout and timeline drawing details

## 1.1.1 - 2026-04-29

- published a patch release so existing `1.1` installs can detect the shortcut installer fix
- creates Desktop and Start Menu shortcuts directly during the installer flow

## 1.1 - 2026-04-29

- reset the public release version to `1.1` after the temporary `v.2.x` updater-fix releases
- kept the self-update fixes that target the exact checked release and reuse the local updater
- removed the leftover test update text from the main window title

## v.1.03 - 2026-04-25

- published a fresh release tag so packaged update checks no longer depend on a replaced `v.1.02` asset
- rebuilt `lightframe.exe` with the current self-update logic and re-published it as `v.1.03`

## v.1.02 - 2026-04-25

- changed update detection to follow GitHub's latest published release tag directly
- normalized release tag handling so formats like `v1.02` and `v.1.02` resolve consistently
- rebuilt and retagged the app for the `v.1.02` release

## v1.1 - 2026-04-25

- added GitHub release update checking from the Help menu
- added packaged Windows self-update support using the `lightframe.exe` release asset
- added a visible build/version label in the status bar
- renamed the packaged executable output to `lightframe.exe`
- kept compatibility with older `LightFrame.exe` launch paths in the install directory
- regenerated the packaged icon and rebuilt the Windows executable

## Earlier 2026-04 work

- hardened FFmpeg resolution so the app prefers trusted local locations
- improved uninstall cleanup to remove only app-owned files
- updated Windows shortcut creation to use a safer encoded PowerShell path
- improved thumbnail temp cache cleanup and runtime behavior
