"""can_use_tool bridge: pending Future resolved by HTTP allow/deny."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from claude_agent_sdk.types import (
    PermissionResult,
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)

logger = logging.getLogger(__name__)

OnPending = Callable[[dict[str, Any]], Awaitable[None]]


class PermissionBridge:
    """Async permission gate; HTTP handler calls allow()/deny() to resolve Future."""

    def __init__(
        self,
        on_pending: OnPending | None = None,
        *,
        wait_timeout_sec: float = 900.0,
    ) -> None:
        self._lock = asyncio.Lock()
        self._future: asyncio.Future[PermissionResult] | None = None
        self.pending: dict[str, Any] | None = None
        self.request_id = 0
        self._on_pending = on_pending
        self._wait_timeout_sec = wait_timeout_sec

    def set_on_pending(self, cb: OnPending | None) -> None:
        self._on_pending = cb

    def pending_payload(self) -> dict[str, Any] | None:
        return dict(self.pending) if self.pending else None

    async def can_use_tool(
        self,
        tool_name: str,
        input: dict[str, Any],
        context: ToolPermissionContext,
    ) -> PermissionResult:
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        payload: dict[str, Any]
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
            payload = dict(self.pending)
        logger.info(
            "can_use_tool pending request_id=%s tool=%s tool_use_id=%s",
            rid,
            tool_name,
            context.tool_use_id,
        )
        if self._on_pending:
            try:
                await self._on_pending(payload)
            except Exception:
                logger.exception("on_pending failed")
        await asyncio.sleep(0)
        try:
            return await asyncio.wait_for(fut, timeout=self._wait_timeout_sec)
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
        self._resolve(PermissionResultDeny(message=message, interrupt=False))


def pending_to_json_preview(p: dict[str, Any] | None, max_len: int = 4000) -> str:
    if not p:
        return ""
    inp = p.get("input")
    try:
        inp_s = json.dumps(inp, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        inp_s = str(inp)
    if len(inp_s) > max_len:
        inp_s = inp_s[: max_len - 1] + "…"
    return inp_s
