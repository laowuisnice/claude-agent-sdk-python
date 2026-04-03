"""ClaudeSDKClient wrapper: multi-turn streaming + SSE events + permission bridge."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    RateLimitEvent,
    ResultMessage,
    StreamEvent,
    SystemMessage,
    TaskNotificationMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from claude_agent_sdk._errors import CLIConnectionError
from claude_agent_sdk.types import PermissionResultAllow, ToolPermissionContext

from .options import build_claude_options
from .permission_bridge import PermissionBridge
from .permission_policy import should_auto_allow

logger = logging.getLogger(__name__)

MAX_INJECT_CHARS = 32000


def _truncate(s: str, max_chars: int) -> str:
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 3] + "…"


def _short_json(obj: Any, limit: int = 1200) -> str:
    try:
        s = json.dumps(obj, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        s = str(obj)
    return s if len(s) <= limit else s[: limit - 3] + "…"


def format_history_for_injection(
    prior_messages: list[dict[str, str]], max_chars: int = MAX_INJECT_CHARS
) -> str:
    if not prior_messages:
        return ""
    lines: list[str] = []
    for m in prior_messages:
        role = m.get("role", "")
        content = (m.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            lines.append(f"User: {content}")
        elif role == "assistant":
            lines.append(f"Assistant: {content}")
        else:
            lines.append(f"{role}: {content}")
    block = "\n\n".join(lines)
    return _truncate(block, max_chars)


def build_query_text(
    user_text: str,
    prior_messages: list[dict[str, str]],
    *,
    inject_history: bool,
) -> str:
    if not inject_history or not prior_messages:
        return user_text
    hist = format_history_for_injection(prior_messages)
    if not hist:
        return user_text
    return (
        "### Prior conversation\n"
        f"{hist}\n\n"
        "### Current message\n"
        f"{user_text}"
    )


def _extract_delta_from_stream_event(event: dict[str, Any]) -> str:
    try:
        et = event.get("type")
        if et == "content_block_delta":
            delta = event.get("delta") or {}
            if delta.get("type") == "text_delta":
                return str(delta.get("text") or "")
        if et == "message_delta":
            delta = event.get("delta") or {}
            if delta.get("type") == "text_delta":
                return str(delta.get("text") or "")
        for key in ("text", "partial_json"):
            v = event.get(key)
            if isinstance(v, str) and v:
                return v
    except (TypeError, AttributeError):
        pass
    return ""


def _format_tool_use(block: ToolUseBlock) -> str:
    return (
        f"\n\n### Tool `{block.name}`\n"
        f"*id:* `{block.id}`\n\n"
        f"```json\n{_short_json(block.input)}\n```\n"
    )


def _format_tool_result(block: ToolResultBlock) -> str:
    err = " **(error)**" if block.is_error else ""
    c = block.content
    if isinstance(c, list):
        body = _short_json(c, 4000)
    else:
        body = (c or "") if isinstance(c, str) else str(c)
        body = _truncate(body, 4000)
    return f"\n\n#### Tool result `{block.tool_use_id}`{err}\n```\n{body}\n```\n"


def _assistant_visible_text(msg: AssistantMessage) -> str:
    parts: list[str] = []
    for block in msg.content:
        if isinstance(block, TextBlock):
            parts.append(block.text)
        elif isinstance(block, ToolUseBlock):
            parts.append(_format_tool_use(block))
        elif isinstance(block, ThinkingBlock):
            parts.append("\n\n*(thinking)*\n")
    return "".join(parts)


def _user_visible_text(msg: UserMessage) -> str:
    if isinstance(msg.content, str):
        return msg.content
    parts: list[str] = []
    for block in msg.content:
        if isinstance(block, TextBlock):
            parts.append(block.text)
        elif isinstance(block, ToolResultBlock):
            parts.append(_format_tool_result(block))
        elif isinstance(block, ToolUseBlock):
            parts.append(_format_tool_use(block))
    return "".join(parts)


class ConversationSession:
    """One conversation id: client, bridge, SSE emit, single turn lock."""

    def __init__(
        self,
        conversation_id: str,
        workspace_dir: Path,
        prefs_getter: Callable[[], dict[str, Any]],
    ) -> None:
        self.conversation_id = conversation_id
        self._workspace = workspace_dir
        self._prefs_getter = prefs_getter

        async def _on_pending(payload: dict[str, Any]) -> None:
            await self.emit(
                {
                    "type": "permission_request",
                    "request_id": payload.get("request_id"),
                    "tool_name": payload.get("tool_name"),
                    "input": payload.get("input"),
                    "tool_use_id": payload.get("tool_use_id"),
                    "agent_id": payload.get("agent_id"),
                }
            )

        self._bridge = PermissionBridge(on_pending=_on_pending)

        async def _can_use_tool_wrapped(
            tool_name: str,
            inp: dict[str, Any],
            context: ToolPermissionContext,
        ) -> Any:
            prefs = self._prefs_getter()
            if should_auto_allow(tool_name, inp, prefs):
                return PermissionResultAllow()
            return await self._bridge.can_use_tool(tool_name, inp, context)

        self._can_use_tool_wrapped = _can_use_tool_wrapped
        self._client: ClaudeSDKClient | None = None
        self._history_injected = False
        self._connect_lock = asyncio.Lock()
        self._turn_lock = asyncio.Lock()
        self._queues: list[asyncio.Queue[dict[str, Any]]] = []
        self._buffer: deque[dict[str, Any]] = deque(maxlen=500)
        self._seq = 0
        self._wake = asyncio.Condition()

    async def emit(self, event: dict[str, Any]) -> None:
        self._seq += 1
        ev = dict(event)
        ev["_seq"] = self._seq
        self._buffer.append(ev)
        async with self._wake:
            self._wake.notify_all()
        for q in self._queues:
            await q.put(ev)

    async def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._queues.append(q)
        for ev in self._buffer:
            await q.put(ev)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        if q in self._queues:
            self._queues.remove(q)

    async def poll_events(
        self, *, since: int, timeout_sec: float = 15.0
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Return events with _seq > since. If none available, wait up to timeout_sec.
        This is used to avoid long-lived SSE connections (HTTP long-poll style).
        """
        events = [ev for ev in self._buffer if int(ev.get("_seq", 0)) > since]
        if events:
            return events, int(events[-1].get("_seq", since))
        async with self._wake:
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=timeout_sec)
            except asyncio.TimeoutError:
                return [], since
        events = [ev for ev in self._buffer if int(ev.get("_seq", 0)) > since]
        if events:
            return events, int(events[-1].get("_seq", since))
        return [], since

    def allow_permission(self) -> None:
        self._bridge.allow()

    def deny_permission(self) -> None:
        self._bridge.deny()

    async def disconnect(self) -> None:
        self._bridge.cancel_pending("会话已断开")
        if self._client is not None:
            try:
                await self._client.disconnect()
            except (CLIConnectionError, OSError, RuntimeError) as e:
                logger.warning("disconnect: %s", e)
            self._client = None
        self._history_injected = False

    def _options(self) -> ClaudeAgentOptions:
        self._workspace.mkdir(parents=True, exist_ok=True)
        pm = self._prefs_getter().get("permission_mode")
        return build_claude_options(
            self._bridge,
            can_use_tool_override=self._can_use_tool_wrapped,
            cwd=self._workspace,
            permission_mode=pm,
        )

    async def _ensure_client(self) -> ClaudeSDKClient:
        async with self._connect_lock:
            if self._client is not None:
                return self._client
            opts = self._options()
            client = ClaudeSDKClient(opts)
            await client.connect()
            self._client = client
            self._history_injected = False
            return client

    def get_client(self) -> ClaudeSDKClient | None:
        return self._client

    def clear_event_buffer(self) -> None:
        self._buffer.clear()

    async def run_turn(
        self,
        user_text: str,
        prior_messages: list[dict[str, str]],
    ) -> str:
        """Run one user turn; return final assistant text for persistence."""
        async with self._turn_lock:
            self.clear_event_buffer()
            assistant_buffer = ""
            try:
                client = await self._ensure_client()
                inject = not self._history_injected and bool(prior_messages)
                query_text = build_query_text(
                    user_text, prior_messages, inject_history=inject
                )
                self._history_injected = True
                await client.query(query_text)

                async for message in client.receive_response():
                    kind = type(message).__name__
                    if isinstance(message, AssistantMessage):
                        t = _assistant_visible_text(message)
                        if t:
                            assistant_buffer = t
                            await self.emit({"type": "delta", "text": assistant_buffer})
                    elif isinstance(message, StreamEvent):
                        delta = _extract_delta_from_stream_event(message.event)
                        if delta:
                            assistant_buffer += delta
                            await self.emit({"type": "delta", "text": assistant_buffer})
                    elif isinstance(message, UserMessage):
                        u = _user_visible_text(message)
                        if u:
                            assistant_buffer += u
                            await self.emit({"type": "delta", "text": assistant_buffer})
                    elif isinstance(message, TaskNotificationMessage):
                        assistant_buffer += (
                            f"\n\n---\n**Task** `{message.task_id}` **{message.status}**\n"
                            f"{message.summary}\n"
                        )
                        await self.emit({"type": "delta", "text": assistant_buffer})
                    elif isinstance(message, SystemMessage) and not isinstance(
                        message, TaskNotificationMessage
                    ):
                        logger.debug("SystemMessage subtype=%s", message.subtype)
                        continue
                    elif isinstance(message, RateLimitEvent):
                        logger.warning("RateLimitEvent: %s", message.rate_limit_info)
                        continue
                    elif isinstance(message, ResultMessage):
                        await self.emit(
                            {
                                "type": "result",
                                "is_error": message.is_error,
                                "num_turns": message.num_turns,
                                "total_cost_usd": message.total_cost_usd,
                                "stop_reason": message.stop_reason,
                                "errors": message.errors,
                            }
                        )
                        if message.is_error and message.errors:
                            await self.emit(
                                {
                                    "type": "error",
                                    "message": "; ".join(message.errors),
                                }
                            )
                        break
                    else:
                        logger.debug("unhandled message type=%s", kind)
            except Exception as e:
                logger.exception("run_turn failed")
                await self.emit({"type": "error", "message": str(e)})
            finally:
                await self.emit({"type": "done"})
            return assistant_buffer


class SessionManager:
    """Maps conversation_id -> ConversationSession; disconnect others on focus."""

    _VALID_PERM = frozenset(
        {"default", "acceptEdits", "plan", "bypassPermissions", "dontAsk"}
    )

    def __init__(
        self,
        workspace_dir: Path,
        prefs_getter: Callable[[], dict[str, Any]],
    ) -> None:
        self._workspace = workspace_dir
        self._prefs_getter = prefs_getter
        self._sessions: dict[str, ConversationSession] = {}
        self._lock = asyncio.Lock()

    async def get_session(self, conversation_id: str) -> ConversationSession:
        async with self._lock:
            if conversation_id not in self._sessions:
                self._sessions[conversation_id] = ConversationSession(
                    conversation_id,
                    self._workspace,
                    self._prefs_getter,
                )
            return self._sessions[conversation_id]

    async def disconnect_others(self, keep_id: str) -> None:
        async with self._lock:
            for cid, sess in list(self._sessions.items()):
                if cid != keep_id:
                    await sess.disconnect()

    async def remove_session(self, conversation_id: str) -> None:
        async with self._lock:
            sess = self._sessions.pop(conversation_id, None)
        if sess:
            await sess.disconnect()

    async def disconnect_all(self) -> None:
        async with self._lock:
            items = list(self._sessions.items())
            self._sessions.clear()
        for _, sess in items:
            await sess.disconnect()

    async def apply_permission_mode_to_connected_clients(
        self, mode: str | None
    ) -> None:
        """Call SDK set_permission_mode on every connected client (if any)."""
        effective = "default" if mode is None else mode
        if effective not in self._VALID_PERM:
            logger.warning("ignore invalid permission_mode: %s", mode)
            return
        async with self._lock:
            sessions = list(self._sessions.values())
        for sess in sessions:
            client = sess.get_client()
            if client is None:
                continue
            try:
                await client.set_permission_mode(effective)  # type: ignore[arg-type]
            except (CLIConnectionError, OSError, RuntimeError, TypeError, ValueError) as e:
                logger.warning("set_permission_mode failed: %s", e)
