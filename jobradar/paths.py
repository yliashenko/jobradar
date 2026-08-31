"""Single source of truth for where data lives (testability requirement #1).

Mutable data — config.json, jobs.db, profile.json/.md, log, .lock — lives under
HOME. In prod HOME = project root (where they already were per ADR-0005). A test
or e2e sets a different HOME — and the whole isolation is ready WITHOUT copying
the tree and without monkeypatching module constants:

  - `JOBRADAR_HOME=/tmp/xxx python -m jobradar serve` — separate process (e2e);
  - `paths.use_home(tmp)` — override within the same process (pytest).

Both go through home(), so the code asks for a path the same way everywhere.
Logos (in resources/) are a CODE asset, not data: HOME does not affect them.
"""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_DIR = PACKAGE_DIR.parent

# In-process override. None → use JOBRADAR_HOME, otherwise the project root.
_override: Path | None = None


def use_home(path) -> None:
    """Set HOME for this process (pytest). None reverts to env/default."""
    global _override
    _override = Path(path) if path is not None else None


def home() -> Path:
    if _override is not None:
        return _override
    env = os.environ.get("JOBRADAR_HOME")
    return Path(env) if env else REPO_DIR


def config_path() -> str:
    return str(home() / "config.json")


def db_path() -> str:
    return str(home() / "jobs.db")


def profile_json_path() -> str:
    return str(home() / "profile.json")


def profile_md_path() -> str:
    return str(home() / "profile.md")


def career_facts_path() -> str:
    """The cover-letter fact source (career-facts.md), personal data under HOME."""
    return str(home() / "career-facts.md")


def log_path() -> str:
    return str(home() / "jobradar.log")


def lock_dir() -> str:
    return str(home() / ".lock")


def resources_dir() -> str:
    return str(REPO_DIR / "resources")


def static_dir() -> str:
    # Static assets (compiled app.css) are a code asset, living next to the package.
    return str(PACKAGE_DIR / "static")
