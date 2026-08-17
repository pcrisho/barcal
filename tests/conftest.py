import contextlib
import io
import json
import time
from pathlib import Path

import pytest

from barcal.render import main

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def utc_timezone(monkeypatch):
    monkeypatch.setenv("TZ", "UTC")
    time.tzset()
    yield


def write_config(
    tmp_path: Path,
    caldir: Path | None = None,
    providers: list[str] | None = None,
    first_day: str | None = None,
) -> Path:
    config_path = tmp_path / "config.toml"
    sections = ["[source]", f'caldir_path = "{caldir or FIXTURES}"']
    if providers is not None:
        sections.append(f"providers = {providers}")
    if first_day:
        sections.append("[display]")
        sections.append(f'first_day_of_week = "{first_day}"')
    config_path.write_text("\n".join(sections) + "\n")
    return config_path


def run_render(argv: list[str]) -> dict:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        rc = main(argv)
    assert rc == 0
    return json.loads(buffer.getvalue())


def render_json(
    tmp_path: Path,
    today: str | None = None,
    month: str | None = None,
    caldir: Path | None = None,
    providers: list[str] | None = None,
    first_day: str | None = None,
) -> dict:
    config = write_config(tmp_path, caldir=caldir, providers=providers, first_day=first_day)
    argv = ["--config", str(config)]
    if today:
        argv += ["--today", today]
    if month:
        argv += ["--month", month]
    return run_render(argv)
