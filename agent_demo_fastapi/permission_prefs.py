"""Load/save global permission preferences (JSON, atomic write)."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from .storage import package_dir

logger = logging.getLogger(__name__)

PREFS_FILENAME = "permission_prefs.json"

# permission_mode: None = CLI default; else one of SDK PermissionMode strings
DEFAULT_PREFS: dict[str, Any] = {
    "permission_mode": None,
    "auto_allow_read_tools": True,
    "auto_allow_safe_bash": True,
    "auto_allow_task": False,
    "safe_bash_patterns": [
        "ls",
        "pwd",
        "echo",
        "cat",
        "head",
        "tail",
        "wc",
        "find",
        "stat",
        "dir",
        "where",
        "type",
        "git status",
        "git branch",
        "git log",
        "git diff",
    ],
}


def default_permission_prefs_path() -> Path:
    return package_dir() / "data" / PREFS_FILENAME


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for k, v in patch.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)  # type: ignore[assignment]
        else:
            out[k] = v
    return out


def normalize_prefs(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Ensure all keys exist; coerce types."""
    base = deepcopy(DEFAULT_PREFS)
    if not raw:
        return base
    merged = _deep_merge(base, raw)
    if not isinstance(merged.get("safe_bash_patterns"), list):
        merged["safe_bash_patterns"] = list(DEFAULT_PREFS["safe_bash_patterns"])
    else:
        merged["safe_bash_patterns"] = [
            str(x).strip() for x in merged["safe_bash_patterns"] if str(x).strip()
        ]
    for key in (
        "auto_allow_read_tools",
        "auto_allow_safe_bash",
        "auto_allow_task",
    ):
        merged[key] = bool(merged.get(key))
    pm = merged.get("permission_mode")
    merged["permission_mode"] = pm if pm is None or pm == "" else str(pm).strip()
    if merged["permission_mode"] == "":
        merged["permission_mode"] = None
    return merged


def load_permission_prefs(path: Path | None = None) -> dict[str, Any]:
    path = path or default_permission_prefs_path()
    if not path.exists():
        return normalize_prefs({})
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return normalize_prefs({})
        return normalize_prefs(data)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("permission prefs load failed %s: %s", path, e)
        return normalize_prefs({})


def save_permission_prefs(data: dict[str, Any], path: Path | None = None) -> None:
    path = path or default_permission_prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_prefs(data)
    payload = json.dumps(normalized, ensure_ascii=False, indent=2)
    fd, tmp = tempfile.mkstemp(
        dir=path.parent, prefix=".permission_prefs_", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def apply_patch(current: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Merge patch into current (shallow for top-level keys except nested not used)."""
    merged = deepcopy(current)
    for k, v in patch.items():
        if k == "safe_bash_patterns":
            if v is not None:
                merged[k] = v
        elif k == "permission_mode":
            merged[k] = v
        elif v is not None:
            merged[k] = v
    return normalize_prefs(merged)
