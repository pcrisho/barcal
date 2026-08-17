# barcal widget (Quickshell)

`Barcal.qml` + `manifest.json` form an Omarchy bar-widget plugin. It runs
`barcal-render` on an interval, re-renders instantly when
`barcal-watcher` bumps the revision marker after `caldir sync`, and shows a
month grid with event days tinted in the active theme's accent.

## Requirements

- Omarchy (Quickshell bar)
- `barcal-render` installed and on `PATH` (see repo root)
- `barcal-watcher` running (it owns the revision marker this widget watches)
- Caldir with at least one connected provider

## Install

Copy the directory into your user plugins folder as `<user>.barcal`:

```bash
mkdir -p ~/.config/omarchy/plugins
cp -r quickshell/barcal ~/.config/omarchy/plugins/<user>.barcal
```

Then add it to the bar layout in `~/.config/omarchy/shell.json`:

```jsonc
{
  "id": "<user>.barcal",
  "position": "left"
}
```

The shell hot-reloads `shell.json` on save — no restart needed.

## Behavior

- **Left click** on the date label toggles the calendar popup.
- **Right click** opens today's agenda in a floating terminal.
- **Scroll / chevrons / arrow keys** step the viewed month; **Enter** jumps
  back to today.
- Event days get an accent-colored dot (and a tinted cell), with the event
  titles on hover.
- A dot before the bar label marks days with events.

## Settings

`interval` (seconds, default 60) controls how often `barcal-render` runs;
the revision marker still forces an immediate refresh on sync.

## Notes

The refresh mechanics (FileView `watchChanges` on the revision marker) and
the popup chrome follow the same shapes as `omarchy.clock` and
`dev.reuk.sysstats`; validate against your shell version after upgrades.
