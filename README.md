# LightFrame

LightFrame is a lightweight Windows video player focused on fast review, trim, and export workflows.

It is designed for desktop use with a native PyQt5 interface and MPV playback. The app keeps the workflow simple: open a file, scrub accurately, choose audio tracks, set In and Out points, and export a trimmed clip.

## What The App Does

- plays common video formats through MPV
- supports drag-and-drop video loading
- shows a precision seek bar with zoom and thumbnail preview
- lets you select and mix multiple audio tracks
- supports trim In/Out marking and clip export through FFmpeg
- installs a Windows-friendly app copy, shortcuts, and file associations
- checks GitHub releases for app updates from the Help menu

## Main Features

- smooth playback with Play, Pause, Stop, seek, and volume controls
- keyboard shortcuts for transport, trimming, and fine seeking
- multi-audio selection for files with more than one track
- export of trimmed clips without a complex editor workflow
- first-run setup that downloads FFmpeg when needed
- self-update flow for packaged Windows builds using GitHub Releases

## Keyboard Shortcuts

- `Space`: play or pause
- `I`: set trim In
- `O`: set trim Out
- `Left` / `Right`: seek backward or forward
- `Shift+Left` / `Shift+Right`: frame-style fine seek
- `Up` / `Down`: adjust volume
- `+` / `-`: zoom the seek bar
- `0`: reset seek bar zoom

## Requirements

- Windows
- Python 3 with the packages in [requirements.txt](d:/VCS%20PROs/LightweightEditor/requirements.txt)
- `mpv-2.dll` present next to the app or project
- FFmpeg available through first-run setup or an approved local install path

## Running From Source

Install dependencies and launch the app:

```bat
setup.bat
launch.bat
```

Or run it directly with Python:

```bat
python main.py
```

## Building The Executable

The packaged Windows executable is built with PyInstaller from [LightEdge.spec](d:/VCS%20PROs/LightweightEditor/LightEdge.spec).

Current output name:

- `dist/lightframe.exe`

## Updates

Packaged Windows builds check GitHub's latest published release from `ccSinni/Lightframe`.

For an update to be detected correctly:

- the GitHub release must be published, not left as a draft
- the uploaded asset must be named `lightframe.exe`
- the release tag must match the app version shown in the status bar

## Project Files

- [main.py](d:/VCS%20PROs/LightweightEditor/main.py): application entrypoint and UI logic
- [LightEdge.spec](d:/VCS%20PROs/LightweightEditor/LightEdge.spec): PyInstaller build spec
- [UI_THEME.md](d:/VCS%20PROs/LightweightEditor/UI_THEME.md): UI styling direction
- [CHANGELOG.md](d:/VCS%20PROs/LightweightEditor/CHANGELOG.md): release history