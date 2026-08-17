# barcal

Calendar widget for the Omarchy bar (Quickshell), powered by Caldir.

Glance at your Google Calendar (or iCloud / Outlook / CalDAV) from the topbar without leaving your desktop. barcal reads the `.ics` files that [Caldir](https://caldir.org) already syncs and renders a month grid with event days highlighted inside the Omarchy bar, themed to match the active Omarchy theme.

- **Zero sync logic** — Caldir owns auth, tokens, and pull/push.
- **Reactive** — the widget refreshes right after `caldir sync` writes new files.
- **Complements [rencal](https://github.com/t4t5/rencal)** — rencal is the full calendar app; barcal is the bar-level glance. Read-only, small, auditable, no telemetry.

## Requirements

- [Omarchy](https://omarchy.org) (Hyprland + Quickshell bar)
- [Caldir](https://caldir.org) with at least one connected provider (`caldir connect google`)

## Install

_Coming soon: `curl | sh` install script and `barcal-git` AUR package._

## Widget

The bar widget lives in [`quickshell/barcal/`](quickshell/barcal/README.md) —
copy it to `~/.config/omarchy/plugins/<user>.barcal` and add it to the bar
layout in `~/.config/omarchy/shell.json`.

## Configure

_Coming soon: config.toml reference and the "relationship to rencal" section._

## Development

_Coming soon: pytest suite with `.ics` fixtures (recurrence, timezones, all-day events) — no real credentials required._

## License

MIT — see [LICENSE](LICENSE).
