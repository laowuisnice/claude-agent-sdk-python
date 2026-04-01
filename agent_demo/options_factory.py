"""Build ClaudeAgentOptions for demo (can_use_tool, cwd, tools, stderr, checkpointing)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from claude_agent_sdk.types import ClaudeAgentOptions, PermissionMode

from agent_demo.permission_bridge import PermissionBridge

logger = logging.getLogger(__name__)

_VALID_PERM: tuple[PermissionMode, ...] = (
    "default",
    "acceptEdits",
    "plan",
    "bypassPermissions",
    "dontAsk",
)


def _parse_list(s: str | None) -> list[str]:
    if not s or not str(s).strip():
        return []
    return [p.strip() for p in str(s).replace("\n", ",").split(",") if p.strip()]


def build_claude_options(
    bridge: PermissionBridge,
    *,
    cwd: str | None = None,
    allowed_tools: str | None = None,
    disallowed_tools: str | None = None,
    permission_mode: str | PermissionMode | None = None,
    enable_file_checkpointing: bool = False,
    extra_args_json: str | None = None,
    stderr_to_log: bool = True,
) -> ClaudeAgentOptions:
    """Construct options; ``can_use_tool`` is wired to ``bridge``."""

    def _stderr_cb(line: str) -> None:
        logger.getChild("claude_cli").info("%s", line.rstrip("\n"))

    extra_args: dict[str, str | None] = {}
    if enable_file_checkpointing:
        extra_args["replay-user-messages"] = None
    if extra_args_json and str(extra_args_json).strip():
        import json

        try:
            parsed = json.loads(extra_args_json)
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    extra_args[str(k)] = v if v is None else str(v)
        except json.JSONDecodeError as e:
            logger.warning("extra_args_json invalid, ignoring: %s", e)

    cwd_path: str | Path | None = None
    if cwd and str(cwd).strip():
        cwd_path = Path(cwd).expanduser()

    pm: PermissionMode | None = None
    if permission_mode and str(permission_mode).strip():
        raw = str(permission_mode).strip()
        if raw in _VALID_PERM:
            pm = raw  # type: ignore[assignment]

    opts = ClaudeAgentOptions(
        include_partial_messages=True,
        max_turns=32,
        can_use_tool=bridge.can_use_tool,
        cwd=cwd_path,
        allowed_tools=_parse_list(allowed_tools),
        disallowed_tools=_parse_list(disallowed_tools),
        permission_mode=pm,
        enable_file_checkpointing=enable_file_checkpointing,
        extra_args=extra_args if extra_args else {},
        stderr=_stderr_cb if stderr_to_log else None,
    )
    return opts
