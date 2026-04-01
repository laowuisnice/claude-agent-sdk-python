"""ClaudeSDKClient wrapper: multi-turn, streaming, tools, permission bridge."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, AsyncIterator

logger = logging.getLogger(__name__)

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
if TYPE_CHECKING:
    from agent_demo.permission_bridge import PermissionBridge

# Demo: avoid filling context; adjust as needed.
MAX_INJECT_CHARS = 32000

DEFAULT_OPTIONS = ClaudeAgentOptions(
    include_partial_messages=True,
    max_turns=32,
)


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
    """Build a block of prior turns for injection before the current user message."""
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
    """Best-effort text delta from Anthropic-style stream `event` JSON."""
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


class AgentService:
    """Holds one ClaudeSDKClient for the active conversation id."""

    def __init__(
        self,
        bridge: "PermissionBridge | None" = None,
        options: ClaudeAgentOptions | None = None,
    ) -> None:
        self._bridge = bridge
        self._base_options = options or DEFAULT_OPTIONS
        self._options_dirty = True
        self._client: ClaudeSDKClient | None = None
        self._conversation_id: str | None = None
        self._history_injected: bool = False
        self._lock = asyncio.Lock()
        self.last_task_id: str | None = None
        self.last_user_message_uuids: list[str] = []

    def set_options(self, options: ClaudeAgentOptions) -> None:
        """Replace options; next connect will pick them up."""
        self._base_options = options
        self._options_dirty = True

    def _effective_options(self) -> ClaudeAgentOptions:
        return self._base_options

    @property
    def connected_conversation_id(self) -> str | None:
        return self._conversation_id

    def get_client(self) -> ClaudeSDKClient | None:
        return self._client

    async def disconnect(self) -> None:
        if self._bridge:
            self._bridge.cancel_pending("会话已断开")
        if self._client is not None:
            try:
                logger.info("disconnect()")
                await self._client.disconnect()
            except (CLIConnectionError, OSError, RuntimeError) as e:
                logger.warning("disconnect raised: %s", e)
            self._client = None
        self._conversation_id = None
        self._history_injected = False

    async def switch_conversation(self) -> None:
        """Disconnect CLI session (e.g. when user picks another conversation)."""
        logger.info("switch_conversation()")
        async with self._lock:
            if self._bridge:
                self._bridge.cancel_pending("已切换会话")
            await self._disconnect_unlocked()

    async def _ensure_client(self, conversation_id: str) -> ClaudeSDKClient:
        if (
            self._client is not None
            and self._conversation_id == conversation_id
            and not self._options_dirty
        ):
            logger.debug(
                "reuse client conversation_id=%s history_injected=%s",
                conversation_id,
                self._history_injected,
            )
            return self._client
        await self._disconnect_unlocked()
        self._options_dirty = False
        logger.info("connect() new ClaudeSDKClient conversation_id=%s", conversation_id)
        client = ClaudeSDKClient(self._effective_options())
        await client.connect()
        self._client = client
        self._conversation_id = conversation_id
        self.last_task_id = None
        self.last_user_message_uuids = []
        return client

    async def _disconnect_unlocked(self) -> None:
        if self._bridge:
            self._bridge.cancel_pending("连接重置")
        if self._client is not None:
            try:
                logger.info("_disconnect_unlocked()")
                await self._client.disconnect()
            except (CLIConnectionError, OSError, RuntimeError) as e:
                logger.warning("_disconnect_unlocked raised: %s", e)
            self._client = None
        self._conversation_id = None
        self._history_injected = False

    async def interrupt_turn(self) -> str:
        c = self._client
        if not c:
            return "未连接"
        await c.interrupt()
        return "已发送 interrupt"

    async def set_perm_mode(self, mode: str) -> str:
        c = self._client
        if not c:
            return "未连接"
        await c.set_permission_mode(mode)  # type: ignore[arg-type]
        return f"permission_mode={mode}"

    async def set_model_cli(self, model: str) -> str:
        c = self._client
        if not c:
            return "未连接"
        await c.set_model(model.strip() or None)
        return f"model set"

    async def fetch_server_info(self) -> dict[str, Any] | str:
        c = self._client
        if not c:
            return {"error": "未连接"}
        info = await c.get_server_info()
        return info or {}

    async def fetch_context_usage(self) -> dict[str, Any] | str:
        c = self._client
        if not c:
            return {"error": "未连接"}
        return await c.get_context_usage()

    async def fetch_mcp_status(self) -> dict[str, Any] | str:
        c = self._client
        if not c:
            return {"error": "未连接"}
        return await c.get_mcp_status()

    async def reconnect_mcp(self, server_name: str) -> str:
        c = self._client
        if not c:
            return "未连接"
        await c.reconnect_mcp_server(server_name.strip())
        return f"reconnect requested: {server_name}"

    async def toggle_mcp(self, server_name: str, enabled: bool) -> str:
        c = self._client
        if not c:
            return "未连接"
        await c.toggle_mcp_server(server_name.strip(), enabled)
        return f"mcp {server_name} enabled={enabled}"

    async def stop_task_cli(self, task_id: str) -> str:
        c = self._client
        if not c:
            return "未连接"
        tid = task_id.strip() or (self.last_task_id or "")
        if not tid:
            return "无 task_id"
        await c.stop_task(tid)
        return f"stop_task({tid})"

    async def rewind_files_cli(self, user_message_id: str) -> str:
        c = self._client
        if not c:
            return "未连接"
        await c.rewind_files(user_message_id.strip())
        return f"rewind_files({user_message_id})"

    async def stream_responses(
        self,
        conversation_id: str,
        user_text: str,
        prior_messages: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        """
        Stream assistant text chunks for one user turn.

        prior_messages: messages before this user turn (no new user message yet).
        """
        async with self._lock:
            client = await self._ensure_client(conversation_id)
            inject = not self._history_injected and bool(prior_messages)
            query_text = build_query_text(
                user_text, prior_messages, inject_history=inject
            )
            logger.info(
                "query() conversation_id=%s inject_history=%s prior_turns=%d user_len=%d",
                conversation_id,
                inject,
                len(prior_messages),
                len(user_text),
            )
            logger.debug(
                "query_text preview: %s",
                query_text[:500] + ("…" if len(query_text) > 500 else ""),
            )
            self._history_injected = True
            await client.query(query_text)

        assistant_buffer = ""
        async for message in client.receive_response():
            kind = type(message).__name__
            logger.debug("receive_response message_type=%s", kind)
            if isinstance(message, AssistantMessage):
                t = _assistant_visible_text(message)
                if t:
                    assistant_buffer = t
                    logger.debug(
                        "AssistantMessage visible_len=%d preview=%s",
                        len(t),
                        t[:200] + ("…" if len(t) > 200 else ""),
                    )
                    yield assistant_buffer
            elif isinstance(message, StreamEvent):
                delta = _extract_delta_from_stream_event(message.event)
                if delta:
                    assistant_buffer += delta
                    yield assistant_buffer
            elif isinstance(message, UserMessage):
                u = _user_visible_text(message)
                if u:
                    assistant_buffer += u
                    yield assistant_buffer
                if message.uuid:
                    self.last_user_message_uuids.append(message.uuid)
                    self.last_user_message_uuids = self.last_user_message_uuids[-20:]
            elif isinstance(message, TaskNotificationMessage):
                self.last_task_id = message.task_id
                assistant_buffer += (
                    f"\n\n---\n**Task** `{message.task_id}` **{message.status}**\n"
                    f"{message.summary}\n"
                )
                yield assistant_buffer
                logger.info("TaskNotification task_id=%s status=%s", message.task_id, message.status)
            elif isinstance(message, SystemMessage):
                logger.debug("SystemMessage subtype=%s", message.subtype)
                continue
            elif isinstance(message, RateLimitEvent):
                logger.warning("RateLimitEvent: %s", message.rate_limit_info)
                continue
            elif isinstance(message, ResultMessage):
                logger.info(
                    "ResultMessage is_error=%s num_turns=%s cost_usd=%s stop_reason=%s",
                    message.is_error,
                    message.num_turns,
                    message.total_cost_usd,
                    message.stop_reason,
                )
                if message.is_error and message.errors:
                    extra = "\n\n[Error: " + "; ".join(message.errors) + "]"
                    assistant_buffer += extra
                    yield assistant_buffer
                break
            else:
                logger.debug("unhandled message type=%s", kind)
