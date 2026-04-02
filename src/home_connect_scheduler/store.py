from __future__ import annotations

import fcntl
from pathlib import Path

import orjson

from home_connect_scheduler.models import AppData

MAX_RUN_LOG = 50
DATA_DIR = Path.home() / ".hcs"
DATA_FILE = DATA_DIR / "data.json"


def _ensure_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load() -> AppData:
    _ensure_dir()
    if not DATA_FILE.exists():
        return AppData()
    with open(DATA_FILE, "rb") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        try:
            raw = f.read()
            return AppData.model_validate(orjson.loads(raw)) if raw else AppData()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def save(data: AppData) -> None:
    _ensure_dir()
    data.run_log = data.run_log[-MAX_RUN_LOG:]
    raw = orjson.dumps(data.model_dump(mode="json"), option=orjson.OPT_INDENT_2)
    with open(DATA_FILE, "wb") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(raw)
            f.flush()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    DATA_FILE.chmod(0o600)
