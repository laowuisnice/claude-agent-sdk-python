"""FastAPI app: REST + SSE for Claude Agent SDK demo."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent_service import SessionManager
from .storage import (
    default_store_path,
    delete_conversation,
    get_conversation,
    load_store,
    new_conversation,
    save_store,
    set_active,
    upsert_conversation_messages,
)

logger = logging.getLogger(__name__)

PACKAGE_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = PACKAGE_DIR / "workspace"
STATIC_DIR = PACKAGE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO)
    yield
    app.state.shutting_down = True
    # Cancel any background tasks created by request handlers so Ctrl+C can exit
    tasks: set[asyncio.Task[Any]] = getattr(app.state, "bg_tasks", set())
    for t in list(tasks):
        t.cancel()
    if tasks:
        with suppress(Exception):
            await asyncio.wait(tasks, timeout=2.0)
    sm: SessionManager = app.state.session_manager
    await sm.disconnect_all()


app = FastAPI(title="Claude Agent SDK FastAPI Demo", lifespan=lifespan)
app.state.session_manager = SessionManager(WORKSPACE_DIR)
app.state.shutting_down = False
app.state.bg_tasks = set()


class CreateConversationBody(BaseModel):
    title: str | None = None


class PostMessageBody(BaseModel):
    text: str = Field(..., min_length=1)


class PermissionBody(BaseModel):
    allow: bool


def _store() -> dict[str, Any]:
    return load_store(default_store_path())


def _save(data: dict[str, Any]) -> None:
    save_store(data, default_store_path())


@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    return {"ok": True, "shutting_down": bool(getattr(app.state, "shutting_down", False))}


@app.get("/api/conversations")
async def list_conversations() -> dict[str, Any]:
    data = _store()
    convs = sorted(
        data["conversations"],
        key=lambda c: c.get("updated_at") or "",
        reverse=True,
    )
    return {
        "conversations": [
            {"id": c["id"], "title": c.get("title"), "updated_at": c.get("updated_at")}
            for c in convs
        ],
        "active_id": data.get("active_id"),
    }


@app.post("/api/conversations")
async def create_conversation(body: CreateConversationBody) -> dict[str, Any]:
    data = _store()
    conv = new_conversation(data, title=body.title)
    _save(data)
    return {"conversation": conv}


@app.get("/api/conversations/{conv_id}")
async def get_conv(conv_id: str) -> dict[str, Any]:
    data = _store()
    conv = get_conversation(data, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"conversation": conv}


@app.delete("/api/conversations/{conv_id}")
async def remove_conv(conv_id: str) -> dict[str, Any]:
    data = _store()
    if not get_conversation(data, conv_id):
        raise HTTPException(status_code=404, detail="conversation not found")
    delete_conversation(data, conv_id)
    _save(data)
    sm: SessionManager = app.state.session_manager
    await sm.remove_session(conv_id)
    return {"ok": True}


@app.post("/api/conversations/{conv_id}/active")
async def set_active_conv(conv_id: str) -> dict[str, Any]:
    data = _store()
    if not get_conversation(data, conv_id):
        raise HTTPException(status_code=404, detail="conversation not found")
    set_active(data, conv_id)
    _save(data)
    sm: SessionManager = app.state.session_manager
    await sm.disconnect_others(conv_id)
    return {"ok": True}


@app.post("/api/conversations/{conv_id}/messages")
async def post_message(conv_id: str, body: PostMessageBody) -> dict[str, Any]:
    data = _store()
    conv = get_conversation(data, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="conversation not found")

    prior = [dict(m) for m in conv.get("messages", [])]
    user_text = body.text.strip()
    new_messages = prior + [{"role": "user", "content": user_text}]
    upsert_conversation_messages(
        data, conv_id, new_messages, bump_title_from_user=True
    )
    _save(data)

    sm: SessionManager = app.state.session_manager
    await sm.disconnect_others(conv_id)
    session = await sm.get_session(conv_id)

    async def run_and_persist() -> None:
        try:
            assistant_text = await session.run_turn(user_text, prior)
            store = load_store(default_store_path())
            c = get_conversation(store, conv_id)
            if c:
                msgs = c["messages"] + [
                    {"role": "assistant", "content": assistant_text}
                ]
                upsert_conversation_messages(store, conv_id, msgs)
                save_store(store, default_store_path())
        except asyncio.CancelledError:
            # Server is shutting down; exit quietly
            return
        except Exception:
            logger.exception("run_and_persist failed")

    task = asyncio.create_task(run_and_persist())
    app.state.bg_tasks.add(task)
    task.add_done_callback(lambda t: app.state.bg_tasks.discard(t))
    return {"ok": True}


@app.post("/api/conversations/{conv_id}/permission")
async def post_permission(conv_id: str, body: PermissionBody) -> dict[str, Any]:
    sm: SessionManager = app.state.session_manager
    session = await sm.get_session(conv_id)
    if body.allow:
        session.allow_permission()
    else:
        session.deny_permission()
    return {"ok": True}


@app.get("/api/conversations/{conv_id}/events")
async def sse_events(conv_id: str) -> StreamingResponse:
    data = _store()
    if not get_conversation(data, conv_id):
        raise HTTPException(status_code=404, detail="conversation not found")

    sm: SessionManager = app.state.session_manager
    session = await sm.get_session(conv_id)

    async def event_generator():
        q = await session.subscribe()
        try:
            while True:
                ev = await q.get()
                line = json.dumps(ev, ensure_ascii=False)
                yield f"data: {line}\n\n"
        except asyncio.CancelledError:
            raise
        finally:
            session.unsubscribe(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/conversations/{conv_id}/events_poll")
async def poll_events(
    conv_id: str,
    since: int = Query(0, ge=0),
    timeout_sec: float = Query(2.0, ge=0.0, le=30.0),
) -> dict[str, Any]:
    """
    Short/long polling endpoint to avoid long-lived connections.
    Returns quickly when new events arrive, otherwise returns empty list after timeout.
    """
    if bool(getattr(app.state, "shutting_down", False)):
        raise HTTPException(status_code=503, detail="server shutting down")
    data = _store()
    if not get_conversation(data, conv_id):
        raise HTTPException(status_code=404, detail="conversation not found")
    sm: SessionManager = app.state.session_manager
    session = await sm.get_session(conv_id)
    events, next_since = await session.poll_events(since=since, timeout_sec=timeout_sec)
    return {"events": events, "next_since": next_since}


@app.get("/")
async def index() -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=500, detail="static/index.html missing")
    return FileResponse(index_path)


app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "agent_demo_fastapi.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )
