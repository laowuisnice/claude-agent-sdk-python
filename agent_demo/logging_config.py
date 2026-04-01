"""Configure stderr + file logging for the agent_demo (see AGENT_DEMO_LOG_LEVEL)."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

_CONFIGURED = False

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_LOG_DATEFMT = "%H:%M:%S"


def _parse_level(name: str = "AGENT_DEMO_LOG_LEVEL") -> int:
    raw = os.environ.get(name, "INFO").strip().upper()
    return getattr(logging, raw, logging.INFO)


def default_log_file_path() -> Path:
    """Append-only text log next to this package (override with AGENT_DEMO_LOG_FILE)."""
    override = os.environ.get("AGENT_DEMO_LOG_FILE", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (Path(__file__).resolve().parent / "demo_log.txt").resolve()


def configure_demo_logging() -> None:
    """Attach StreamHandler + FileHandler to the ``agent_demo`` logger tree."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    level = _parse_level()
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATEFMT)

    log = logging.getLogger("agent_demo")
    log.setLevel(level)
    if not log.handlers:
        h_err = logging.StreamHandler(sys.stderr)
        h_err.setFormatter(formatter)
        log.addHandler(h_err)

        log_path = default_log_file_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        h_file = logging.FileHandler(
            log_path,
            mode="a",
            encoding="utf-8",
        )
        h_file.setFormatter(formatter)
        log.addHandler(h_file)
    log.propagate = False

    if level > logging.DEBUG:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("uvicorn").setLevel(logging.WARNING)
