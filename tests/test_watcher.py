import threading
import time

import pytest
from watchdog.observers import Observer

from barcal.config import Config
from barcal.watcher import CaldirEventHandler, bump_revision, run

POLL_TIMEOUT = 5.0
POLL_INTERVAL = 0.05


def wait_until(predicate, timeout: float = POLL_TIMEOUT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(POLL_INTERVAL)
    return False


def test_bump_revision_creates_file(tmp_path):
    revision = tmp_path / "nested" / "dir" / "revision"
    bump_revision(revision)
    assert revision.is_file()


def test_bump_revision_updates_mtime(tmp_path):
    revision = tmp_path / "revision"
    bump_revision(revision)
    first_mtime = revision.stat().st_mtime_ns
    time.sleep(0.02)
    bump_revision(revision)
    assert revision.stat().st_mtime_ns > first_mtime


def test_handler_bumps_after_debounce(tmp_path):
    revision = tmp_path / "revision"
    handler = CaldirEventHandler(revision, debounce=0.1)
    handler.on_created(None)
    assert wait_until(revision.exists)
    assert handler._timer is None


def test_handler_debounces_burst(tmp_path):
    revision = tmp_path / "revision"
    handler = CaldirEventHandler(revision, debounce=0.1)
    for _ in range(10):
        handler.on_modified(None)
    assert wait_until(revision.exists)
    mtime = revision.stat().st_mtime_ns
    time.sleep(0.25)
    assert revision.stat().st_mtime_ns == mtime


def test_watch_detects_new_ics_file(tmp_path):
    caldir = tmp_path / "caldir"
    caldir.mkdir()
    revision = tmp_path / "revision"
    handler = CaldirEventHandler(revision, debounce=0.1)
    observer = Observer()
    observer.daemon = True
    observer.schedule(handler, str(caldir), recursive=True)
    observer.start()
    try:
        (caldir / "new-event.ics").write_text("BEGIN:VCALENDAR\nEND:VCALENDAR\n")
        assert wait_until(revision.exists)
    finally:
        observer.stop()
        observer.join()


def test_watch_ignores_non_ics_files(tmp_path):
    caldir = tmp_path / "caldir"
    caldir.mkdir()
    revision = tmp_path / "revision"
    handler = CaldirEventHandler(revision, debounce=0.1)
    observer = Observer()
    observer.daemon = True
    observer.schedule(handler, str(caldir), recursive=True)
    observer.start()
    try:
        (caldir / "notes.txt").write_text("nothing")
        time.sleep(0.5)
        assert not revision.exists()
    finally:
        observer.stop()
        observer.join()


def test_watch_recursive_subdirectories(tmp_path):
    provider_dir = tmp_path / "caldir" / "google"
    provider_dir.mkdir(parents=True)
    revision = tmp_path / "revision"
    handler = CaldirEventHandler(revision, debounce=0.1)
    observer = Observer()
    observer.daemon = True
    observer.schedule(handler, str(tmp_path / "caldir"), recursive=True)
    observer.start()
    try:
        (provider_dir / "event.ics").write_text("BEGIN:VCALENDAR\nEND:VCALENDAR\n")
        assert wait_until(revision.exists)
    finally:
        observer.stop()
        observer.join()


def test_run_starts_when_caldir_appears(tmp_path):
    caldir = tmp_path / "caldir"
    revision = tmp_path / "revision"
    stop_event = threading.Event()
    cfg = Config(caldir_path=caldir)

    thread = threading.Thread(
        target=run, args=(cfg, revision), kwargs={"debounce": 0.1, "stop_event": stop_event},
        daemon=True,
    )
    thread.start()
    try:
        caldir.mkdir()
        assert wait_until(revision.exists)
        (caldir / "a.ics").write_text("BEGIN:VCALENDAR\nEND:VCALENDAR\n")
        first_mtime = revision.stat().st_mtime_ns
        assert wait_until(
            lambda: revision.stat().st_mtime_ns != first_mtime
        )
    finally:
        stop_event.set()
        thread.join(timeout=POLL_TIMEOUT)


def test_run_stops_cleanly(tmp_path):
    caldir = tmp_path / "caldir"
    caldir.mkdir()
    revision = tmp_path / "revision"
    stop_event = threading.Event()
    cfg = Config(caldir_path=caldir)

    thread = threading.Thread(
        target=run, args=(cfg, revision), kwargs={"debounce": 0.1, "stop_event": stop_event},
        daemon=True,
    )
    thread.start()
    try:
        time.sleep(0.5)
        stop_event.set()
        thread.join(timeout=POLL_TIMEOUT)
        assert not thread.is_alive()
    finally:
        stop_event.set()
