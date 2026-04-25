# LightweightEditor UI Theme

## Direction

The interface should feel like a professional desktop video editor:

- restrained, dark control-room palette
- high legibility for long editing sessions
- clear hierarchy between canvas, transport, utility panels, and status surfaces
- precise accent usage for actionable controls and trim feedback

## Visual Language

### Palette

- Canvas black: `#050608`
- Main shell: `#12161d`
- Raised surface: `#1a2029`
- Panel surface: `#202833`
- Panel border: `#313c4c`
- Divider / inactive line: `#435066`
- Primary text: `#e7edf7`
- Secondary text: `#93a1b7`
- Muted text: `#677489`
- Accent blue: `#4aa3ff`
- Accent blue hover: `#68b6ff`
- Accent blue pressed: `#2c86e8`
- Success trim-in: `#38d27d`
- Warning trim-out: `#ff9f43`
- Danger / error: `#ff5d73`

### Typography

- Primary UI font: Segoe UI
- Time readouts: Consolas
- Titles and section labels should use weight and contrast instead of oversized text

### Component Rules

- Video canvas should remain the darkest area on screen.
- Buttons should read as tactile control surfaces, not flat web buttons.
- Group boxes should look like docked editor panels with subtle separators.
- Menus and status bar should blend into the shell, not appear as disconnected widgets.
- Progress dialogs should match the shell and read like modal workflow blockers.
- Timeline and seek accents should use blue for playback state, green for In, and amber for Out.

## Applied Surfaces

This theme should cover:

- main application shell
- transport controls
- audio and trim panels
- seek bar ruler and markers
- status bar and menus
- first-run setup dialog
- export-in-progress dialog
