"""barcal-watcher — watch Caldir .ics files and bump a revision marker."""

from __future__ import annotations

import argparse
import signal
import sys
import threading
import time
from pathlib import Path

from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer

from barcal.config import Config, load_config

DEFAULT_REVISION_PATH = Path.home() / ".cache" / "barcal" / "revision"
DEBOUNCE_SECONDS = 0.5
WATCH_RETRY_SECONDS = 2.0
LOOP_INTERVAL = 0.5


def bump_revision(revision_path: Path) -> None:
    revision_path.parent.mkdir(parents=True, exist_ok=True)
    revision_path.touch()


class CaldirEventHandler(PatternMatchingEventHandler):
    def __init__(self, revision_path: Path, debounce: float = DEBOUNCE_SECONDS):
        super().__init__(patterns=["*.ics"], ignore_directories=True)
        self.revision_path = revision_path
        self.debounce = debounce
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def _schedule_bump(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.debounce, self._bump)
            self._timer.daemon = True
            self._timer.start()

    def _bump(self) -> None:
        with self._lock:
            self._timer = None
        bump_revision(self.revision_path)

    def on_created(self, event) -> None:
        self._schedule_bump()

    def on_modified(self, event) -> None:
        self._schedule_bump()

    def on_deleted(self, event) -> None:
        self._schedule_bump()

    def on_moved(self, event) -> None:
        self._schedule_bump()


def run(
    cfg: Config,
    revision_path: Path,
    debounce: float = DEBOUNCE_SECONDS,
    stop_event: threading.Event | None = None,
) -> None:
    stop = stop_event or threading.Event()
    observer: Observer | None = None
    missing_reported = False
    while not stop.is_set():
        if observer is not None and not cfg.caldir_path.is_dir():
            observer.stop()
            observer.join()
            observer = None
        if observer is None:
            if cfg.caldir_path.is_dir():
                handler = CaldirEventHandler(revision_path, debounce)
                observer = Observer()
                observer.daemon = True
                observer.schedule(handler, str(cfg.caldir_path), recursive=True)
                observer.start()
                bump_revision(revision_path)
                print(
                    f"barcal-watcher: watching {cfg.caldir_path} "
                    f"(revision: {revision_path})",
                    file=sys.stderr,
                )
                missing_reported = False
            elif not missing_reported:
                print(
                    f"barcal-watcher: {cfg.caldir_path} not found, "
                    f"retrying every {WATCH_RETRY_SECONDS:.0f}s",
                    file=sys.stderr,
                )
                missing_reported = True
        time.sleep(LOOP_INTERVAL)
    if observer is not None:
        observer.stop()
        observer.join()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="barcal-watcher",
        description="Watch Caldir .ics files and bump a revision marker.",
    )
    parser.add_argument("--config", type=Path, default=None, help="Path to config.toml")
    parser.add_argument(
        "--revision", type=Path, default=None, help="Revision marker path (default: ~/.cache/barcal/revision)"
    )
    parser.add_argument(
        "--debounce", type=float, default=DEBOUNCE_SECONDS, help="Debounce window in seconds"
    )
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    revision_path = args.revision or DEFAULT_REVISION_PATH
    stop_event = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop_event.set())
    signal.signal(signal.SIGTERM, lambda *_: stop_event.set())

    run(cfg, revision_path, args.debounce, stop_event)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
