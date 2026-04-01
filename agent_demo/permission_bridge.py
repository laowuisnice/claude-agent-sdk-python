"""Gradio-friendly can_use_tool bridge: pending Future + Allow/Deny."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from claude_agent_sdk.types import (
    PermissionResult,
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)

logger = logging.getLogger(__name__)


class PermissionBridge:
    """Async permission gate; UI calls allow()/deny() to resolve the pending Future."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._future: asyncio.Future[PermissionResult] | None = None
        self.pending: dict[str, Any] | None = None
        self.request_id = 0

    def pending_markdown(self) -> str:
        """Render current pending request for Gradio Markdown."""
        p = self.pending
        if not p:
            return "*（无待处理工具权限请求）*"
        inp = p.get("input")
        try:
            inp_s = json.dumps(inp, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            inp_s = str(inp)
        if len(inp_s) > 4000:
            inp_s = inp_s[:3997] + "…"
        return (
            f"**请求 #{p.get('request_id')}** — `tool_name={p.get('tool_name')}`\n\n"
            f"`tool_use_id`: `{p.get('tool_use_id')}`\n\n"
            f"```json\n{inp_s}\n```\n\n"
            "请点击 **允许** 或 **拒绝**。"
        )

    async def can_use_tool(
        self,
        tool_name: str,
        input: dict[str, Any],
        context: ToolPermissionContext,
    ) -> PermissionResult:
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        async with self._lock:
            self.request_id += 1
            rid = self.request_id
            self._future = fut
            self.pending = {
                "request_id": rid,
                "tool_name": tool_name,
                "input": input,
                "tool_use_id": context.tool_use_id,
                "agent_id": context.agent_id,
            }
        logger.info(
            "can_use_tool pending request_id=%s tool=%s tool_use_id=%s",
            rid,
            tool_name,
            context.tool_use_id,
        )
        await asyncio.sleep(0)
        try:
            return await asyncio.wait_for(fut, timeout=3600.0)
        except asyncio.TimeoutError:
            logger.warning("can_use_tool timeout request_id=%s", rid)
            return PermissionResultDeny(message="等待用户操作超时", interrupt=False)
        finally:
            async with self._lock:
                if self._future is fut:
                    self._future = None
                self.pending = None

    def allow(self) -> None:
        self._resolve(PermissionResultAllow())

    def deny(self) -> None:
        self._resolve(PermissionResultDeny(message="用户拒绝", interrupt=False))

    def _resolve(self, result: PermissionResult) -> None:
        fut = self._future
        if fut is not None and not fut.done():
            fut.set_result(result)
            logger.info(
                "can_use_tool resolved behavior=%s",
                getattr(result, "behavior", type(result).__name__),
            )

    def cancel_pending(self, message: str = "会话已断开") -> None:
        """Deny any in-flight permission (e.g. on disconnect)."""
        self._resolve(PermissionResultDeny(message=message, interrupt=False))
