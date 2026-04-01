"""Gradio UI: agent chat + tool permissions + developer controls."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Allow `python agent_demo/app.py` from repo root
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import gradio as gr

from claude_agent_sdk._errors import CLIConnectionError

from agent_demo.agent_service import AgentService
from agent_demo.logging_config import configure_demo_logging, default_log_file_path
from agent_demo.options_factory import build_claude_options
from agent_demo.permission_bridge import PermissionBridge
from agent_demo.storage import (
    get_conversation,
    list_conversation_choices,
    load_store,
    new_conversation,
    normalize_messages_for_json,
    save_store,
    set_active,
    upsert_conversation_messages,
)

_CSS = """
.gradio-container { max-width: 1280px !important; margin: auto !important; }
.sidebar-col { border-right: 1px solid var(--border-color-primary); padding-right: 12px; }
.main-chat { min-height: 420px; }
"""

logger = logging.getLogger(__name__)

PERM_MODE_CHOICES = [
    "",
    "default",
    "acceptEdits",
    "plan",
    "bypassPermissions",
    "dontAsk",
]

bridge = PermissionBridge()
service = AgentService(bridge, build_claude_options(bridge))


def _ensure_store() -> dict:
    store = load_store()
    changed = False
    if not store["conversations"]:
        new_conversation(store)
        changed = True
    if store.get("active_id") is None and store["conversations"]:
        store["active_id"] = store["conversations"][0]["id"]
        changed = True
    if changed:
        save_store(store)
    return store


def _dropdown_update(store: dict) -> gr.Dropdown:
    choices = list_conversation_choices(store)
    values = [c[1] for c in choices]
    active = store.get("active_id")
    val = active if active in values else (values[0] if values else None)
    return gr.Dropdown(choices=choices, value=val)


def apply_advanced_settings(
    cwd: str,
    allowed_tools: str,
    disallowed_tools: str,
    permission_mode: str,
    enable_checkpoint: bool,
    extra_args_json: str,
    stderr_to_log: bool,
) -> str:
    opts = build_claude_options(
        bridge,
        cwd=cwd or None,
        allowed_tools=allowed_tools or None,
        disallowed_tools=disallowed_tools or None,
        permission_mode=permission_mode or None,
        enable_file_checkpointing=enable_checkpoint,
        extra_args_json=extra_args_json or None,
        stderr_to_log=stderr_to_log,
    )
    service.set_options(opts)
    return "已应用高级设置；下次发送消息时会用新选项重新连接 CLI。"


async def on_new_chat(current_conv_id: str | None, chat_history: list | None):
    logger.info(
        "on_new_chat() current_conv_id=%s history_len=%s",
        current_conv_id,
        len(chat_history or []),
    )
    store = load_store()
    if current_conv_id and chat_history:
        upsert_conversation_messages(
            store, current_conv_id, chat_history, bump_title_from_user=True
        )
    await service.switch_conversation()
    new_conversation(store)
    save_store(store)
    cid = store["active_id"]
    return (
        _dropdown_update(store),
        [],
        "",
        cid,
    )


async def on_conv_select(
    new_id: str | None,
    current_conv_id: str | None,
    chat_history: list | None,
):
    logger.info(
        "on_conv_select() new_id=%s current_conv_id=%s history_len=%s",
        new_id,
        current_conv_id,
        len(chat_history or []),
    )
    store = load_store()
    if current_conv_id and chat_history is not None:
        upsert_conversation_messages(
            store, current_conv_id, chat_history, bump_title_from_user=True
        )
    await service.switch_conversation()
    if new_id:
        set_active(store, new_id)
        save_store(store)
        conv = get_conversation(store, new_id)
        msgs = list(conv["messages"]) if conv else []
    else:
        msgs = []
    return msgs, new_id


async def on_submit(
    user_text: str,
    history: list | None,
    conv_id: str | None,
):
    if not user_text or not str(user_text).strip():
        yield history or [], gr.update(), gr.update(), conv_id
        return

    store = _ensure_store()
    if conv_id is None or get_conversation(store, conv_id) is None:
        conv_id = store["active_id"]

    history = list(history or [])
    prior = normalize_messages_for_json(history)
    logger.info(
        "on_submit() conv_id=%s prior_turns=%d user_preview=%s",
        conv_id,
        len(prior),
        str(user_text).strip()[:120],
    )
    user_text = str(user_text).strip()
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": ""})

    yield history, gr.update(value=""), gr.update(), conv_id

    try:
        chunk_count = 0
        async for chunk in service.stream_responses(conv_id, user_text, prior):
            chunk_count += 1
            history[-1]["content"] = chunk
            yield history, gr.update(), gr.update(), conv_id
        logger.info(
            "on_submit() stream done conv_id=%s chunks=%d reply_len=%d",
            conv_id,
            chunk_count,
            len(history[-1].get("content") or ""),
        )
    except (CLIConnectionError, OSError, RuntimeError) as e:
        logger.exception("on_submit() stream failed: %s", e)
        history[-1]["content"] = (history[-1]["content"] or "") + f"\n\n[错误: {e}]"
        yield history, gr.update(), gr.update(), conv_id

    st = load_store()
    try:
        upsert_conversation_messages(st, conv_id, history, bump_title_from_user=True)
        save_store(st)
        logger.info("on_submit() saved conv_id=%s", conv_id)
    except (OSError, TypeError, ValueError) as e:
        logger.exception("on_submit() save_store failed: %s", e)
        history[-1]["content"] = (
            (history[-1].get("content") or "")
            + f"\n\n[保存会话失败: {e}]"
        )
    yield history, gr.update(value=""), _dropdown_update(load_store()), conv_id


def build_ui() -> gr.Blocks:
    store = _ensure_store()
    choices = list_conversation_choices(store)
    initial_id = store.get("active_id")
    initial_msgs: list = []
    if initial_id:
        c = get_conversation(store, initial_id)
        if c:
            initial_msgs = list(c["messages"])

    with gr.Blocks(title="Claude Agent Demo") as demo:
        conv_id_state = gr.State(initial_id)

        gr.Markdown(
            "# Claude Agent Demo\n"
            "基于 `ClaudeSDKClient`：多轮对话、**工具调用**、流式输出、`can_use_tool` 权限按钮。"
        )

        with gr.Row(equal_height=True):
            with gr.Column(scale=1, min_width=240, elem_classes="sidebar-col"):
                gr.Markdown("### 会话")
                conv_dropdown = gr.Dropdown(
                    label="历史会话",
                    choices=choices,
                    value=initial_id,
                    allow_custom_value=False,
                )
                new_btn = gr.Button("新建会话", variant="secondary")

                gr.Markdown("### 待处理工具权限")
                perm_panel = gr.Markdown("*（无待处理工具权限请求）*")
                with gr.Row():
                    allow_btn = gr.Button("允许", variant="primary")
                    deny_btn = gr.Button("拒绝", variant="stop")
                timer = gr.Timer(0.5)

                with gr.Accordion("高级设置（ClaudeAgentOptions）", open=False):
                    cwd_inp = gr.Textbox(label="cwd", placeholder="工作目录，默认仓库根目录")
                    allowed_inp = gr.Textbox(
                        label="allowed_tools",
                        placeholder="逗号分隔，如 Read,Write,Bash",
                        lines=2,
                    )
                    disallowed_inp = gr.Textbox(
                        label="disallowed_tools",
                        placeholder="逗号分隔",
                        lines=2,
                    )
                    perm_mode_inp = gr.Dropdown(
                        label="初始 permission_mode",
                        choices=PERM_MODE_CHOICES,
                        value="",
                    )
                    checkpoint_cb = gr.Checkbox(
                        label="enable_file_checkpointing（用于 rewind_files）",
                        value=False,
                    )
                    extra_args_inp = gr.Textbox(
                        label="extra_args（JSON 对象，会与 replay-user-messages 合并）",
                        placeholder='{"foo": null}',
                        lines=3,
                    )
                    stderr_cb = gr.Checkbox(label="stderr 写入日志", value=True)
                    apply_btn = gr.Button("应用高级设置")
                    apply_status = gr.Markdown("")

                with gr.Accordion("开发者：ClaudeSDKClient 方法", open=False):
                    dev_out = gr.JSON(label="调用结果")
                    interrupt_btn = gr.Button("interrupt()")
                    perm_mode_dev = gr.Dropdown(
                        label="set_permission_mode",
                        choices=[
                            "default",
                            "acceptEdits",
                            "plan",
                            "bypassPermissions",
                            "dontAsk",
                        ],
                        value="default",
                    )
                    perm_mode_apply = gr.Button("应用权限模式")
                    model_inp = gr.Textbox(label="set_model", placeholder="如 claude-sonnet-4-5")
                    model_btn = gr.Button("apply model")
                    srv_btn = gr.Button("get_server_info()")
                    ctx_btn = gr.Button("get_context_usage()")
                    mcp_btn = gr.Button("get_mcp_status()")
                    mcp_reconnect = gr.Textbox(label="reconnect_mcp_server 名称")
                    mcp_reconnect_btn = gr.Button("重连 MCP")
                    mcp_toggle_name = gr.Textbox(label="toggle_mcp_server 名称")
                    mcp_toggle_en = gr.Checkbox(label="enabled", value=True)
                    mcp_toggle_btn = gr.Button("toggle MCP")
                    stop_task_inp = gr.Textbox(
                        label="stop_task(task_id) 留空则用 last_task_id",
                        placeholder="task id",
                    )
                    stop_task_btn = gr.Button("stop_task")
                    rewind_inp = gr.Textbox(
                        label="rewind_files(user_message_id)",
                        placeholder="UserMessage.uuid",
                    )
                    rewind_btn = gr.Button("rewind_files")

            with gr.Column(scale=4):
                chatbot = gr.Chatbot(
                    label="对话",
                    value=initial_msgs,
                    height=460,
                    elem_classes="main-chat",
                    render_markdown=True,
                )
                with gr.Row():
                    chat_input = gr.Textbox(
                        placeholder="输入消息…（Enter 提交）",
                        lines=3,
                        scale=5,
                        show_label=False,
                    )
                    submit_btn = gr.Button(
                        "发送",
                        variant="primary",
                        scale=1,
                        min_width=96,
                        icon="arrow-right",
                    )

        # --- Events ---
        timer.tick(lambda: bridge.pending_markdown(), outputs=[perm_panel])
        allow_btn.click(bridge.allow)
        deny_btn.click(bridge.deny)

        apply_btn.click(
            apply_advanced_settings,
            inputs=[
                cwd_inp,
                allowed_inp,
                disallowed_inp,
                perm_mode_inp,
                checkpoint_cb,
                extra_args_inp,
                stderr_cb,
            ],
            outputs=[apply_status],
        )

        async def _interrupt() -> dict:
            return {"result": await service.interrupt_turn()}

        async def _pm_mode(v: str) -> dict:
            return {"result": await service.set_perm_mode(v)}

        async def _model(v: str) -> dict:
            return {"result": await service.set_model_cli(v)}

        async def _srv() -> dict:
            return await service.fetch_server_info()

        async def _ctx() -> dict:
            return await service.fetch_context_usage()

        async def _mcp() -> dict:
            return await service.fetch_mcp_status()

        async def _mcp_rec(name: str) -> dict:
            return {"result": await service.reconnect_mcp(name)}

        async def _mcp_tog(name: str, en: bool) -> dict:
            return {"result": await service.toggle_mcp(name, en)}

        async def _stop(tid: str) -> dict:
            return {"result": await service.stop_task_cli(tid)}

        async def _rew(uid: str) -> dict:
            return {"result": await service.rewind_files_cli(uid)}

        interrupt_btn.click(_interrupt, outputs=[dev_out])
        perm_mode_apply.click(_pm_mode, inputs=[perm_mode_dev], outputs=[dev_out])
        model_btn.click(_model, inputs=[model_inp], outputs=[dev_out])
        srv_btn.click(_srv, outputs=[dev_out])
        ctx_btn.click(_ctx, outputs=[dev_out])
        mcp_btn.click(_mcp, outputs=[dev_out])
        mcp_reconnect_btn.click(_mcp_rec, inputs=[mcp_reconnect], outputs=[dev_out])
        mcp_toggle_btn.click(
            _mcp_tog, inputs=[mcp_toggle_name, mcp_toggle_en], outputs=[dev_out]
        )
        stop_task_btn.click(_stop, inputs=[stop_task_inp], outputs=[dev_out])
        rewind_btn.click(_rew, inputs=[rewind_inp], outputs=[dev_out])

        conv_dropdown.change(
            fn=on_conv_select,
            inputs=[conv_dropdown, conv_id_state, chatbot],
            outputs=[chatbot, conv_id_state],
        )

        new_btn.click(
            fn=on_new_chat,
            inputs=[conv_id_state, chatbot],
            outputs=[conv_dropdown, chatbot, chat_input, conv_id_state],
        )

        chat_input.submit(
            on_submit,
            inputs=[chat_input, chatbot, conv_id_state],
            outputs=[chatbot, chat_input, conv_dropdown, conv_id_state],
        )
        submit_btn.click(
            on_submit,
            inputs=[chat_input, chatbot, conv_id_state],
            outputs=[chatbot, chat_input, conv_dropdown, conv_id_state],
        )

    return demo


def main() -> None:
    configure_demo_logging()
    logger.info(
        "Starting agent_demo log_file=%s (set AGENT_DEMO_LOG_LEVEL=DEBUG for verbose)",
        default_log_file_path(),
    )
    demo = build_ui()
    demo.queue(default_concurrency_limit=8)
    demo.launch(theme=gr.themes.Soft(), css=_CSS)


if __name__ == "__main__":
    main()
