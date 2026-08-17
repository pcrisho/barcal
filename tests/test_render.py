import contextlib
import io
import json
from pathlib import Path

import pytest

import barcal.theme
from barcal.render import agenda_text, main, month_grid_range
from tests.conftest import FIXTURES, render_json, write_config

AUGUST = "2026-08"


def events_by_date(payload: dict) -> dict[str, dict]:
    return {e["date"]: e for e in payload["events"]}


def test_all_day_single_event(tmp_path):
    payload = render_json(tmp_path, today="2026-08-16", month=AUGUST)
    events = events_by_date(payload)
    assert "2026-08-16" in events
    day = events["2026-08-16"]
    assert day["count"] == 1
    assert day["titles"] == ["Dentist"]
    assert day["provider"] == "google"


def test_daily_rrule_expansion(tmp_path):
    payload = render_json(tmp_path, today="2026-08-16", month=AUGUST)
    events = events_by_date(payload)
    for day in ("2026-08-03", "2026-08-12"):
        assert any("Team sync" in e["titles"] for e in [events[day]])
    assert "2026-08-13" not in events


def test_weekly_rrule_with_exdate(tmp_path):
    payload = render_json(tmp_path, today="2026-08-16", month=AUGUST)
    events = events_by_date(payload)
    assert "Yoga" in events["2026-08-10"]["titles"]
    assert "Yoga" not in events["2026-08-05"]["titles"]


def test_multi_day_all_day_event(tmp_path):
    payload = render_json(tmp_path, today="2026-08-16", month=AUGUST)
    events = events_by_date(payload)
    for day in ("2026-08-01", "2026-08-02", "2026-08-03"):
        assert "Holiday" in events[day]["titles"]
    assert events["2026-08-01"]["provider"] == "icloud"
    assert events["2026-08-02"]["provider"] == "icloud"
    assert events["2026-08-03"]["provider"] == "google,icloud"
    assert "Holiday" not in events["2026-08-04"]["titles"]


def test_multi_event_file(tmp_path):
    payload = render_json(tmp_path, today="2026-08-16", month=AUGUST)
    events = events_by_date(payload)
    assert "Coffee with Alex" in events["2026-08-14"]["titles"]
    assert "Project review" in events["2026-08-21"]["titles"]


def test_malformed_file_skipped(tmp_path):
    payload = render_json(tmp_path, today="2026-08-16", month=AUGUST)
    assert payload["class"] == "has-events"
    assert all(e["titles"] for e in payload["events"])


def test_provider_merge_on_shared_day(tmp_path):
    payload = render_json(tmp_path, today="2026-08-16", month=AUGUST)
    day = events_by_date(payload)["2026-08-03"]
    assert day["count"] == 3
    assert set(day["titles"]) == {"Team sync", "Yoga", "Holiday"}
    assert day["provider"] == "google,icloud"


def test_class_reflects_today(tmp_path):
    payload = render_json(tmp_path, today="2026-08-16", month=AUGUST)
    assert payload["class"] == "has-events"
    payload = render_json(tmp_path, today="2026-08-15", month=AUGUST)
    assert payload["class"] == "no-events"


def test_bar_text(tmp_path):
    payload = render_json(tmp_path, today="2026-08-16", month=AUGUST)
    assert payload["text"] == "16 Aug"


def test_provider_filter(tmp_path):
    payload = render_json(tmp_path, today="2026-08-16", month=AUGUST, providers=["icloud"])
    events = events_by_date(payload)
    assert set(events.keys()) == {"2026-08-01", "2026-08-02", "2026-08-03"}
    assert payload["class"] == "no-events"


def test_grid_covers_adjacent_month_days(tmp_path):
    payload = render_json(tmp_path, today="2026-08-16", month=AUGUST)
    events = events_by_date(payload)
    assert "2026-07-27" in events
    assert "2026-07-20" not in events


def test_monday_first_grid(tmp_path):
    payload = render_json(
        tmp_path, today="2026-08-16", month=AUGUST, first_day="monday"
    )
    events = events_by_date(payload)
    assert "2026-07-27" in events
    assert "2026-07-26" not in events
    assert payload["week"]["firstDay"] == "monday"


def test_week_fields(tmp_path):
    payload = render_json(tmp_path, today="2026-08-16", month=AUGUST)
    assert payload["week"] == {"firstDay": "sunday", "weekNumbers": True}


def test_missing_caldir_dir(tmp_path):
    empty = tmp_path / "empty-caldir"
    payload = render_json(tmp_path, today="2026-08-16", month=AUGUST, caldir=empty)
    assert payload["events"] == []
    assert payload["class"] == "no-events"
    assert payload["text"] == "16 Aug"


def test_payload_structure(tmp_path):
    payload = render_json(tmp_path, today="2026-08-16", month=AUGUST)
    assert set(payload.keys()) == {"text", "class", "palette", "week", "events"}
    for key in ("mode", "accent", "muted", "background", "foreground", "selection"):
        assert key in payload["palette"]


def test_month_override_switches_grid(tmp_path):
    payload = render_json(tmp_path, today="2026-09-15", month="2026-09")
    events = events_by_date(payload)
    assert "2026-08-16" not in events
    assert "2026-09-02" in events
    assert "Yoga" in events["2026-09-02"]["titles"]


def test_agenda_today(tmp_path):
    config = write_config(tmp_path)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        rc = main(
            [
                "--config", str(config),
                "--today", "2026-08-16",
                "--month", AUGUST,
                "--agenda-today",
            ]
        )
    assert rc == 0
    assert buffer.getvalue().strip() == "- Dentist"

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        rc = main(
            [
                "--config", str(config),
                "--today", "2026-08-15",
                "--month", AUGUST,
                "--agenda-today",
            ]
        )
    assert rc == 0
    assert buffer.getvalue().strip() == "No events today."


def test_agenda_text_no_events():
    assert agenda_text({}, __import__("datetime").date(2026, 8, 15)) == "No events today."


def test_parse_colors_toml_fills_defaults(tmp_path):
    colors = tmp_path / "colors.toml"
    colors.write_text('mode = "dark"\naccent = "#ff0000"\nbackground = "#111111"\n')
    palette = barcal.theme.parse_colors_toml(colors)
    assert palette["accent"] == "#ff0000"
    assert palette["mode"] == "dark"
    assert palette["selection"] == barcal.theme.DEFAULT_PALETTE["selection"]
    assert palette["foreground"] == barcal.theme.DEFAULT_PALETTE["foreground"]


def test_find_colors_path_prefers_user_theme(tmp_path, monkeypatch):
    slug = "test-theme"
    user_dir = tmp_path / "user" / "themes" / slug
    stock_dir = tmp_path / "stock" / "themes" / slug
    user_dir.mkdir(parents=True)
    stock_dir.mkdir(parents=True)
    (user_dir / "colors.toml").write_text("accent = '#00ff00'\n")
    (stock_dir / "colors.toml").write_text("accent = '#0000ff'\n")
    monkeypatch.setattr(barcal.theme, "USER_THEMES_DIR", tmp_path / "user" / "themes")
    monkeypatch.setattr(barcal.theme, "STOCK_THEMES_DIR", tmp_path / "stock" / "themes")
    assert barcal.theme.find_colors_path(slug) == user_dir / "colors.toml"
    monkeypatch.setattr(barcal.theme, "USER_THEMES_DIR", tmp_path / "missing")
    assert barcal.theme.find_colors_path(slug) == stock_dir / "colors.toml"


def test_resolve_palette_falls_back_to_default(tmp_path, monkeypatch):
    monkeypatch.setattr(barcal.theme, "USER_THEMES_DIR", tmp_path / "missing")
    monkeypatch.setattr(barcal.theme, "STOCK_THEMES_DIR", tmp_path / "missing")
    assert barcal.theme.resolve_palette() == barcal.theme.DEFAULT_PALETTE


def test_render_uses_resolved_palette(tmp_path, monkeypatch):
    theme_dir = tmp_path / "themes" / "vantablack"
    theme_dir.mkdir(parents=True)
    (theme_dir / "colors.toml").write_text(
        'mode = "dark"\naccent = "#8d8d8d"\nmuted = "#7a7a7a"\n'
        'background = "#000000"\nforeground = "#ffffff"\nselection = "#1a1a1a"\n'
    )
    monkeypatch.setattr(barcal.theme, "USER_THEMES_DIR", tmp_path / "themes")
    monkeypatch.setattr(barcal.theme, "STOCK_THEMES_DIR", tmp_path / "missing")
    payload = render_json(tmp_path, today="2026-08-16", month=AUGUST)
    assert payload["palette"]["accent"] == "#8d8d8d"


def test_month_grid_range_sunday_first():
    start, end = month_grid_range(2026, 8, "sunday")
    assert start.isoformat() == "2026-07-26"
    assert end.isoformat() == "2026-09-06"


def test_month_grid_range_monday_first():
    start, end = month_grid_range(2026, 8, "monday")
    assert start.isoformat() == "2026-07-27"
    assert end.isoformat() == "2026-09-07"


def test_month_grid_range_december_wraps():
    start, end = month_grid_range(2026, 12, "sunday")
    assert start.isoformat() == "2026-11-29"
    assert end.isoformat() == "2027-01-03"
