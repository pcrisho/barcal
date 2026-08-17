"""Omarchy theme resolution: active slug -> colors.toml -> palette."""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

PALETTE_KEYS = ("mode", "accent", "muted", "background", "foreground", "selection")

DEFAULT_PALETTE: dict[str, str] = {
    "mode": "dark",
    "accent": "#8d8d8d",
    "muted": "#7a7a7a",
    "background": "#000000",
    "foreground": "#ffffff",
    "selection": "#1a1a1a",
}

USER_THEMES_DIR = Path.home() / ".config" / "omarchy" / "themes"
STOCK_THEMES_DIR = Path("/usr/share/omarchy/themes")


def resolve_theme_slug() -> str | None:
    try:
        out = subprocess.run(
            ["omarchy", "theme", "current"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    slug = out.stdout.strip().lower().replace(" ", "-")
    return slug or None


def find_colors_path(slug: str) -> Path | None:
    for base in (USER_THEMES_DIR, STOCK_THEMES_DIR):
        candidate = base / slug / "colors.toml"
        if candidate.is_file():
            return candidate
    return None


def parse_colors_toml(path: Path) -> dict[str, str]:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return {key: str(data.get(key, DEFAULT_PALETTE[key])) for key in PALETTE_KEYS}


def resolve_palette() -> dict[str, str]:
    slug = resolve_theme_slug()
    path = find_colors_path(slug) if slug else None
    if path is None:
        return dict(DEFAULT_PALETTE)
    return parse_colors_toml(path)
