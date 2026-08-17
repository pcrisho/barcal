# barcal — Spec v0.1

**Calendar widget for the Omarchy bar (Quickshell), powered by Caldir**

## 1. Problem Statement

Omarchy's bar is a Quickshell shell (`omarchy-shell`). Its built-in `omarchy.clock` widget renders the date and time but has no calendar popup and no concept of events — it cannot be wired to any calendar backend, including HEY (which is a fully separate desktop app) or Google Calendar.

Users who want to glance at their Google Calendar from the topbar today have no first-party option. rencal is the closest thing — a full GUI calendar app that syncs via Caldir — but it does not live in the bar: there is no glanceable month grid with event highlights at the topbar level.

**barcal** closes this gap by reading the `.ics` files that [Caldir](https://caldir.org) already syncs from Google (or iCloud/Outlook/CalDAV) and rendering them as a calendar widget in the Omarchy bar — no OAuth code, no sync engine, no GUI framework required.

## 2. Goals

- Add a calendar popup to the Omarchy bar showing actual events, sourced from local `.ics` files maintained by Caldir.
- Zero sync logic in barcal itself — Caldir owns auth, tokens, and pull/push.
- Feel reactive: the bar widget updates shortly after `caldir sync` runs, not just on a fixed poll interval.
- Match the active Omarchy theme (colors pulled from the active theme's `colors.toml`).
- Ship as a small, auditable, installable open-source tool. It complements rencal; it is not a fork or a replacement of it.

## 3. Non-Goals (v1)

- No event creation/editing (read-only). Use rencal or `caldir`/text editing of `.ics` for that.
- No standalone GUI window — rendering happens inside the Omarchy bar (Quickshell widget) plus an optional terminal agenda view.
- No custom sync engine, no direct Google API calls, no token storage. Caldir is a hard dependency.
- No Windows/macOS support — Omarchy/Hyprland/Quickshell only for v1.

## 4. Architecture

```
┌─────────────────┐      caldir sync       ┌──────────────────────┐
│ Google Calendar  │ ─────────────────────► │  ~/caldir/google/*.ics│
│ (via Caldir)     │                        │  ~/caldir/icloud/*.ics│
└─────────────────┘                        └──────────┬───────────┘
                                                       │ inotify watch
                                                       ▼
                                           ┌───────────────────────┐
                                           │   barcal-watcher       │
                                           │  (background, systemd  │
                                           │   user service)         │
                                           └──────────┬─────────────┘
                                                      │ bump ~/.cache/barcal/revision
                                                      ▼
┌──────────────────────┐   poll + on revision  ┌─────────────────────┐
│ omarchy-shell widget  │ ◄──────────────────── │  barcal-render      │
│ (<user>.barcal, QML)  │ ── JSON on stdout ──► │  (Python, stateless)│
└──────────────────────┘                        └─────────────────────┘
```

Two components, one config file:

1. **`barcal-render`** — invoked by the bar widget, reads `.ics` files, expands recurrence, emits structured JSON on stdout, exits. Stateless, fast, safe to call every N seconds.
2. **`barcal-watcher`** — long-running, watches `~/caldir/` for filesystem changes via inotify, and on change bumps a revision marker so the widget re-renders without waiting for the next poll. Runs as a systemd `--user` service.

### Refresh flow

1. The Quickshell widget runs `barcal-render` on its interval timer.
2. `barcal-watcher` watches `~/caldir/**/*.ics` with inotify (watchdog).
3. On any change, the watcher bumps `~/.cache/barcal/revision` (mtime touch).
4. The widget watches that file (QFileSystemWatcher) and re-runs `barcal-render` immediately.

## 5. Data Source Contract

- Caldir is a **hard prerequisite**, not bundled. Installation docs point users to `curl -sSf https://caldir.org/install.sh | sh` and `caldir connect google`.
- barcal reads `~/caldir/<provider>/*.ics` recursively (path configurable).
- Each `.ics` file is a single VEVENT (per Caldir's one-file-per-event convention) — no need to handle multi-event calendar files, but barcal should not crash if it encounters one.
- Recurrence (RRULE) must be expanded for the visible month range at render time — do not assume Caldir pre-expands recurring events.
- The exact `~/caldir/` layout and the one-file-per-event convention must be verified against a live Caldir install at implementation time (see §14).

## 6. Tech Stack

| Concern | Choice | Why |
|---|---|---|
| Bar widget | QML (Quickshell plugin) | native to the Omarchy bar; registered via the `omarchy plugin` clone pattern, placed with `omarchy bar move` / `shell.json` |
| Render script | Python 3.11+ | `icalendar` + `recurring-ical-events` handle RRULE/timezone edge cases correctly; startup overhead is irrelevant at the widget's poll interval |
| ICS parsing | `icalendar` | de facto standard, RFC 5545 compliant |
| Recurrence expansion | `recurring-ical-events` | built on top of `icalendar`, handles EXDATE/RDATE/RRULE |
| Watcher | Python `watchdog` (inotify wrapper) | simplest reliable inotify binding, avoids shelling out to `inotifywait` |
| Config format | TOML | consistent with Omarchy/Hyprland ecosystem conventions |
| Packaging | `pipx`-installable + AUR package (`barcal-git`) | matches how Omarchy-adjacent tools are typically distributed |
| Service management | systemd `--user` unit for the watcher | standard on Omarchy (Arch-based) |

The renderer stays front-end agnostic (stable stdout JSON contract), so a future Rust rewrite or a standalone Waybar adapter does not touch the widget.

## 7. Bar Integration (Quickshell widget)

Registered as a user plugin following the `omarchy plugin clone` pattern, resulting in `<user>.barcal`, then placed in the bar layout via `~/.config/omarchy/shell.json` (or `omarchy bar move`).

```jsonc
{
  "id": "<user>.barcal",
  "position": "left"
}
```

Widget behavior:

- Displays compact date text from `barcal-render` output; clicking it opens the tooltip popup with the month grid.
- Right-click (or a dedicated action) opens today's agenda in a floating terminal via the configured `agenda_terminal_cmd`.
- Tooltip grid mirrors the visual layout of a classic month calendar (week numbers left, Sun–Sat header, current day boxed) with event days rendered in the theme's accent color.

### Output contract (stdout JSON from `barcal-render`)

```json
{
  "text": "16 Aug",
  "class": "has-events",
  "palette": {
    "accent": "#8d8d8d",
    "background": "#000000",
    "foreground": "#ffffff",
    "muted": "#7a7a7a"
  },
  "week": { "firstDay": "sunday", "weekNumbers": true },
  "events": [
    { "date": "2026-08-16", "count": 2, "titles": ["Team sync", "Dentist"], "provider": "google" }
  ]
}
```

- `text` is the bar label; `class` toggles `has-events` / `no-events` for bar-level styling.
- `palette` carries the resolved theme colors; `events` drives the grid highlighting in the QML widget.
- `barcal-render --agenda-today` prints a plain-text agenda of today's events, for the floating terminal.

## 8. Theming

- Active theme slug resolved via `omarchy theme current`.
- Palette file: `~/.config/omarchy/themes/<slug>/colors.toml`, falling back to `/usr/share/omarchy/themes/<slug>/colors.toml`.
- Keys used: `mode`, `accent`, `muted`, `background`, `foreground`, `selection`.
- The renderer maps them into the JSON `palette` field; the QML widget applies them. No custom theme engine — just enough to not look out of place next to the rest of Omarchy.

## 9. Config File

`~/.config/barcal/config.toml`

```toml
[source]
caldir_path = "~/caldir"
providers = []  # empty = all providers found under caldir_path

[display]
first_day_of_week = "sunday"  # or "monday"
mode = "month"                 # "month" | "year" (future)
show_event_count_in_bar = false

[behavior]
poll_interval_seconds = 60
agenda_terminal_cmd = "omarchy launch floating terminal with presentation"
```

## 10. MVP Scope (v1)

1. `barcal-render` producing correct JSON (`text`/`class`/`events`/`palette`) for the widget, month view, event days highlighted.
2. `barcal-watcher` systemd user service + revision marker triggering instant widget refresh on Caldir changes.
3. Theme-aware palette resolution.
4. QML widget (`<user>.barcal`) with month-grid tooltip and agenda click action.
5. Install script (`curl | sh` style, matching Caldir/rencal conventions) + AUR package.
6. README with shell.json config snippet, screenshot/GIF, and a "relationship to rencal" section.

## 11. Phase 2 (explicitly out of scope for v1, note in README as roadmap)

- Year view mode.
- Multi-day event bars / week view in tooltip.
- Click-to-jump into rencal at a specific date, if rencal exposes a deep-link/CLI arg for it.
- Per-provider color coding (Google vs iCloud vs Outlook events shown in different accent colors).
- Standalone Waybar module adapter for non-Omarchy setups.

## 12. Repo Structure

```
barcal/
├── LICENSE                 # MIT
├── README.md
├── docs/
│   └── BARCAL-SPEC.md      # this document
├── barcal/
│   ├── render.py
│   ├── watcher.py
│   ├── theme.py
│   └── config.py
├── quickshell/
│   └── Barcal.qml          # widget + manifest
├── packaging/
│   └── barcal-git/PKGBUILD
├── install.sh
├── pyproject.toml
└── tests/
    ├── test_render.py
    └── fixtures/*.ics
```

## 13. Open Source Checklist

- License: MIT (matches Caldir and rencal, lowers friction for anyone building on top).
- CI: GitHub Actions running `pytest` on push/PR.
- Contributing guide referencing Caldir's `.ics` layout so contributors don't need real Google credentials to test — fixtures cover recurrence, timezones, all-day events.
- No telemetry, no network calls beyond what Caldir already does.

## 14. Open Questions for Implementation

- Verify the real `~/caldir/` layout and the one-file-per-event convention against a live Caldir install (the CLI is not installed on the reference machine at spec time).
- Confirm the Quickshell plugin registration/refresh mechanics (`omarchy plugin` clone pattern + QFileSystemWatcher on a revision marker) against the shipped shell version.
- Decide whether `barcal-watcher` should be started automatically by the install script or left as a manual `systemctl --user enable` step.
