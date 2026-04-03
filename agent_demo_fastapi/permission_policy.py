"""Auto-allow rules for can_use_tool (before UI permission bridge)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_READ_TOOLS = frozenset({"Read", "Glob", "Grep"})


def _bash_command_text(inp: dict[str, Any]) -> str:
    cmd = inp.get("command")
    if isinstance(cmd, str):
        return cmd
    return ""


def _is_safe_bash_command(cmd: str, patterns: list[str]) -> bool:
    if not cmd or not cmd.strip():
        return False
    first_line = cmd.strip().split("\n")[0].strip()
    if not first_line:
        return False
    # Reject obvious chaining / substitution (demo-only heuristic)
    if any(
        bad in first_line
        for bad in (";", "|", "&&", "||", "`", "$(", "${", ">", "<", "\n")
    ):
        return False
    lower = first_line.lower()
    for p in patterns:
        pl = p.strip().lower()
        if not pl:
            continue
        if lower == pl:
            return True
        if lower.startswith(pl + " ") or lower.startswith(pl + "\t"):
            return True
    return False


def should_auto_allow(
    tool_name: str,
    inp: dict[str, Any],
    prefs: dict[str, Any],
) -> bool:
    """
    Return True if this tool call should be allowed without showing the UI prompt.
    """
    if prefs.get("auto_allow_read_tools") and tool_name in _READ_TOOLS:
        return True

    if prefs.get("auto_allow_task") and tool_name == "Task":
        return True

    if prefs.get("auto_allow_safe_bash") and tool_name == "Bash":
        patterns = prefs.get("safe_bash_patterns") or []
        if not isinstance(patterns, list):
            patterns = []
        cmd = _bash_command_text(inp)
        ok = _is_safe_bash_command(cmd, [str(x) for x in patterns])
        if ok:
            logger.debug("auto_allow Bash: %s", cmd[:80])
        return ok

    return False
