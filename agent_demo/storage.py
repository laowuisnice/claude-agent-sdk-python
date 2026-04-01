"""JSON persistence for conversation list and chat messages."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _content_to_str(content: Any) -> str:
    """Gradio Chatbot may use str or structured content; JSON needs plain strings."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    try:
        return json.dumps(content, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(content)


def normalize_messages_for_json(messages: list[Any] | None) -> list[dict[str, str]]:
    """Turn Chatbot message list into JSON-safe ``[{role, content}, ...]``."""
    out: list[dict[str, str]] = []
    for raw in messages or []:
        try:
            if isinstance(raw, dict):
                d = raw
            elif hasattr(raw, "model_dump"):
                d = raw.model_dump()  # type: ignore[no-untyped-call]
            elif hasattr(raw, "__dict__"):
                d = vars(raw)
            else:
                d = dict(raw)  # type: ignore[arg-type]
            role = str(d.get("role", ""))
            content = _content_to_str(d.get("content"))
            out.append({"role": role, "content": content})
        except (TypeError, ValueError) as e:
            logger.warning("skip message (normalize failed): %s raw=%r", e, raw)
    return out

STORE_FILENAME = "conversations.json"


def default_store_path() -> Path:
    return Path(__file__).resolve().parent / STORE_FILENAME


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def empty_store() -> dict[str, Any]:
    return {"conversations": [], "active_id": None}


def load_store(path: Path | None = None) -> dict[str, Any]:
    path = path or default_store_path()
    if not path.exists():
        return empty_store()
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if "conversations" not in data:
        data["conversations"] = []
    if "active_id" not in data:
        data["active_id"] = None
    return data


def save_store(data: dict[str, Any], path: Path | None = None) -> None:
    path = path or default_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    fd, tmp = tempfile.mkstemp(
        dir=path.parent, prefix=".conversations_", suffix=".tmp"
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


def title_from_first_message(text: str, max_len: int = 40) -> str:
    one_line = " ".join(text.strip().split())
    if not one_line:
        return "新对话"
    return one_line[:max_len] + ("…" if len(one_line) > max_len else "")


def new_conversation(
    store: dict[str, Any], title: str | None = None
) -> dict[str, Any]:
    cid = str(uuid.uuid4())
    conv: dict[str, Any] = {
        "id": cid,
        "title": title or "新对话",
        "updated_at": _utc_now_iso(),
        "messages": [],
    }
    store["conversations"].insert(0, conv)
    store["active_id"] = cid
    return conv


def get_conversation(store: dict[str, Any], conv_id: str) -> dict[str, Any] | None:
    for c in store["conversations"]:
        if c["id"] == conv_id:
            return c
    return None


def upsert_conversation_messages(
    store: dict[str, Any],
    conv_id: str,
    messages: list[Any] | None,
    *,
    bump_title_from_user: bool = False,
) -> None:
    safe = normalize_messages_for_json(messages)
    logger.debug(
        "upsert_conversation_messages conv_id=%s messages=%d",
        conv_id,
        len(safe),
    )
    conv = get_conversation(store, conv_id)
    if conv is None:
        conv = {
            "id": conv_id,
            "title": "新对话",
            "updated_at": _utc_now_iso(),
            "messages": [],
        }
        store["conversations"].insert(0, conv)
    conv["messages"] = safe
    conv["updated_at"] = _utc_now_iso()
    if bump_title_from_user and safe:
        first_user = next(
            (m["content"] for m in safe if m.get("role") == "user"), None
        )
        if first_user:
            conv["title"] = title_from_first_message(first_user)


def set_active(store: dict[str, Any], conv_id: str | None) -> None:
    store["active_id"] = conv_id


def list_conversation_choices(
    store: dict[str, Any],
) -> list[tuple[str, str]]:
    """Return [(label, id), ...] sorted by updated_at descending (newest first)."""
    convs = sorted(
        store["conversations"],
        key=lambda c: c.get("updated_at") or "",
        reverse=True,
    )
    return [(c.get("title") or c["id"], c["id"]) for c in convs]


def delete_conversation(store: dict[str, Any], conv_id: str) -> bool:
    before = len(store["conversations"])
    store["conversations"] = [c for c in store["conversations"] if c["id"] != conv_id]
    if store.get("active_id") == conv_id:
        store["active_id"] = None
    return len(store["conversations"]) < before
