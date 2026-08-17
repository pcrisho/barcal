"""barcal-render — read Caldir .ics files, expand recurrence, emit JSON for the bar widget."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import icalendar
import recurring_ical_events

from barcal.config import Config, DEFAULT_REVISION_PATH, load_config
from barcal.theme import resolve_palette

MONTH_ABBREVIATIONS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

FIRST_WEEKDAY_OFFSET = {"sunday": 6, "monday": 0}

MAX_TITLES_PER_DAY = 5


def weekday_offset(first_day_of_week: str) -> int:
    return FIRST_WEEKDAY_OFFSET.get(first_day_of_week, 6)


def month_grid_range(
    year: int, month: int, first_day_of_week: str = "sunday"
) -> tuple[date, date]:
    offset = weekday_offset(first_day_of_week)
    first = date(year, month, 1)
    grid_start = first - timedelta(days=(first.weekday() - offset) % 7)
    if month == 12:
        last = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    grid_end = last + timedelta(days=(offset - 1 - last.weekday()) % 7)
    return grid_start, grid_end + timedelta(days=1)


def occurrence_date(occurrence: datetime | date) -> date:
    if isinstance(occurrence, datetime):
        return occurrence.astimezone().date()
    return occurrence


def event_days(occurrence: icalendar.cal.Event) -> list[date]:
    dtstart = occurrence.get("dtstart")
    if dtstart is None:
        return []
    start = dtstart.dt
    dtend = occurrence.get("dtend")
    end = dtend.dt if dtend is not None else None

    if isinstance(start, datetime):
        start_day = start.astimezone().date()
        if isinstance(end, datetime):
            end_day = end.astimezone().date()
        else:
            end_day = start_day
        span = (end_day - start_day).days + 1
    else:
        start_day = start
        if isinstance(end, date):
            span = (end - start).days
        else:
            span = 1
    return [start_day + timedelta(days=i) for i in range(max(span, 0))]


def provider_of(caldir_path: Path, ics_path: Path) -> str | None:
    try:
        rel = ics_path.resolve().relative_to(caldir_path.resolve())
    except ValueError:
        return None
    if len(rel.parts) < 2:
        return None
    return rel.parts[0]


def occurrences_in_range(
    vevent: icalendar.cal.Component,
    start: datetime,
    end: datetime,
) -> list[icalendar.cal.Event]:
    calendar = icalendar.Calendar()
    calendar.add("prodid", "-//barcal//EN")
    calendar.add("version", "2.0")
    calendar.add_component(vevent)
    return list(recurring_ical_events.of(calendar).between(start, end))


def collect_events(
    caldir_path: Path,
    providers: list[str],
    start: date,
    end: date,
) -> dict[str, dict]:
    events_by_date: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "titles": [], "provider": set(), "uids": set()}
    )
    if not caldir_path.is_dir():
        return dict(events_by_date)

    window_start = datetime(start.year, start.month, start.day)
    window_end = datetime(end.year, end.month, end.day)

    for ics_path in sorted(caldir_path.rglob("*.ics")):
        provider = provider_of(caldir_path, ics_path)
        if provider is None:
            provider = "local"
        if providers and provider not in providers:
            continue
        try:
            with open(ics_path, "rb") as f:
                calendar = icalendar.Calendar.from_ical(f.read())
        except Exception:
            print(f"barcal-render: skipping unreadable file {ics_path}", file=sys.stderr)
            continue

        for component in calendar.walk("VEVENT"):
            try:
                occurrences = occurrences_in_range(component, window_start, window_end)
            except Exception:
                print(f"barcal-render: skipping malformed event {ics_path}", file=sys.stderr)
                continue
            for occurrence in occurrences:
                summary = str(component.get("summary", "Untitled"))
                uid = str(component.get("uid", summary))
                for day in event_days(occurrence):
                    bucket = events_by_date[day.isoformat()]
                    if uid not in bucket["uids"]:
                        bucket["uids"].add(uid)
                        bucket["count"] += 1
                        if summary not in bucket["titles"] and len(bucket["titles"]) < MAX_TITLES_PER_DAY:
                            bucket["titles"].append(summary)
                    bucket["provider"].add(provider)
    return dict(events_by_date)


def events_payload(events_by_date: dict[str, dict]) -> list[dict]:
    payload = []
    for day, bucket in sorted(events_by_date.items()):
        payload.append(
            {
                "date": day,
                "count": bucket["count"],
                "titles": bucket["titles"],
                "provider": ",".join(sorted(bucket["provider"])),
            }
        )
    return payload


def bar_text(today: date) -> str:
    return f"{today.day} {MONTH_ABBREVIATIONS[today.month - 1]}"


def agenda_text(events_by_date: dict[str, dict], today: date) -> str:
    bucket = events_by_date.get(today.isoformat())
    if not bucket:
        return "No events today."
    lines = []
    for title in sorted(bucket["titles"]):
        lines.append(f"- {title}")
    return "\n".join(lines) if lines else "No events today."


def build_payload(
    cfg: Config,
    today: date,
    grid_start: date,
    grid_end: date,
    palette: dict[str, str],
) -> dict:
    events_by_date = collect_events(cfg.caldir_path, cfg.providers, grid_start, grid_end)
    today_key = today.isoformat()
    return {
        "text": bar_text(today),
        "class": "has-events" if today_key in events_by_date else "no-events",
        "palette": palette,
        "week": {"firstDay": cfg.first_day_of_week, "weekNumbers": True},
        "revisionPath": str(DEFAULT_REVISION_PATH),
        "events": events_payload(events_by_date),
    }


def parse_month(value: str) -> tuple[int, int]:
    year_s, _, month_s = value.partition("-")
    return int(year_s), int(month_s)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="barcal-render",
        description="Read Caldir .ics files and emit bar widget JSON.",
    )
    parser.add_argument("--config", type=Path, default=None, help="Path to config.toml")
    parser.add_argument(
        "--today", type=date.fromisoformat, default=date.today(), help="Override today (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--month", type=str, default=None, help="Override visible month (YYYY-MM)"
    )
    parser.add_argument("--agenda-today", action="store_true", help="Print today's agenda as text")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    palette = resolve_palette()

    if args.month:
        year, month = parse_month(args.month)
        grid_start, grid_end = month_grid_range(year, month, cfg.first_day_of_week)
    else:
        grid_start, grid_end = month_grid_range(
            args.today.year, args.today.month, cfg.first_day_of_week
        )

    if args.agenda_today:
        events_by_date = collect_events(cfg.caldir_path, cfg.providers, grid_start, grid_end)
        print(agenda_text(events_by_date, args.today))
        return 0

    payload = build_payload(cfg, args.today, grid_start, grid_end, palette)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
