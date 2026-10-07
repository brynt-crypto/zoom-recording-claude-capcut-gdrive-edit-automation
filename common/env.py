"""Read settings from the environment, falling back to a repo-root ``.env``.

Nothing private is baked into this repo: every machine-specific value (Drive
folders, media roots, the host's on-screen name) is read from here. Copy
``.env.example`` to ``.env`` and fill in your own values — ``.env`` is
gitignored.

No dependency on python-dotenv; the format is plain ``KEY=VALUE`` per line.
"""
from __future__ import annotations
import os
from pathlib import Path

# Repo root (this file lives in <root>/common/).
BASE = Path(__file__).resolve().parent.parent


def _read_dotenv(path: Path | None = None) -> dict:
    """Best-effort parse of a repo-root ``.env``. Returns {} if absent."""
    env: dict = {}
    path = path or BASE / ".env"
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


_DOTENV = _read_dotenv()


def env(name: str, default: str = "") -> str:
    """Environment variable, falling back to the repo-root ``.env``, then
    ``default``. An empty value counts as unset."""
    val = os.environ.get(name)
    if val:
        return val
    return _DOTENV.get(name, default)


def env_list(name: str, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Comma-separated setting as a tuple, e.g. ``HOST_NAMES=Jordan,Jo``."""
    raw = env(name)
    if not raw:
        return default
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def env_path(name: str, default: Path | str) -> Path:
    """Path setting, expanding ``~``; ``default`` when unset."""
    raw = env(name)
    return Path(raw).expanduser() if raw else Path(default).expanduser()
