"""Configuration loading for barcal (~/.config/barcal/config.toml)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "barcal" / "config.toml"

DEFAULT_REVISION_PATH = Path.home() / ".cache" / "barcal" / "revision"

DEFAULT_AGENDA_TERMINAL_CMD = "omarchy launch floating terminal with presentation"


@dataclass
class Config:
    caldir_path: Path = Path("~/caldir").expanduser()
    providers: list[str] = field(default_factory=list)
    first_day_of_week: str = "sunday"
    mode: str = "month"
    show_event_count_in_bar: bool = False
    poll_interval_seconds: int = 60
    agenda_terminal_cmd: str = DEFAULT_AGENDA_TERMINAL_CMD


def load_config(path: Path | None = None) -> Config:
    path = path or DEFAULT_CONFIG_PATH
    data: dict = {}
    if path.is_file():
        with open(path, "rb") as f:
            data = tomllib.load(f)

    source = data.get("source", {})
    display = data.get("display", {})
    behavior = data.get("behavior", {})

    return Config(
        caldir_path=Path(source.get("caldir_path", "~/caldir")).expanduser(),
        providers=list(source.get("providers", [])),
        first_day_of_week=str(display.get("first_day_of_week", "sunday")),
        mode=str(display.get("mode", "month")),
        show_event_count_in_bar=bool(display.get("show_event_count_in_bar", False)),
        poll_interval_seconds=int(behavior.get("poll_interval_seconds", 60)),
        agenda_terminal_cmd=str(
            behavior.get("agenda_terminal_cmd", DEFAULT_AGENDA_TERMINAL_CMD)
        ),
    )
