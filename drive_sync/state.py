"""Read/write the pipeline ledger (drive_sync/state.json).

The ledger keys are the *source recording filenames* from the Drive input
folder. Each entry remembers how far that recording got through the pipeline so
re-running /scan only surfaces genuinely new footage.
"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

from . import config


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load() -> dict:
    p = Path(config.STATE_FILE)
    if not p.exists():
        return {"processed": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return {"processed": {}}
    data.setdefault("processed", {})
    return data


def save(data: dict) -> None:
    p = Path(config.STATE_FILE)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def is_processed(source_name: str) -> bool:
    return source_name in load().get("processed", {})


def get(source_name: str) -> dict | None:
    return load().get("processed", {}).get(source_name)


def mark(source_name: str, **fields) -> dict:
    """Merge fields into the ledger entry for a source recording."""
    data = load()
    entry = data["processed"].get(source_name, {})
    entry.update(fields)
    entry.setdefault("first_seen", now())
    entry["updated_at"] = now()
    data["processed"][source_name] = entry
    save(data)
    return entry
