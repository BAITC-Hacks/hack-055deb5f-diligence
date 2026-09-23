"""Small, resilient JSON storage layer used by the Streamlit application."""

from __future__ import annotations

import copy
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
TASKS_FILE = DATA_DIR / "tasks.json"
PROPOSALS_FILE = DATA_DIR / "proposals.json"
TEAMS_FILE = DATA_DIR / "teams.json"

_STORAGE_LOCK = threading.RLock()


def _fresh_default(default: Any) -> Any:
    """Return a new default object so callers cannot share mutable state."""

    return copy.deepcopy([] if default is None else default)


def safe_save_json(file_path: str | os.PathLike[str], data: Any) -> None:
    """Atomically write JSON data using UTF-8.

    JSON is first serialised completely and then written to a temporary file in
    the destination directory.  ``os.replace`` makes the final swap atomic, so
    a rerun or interrupted process cannot leave a half-written JSON document.
    """

    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"

    temp_path: Path | None = None
    with _STORAGE_LOCK:
        try:
            descriptor, temp_name = tempfile.mkstemp(
                prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
            )
            temp_path = Path(temp_name)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, path)
            temp_path = None
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass


def safe_load_json(
    file_path: str | os.PathLike[str], default: Any = None
) -> Any:
    """Load JSON safely, returning a fresh default for missing/bad content.

    A missing or empty file is repaired with the supplied default.  Malformed
    non-empty data is deliberately left untouched for diagnosis/recovery while
    the application continues with the default value.
    """

    path = Path(file_path)
    fallback = _fresh_default(default)

    with _STORAGE_LOCK:
        if not path.exists():
            safe_save_json(path, fallback)
            return _fresh_default(fallback)

        try:
            raw_content = path.read_text(encoding="utf-8-sig")
        except OSError:
            return _fresh_default(fallback)

        if not raw_content.strip():
            safe_save_json(path, fallback)
            return _fresh_default(fallback)

        try:
            return json.loads(raw_content)
        except (json.JSONDecodeError, UnicodeError):
            return _fresh_default(fallback)


def _load_list(file_path: Path) -> list[dict[str, Any]]:
    data = safe_load_json(file_path, default=[])
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def load_tasks() -> list[dict[str, Any]]:
    """Load all task records."""

    return _load_list(TASKS_FILE)


def save_tasks(tasks: list[dict[str, Any]]) -> None:
    """Persist all task records atomically."""

    safe_save_json(TASKS_FILE, tasks)


def load_proposals() -> list[dict[str, Any]]:
    """Load all student proposal records."""

    return _load_list(PROPOSALS_FILE)


def save_proposals(proposals: list[dict[str, Any]]) -> None:
    """Persist all proposal records atomically."""

    safe_save_json(PROPOSALS_FILE, proposals)


def load_teams() -> list[dict[str, Any]]:
    """Load all demo team profiles."""

    return _load_list(TEAMS_FILE)


def save_teams(teams: list[dict[str, Any]]) -> None:
    """Persist all team profiles atomically."""

    safe_save_json(TEAMS_FILE, teams)
