# Claude Agent Demo（Gradio）

基于本仓库的 `ClaudeSDKClient`：**多轮对话、工具调用（Bash/Write 等）、流式输出、`can_use_tool` 人工允许/拒绝**、同目录 JSON 持久化，以及「开发者」面板演示 Client 上的其它方法。

## 从零配置环境（新建虚拟环境）

**前提**：已安装 **Python 3.10+**，且能在终端执行 `python --version`。

以下路径请把 `d:\claude_agent_sdk\claude-agent-sdk-python` 换成你本机克隆的仓库根目录。

### Windows（PowerShell）

在仓库根目录执行：

```powershell
cd d:\claude_agent_sdk\claude-agent-sdk-python

# 1. 创建虚拟环境（目录名 .venv 可自定）
python -m venv .venv

# 2. 激活（每次新开终端都要先激活）
.\.venv\Scripts\Activate.ps1

# 若提示“无法加载，因为在此系统上禁止运行脚本”，可先执行：
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 3. 升级 pip（可选）
python -m pip install -U pip

# 4. 以可编辑方式安装本仓库 SDK，并安装 demo 依赖（含 Gradio）
pip install -e ".[demo]"

# 5. 验证
python -c "import gradio; import claude_agent_sdk; print('OK')"
```

### Windows（命令提示符 cmd）

```bat
cd /d d:\claude_agent_sdk\claude-agent-sdk-python
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -U pip
pip install -e ".[demo]"
```

### macOS / Linux（bash）

```bash
cd /path/to/claude-agent-sdk-python
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -e ".[demo]"
```

### 在 Cursor / VS Code 里选对解释器

1. `Ctrl+Shift+P` → 输入 **Python: Select Interpreter**。
2. 选择 **`.venv\Scripts\python.exe`**（或 `./.venv/bin/python`）。

### Claude Code CLI

本 SDK 会优先使用**随包提供的 Claude Code CLI**（详见仓库根目录 [README.md](../README.md) 的 Installation）。若你使用自定义 CLI，可在 `ClaudeAgentOptions(cli_path="...")` 中指定（本 demo 可在 `options_factory.py` 中扩展）。未正确配置时，运行 demo 可能出现连接错误。

### 可选：仅装 SDK、再单独装 Gradio

```bash
pip install -e .
pip install -r agent_demo/requirements.txt
```

## 运行

激活虚拟环境后，在**仓库根目录**执行：

```powershell
python -m agent_demo.app
```

若**没有**执行 `pip install -e .`（仅用源码），则需：

```powershell
$env:PYTHONPATH = "src"
python -m agent_demo.app
```

浏览器会打开 Gradio 页面（默认 `http://127.0.0.1:7860`）。

## 工具权限（`can_use_tool`）

- 当模型尝试调用需要授权的工具时，SDK 会调用 `PermissionBridge.can_use_tool`；界面左侧 **待处理工具权限** 会显示工具名与输入摘要。
- 请点击 **允许** 或 **拒绝**。流式回复会暂停直到你选择（定时器约每 0.5s 刷新说明文字）。
- **`permission_mode`（高级设置 / 开发者里的 set_permission_mode）** 仍会影响 CLI 侧默认策略；与逐次 `can_use_tool` 的关系以 [官方权限文档](https://platform.claude.com/docs/en/agent-sdk/permissions) 为准。
- **`bypassPermissions` / `dontAsk`** 会显著降低交互门槛，仅建议在受控环境使用。

## 工具与消息展示

- 助手回复中会内嵌 **Markdown**：`### Tool \`Name\`` 与工具输入摘要、**Tool result** 块（含错误标记）。
- 若 CLI 发出 **Task** 通知，会在对话中追加简短说明；`stop_task` 可使用最后一次通知中的 `task_id`（或手动输入）。

## 高级设置（`ClaudeAgentOptions`）

- **cwd**：工作目录。
- **allowed_tools / disallowed_tools**：逗号分隔列表。
- **初始 permission_mode**：未选表示使用 SDK 默认。
- **enable_file_checkpointing**：配合 **rewind_files**；并会自动合并 `extra_args` 中的 `replay-user-messages`（若需从流里拿到带 `uuid` 的 `UserMessage`，需满足 CLI/SDK 要求）。
- **extra_args**：JSON 对象，与上述项合并。
- **stderr 写入日志**：将 CLI 标准错误转发到 `agent_demo` 日志。

点击 **应用高级设置** 后，**下一次**建立连接时会使用新选项（当前会话会在发送前按需重连）。

## 开发者面板（`ClaudeSDKClient` 方法）

| 方法 | 说明 |
|------|------|
| `interrupt()` | 中断当前生成 |
| `set_permission_mode` | 运行时切换权限模式 |
| `set_model` | 切换模型 |
| `get_server_info` | 初始化阶段缓存的服务端信息 |
| `get_context_usage` | 上下文用量 |
| `get_mcp_status` | MCP 连接状态 |
| `reconnect_mcp_server` / `toggle_mcp_server` | 按名称重连或启停 MCP |
| `stop_task` | 停止任务（`task_id` 可空，使用最近一条任务 id） |
| `rewind_files` | 回滚文件（需 checkpoint 等前提） |

本 demo **主聊天循环**使用 `query` + `receive_response`（单轮直到 `ResultMessage`）。若需**不**在每条 `ResultMessage` 处截断、持续读取流，应改用 `receive_messages()`（见 SDK 文档与 `examples/streaming_mode.py`）。

### 包级 API（不在 `ClaudeSDKClient` 上）

例如 `list_sessions`、`get_session_messages`、`get_session_info`（见 `claude_agent_sdk` 包导出）。学习时可与 Client 流式会话对照使用。

## 终端日志与文件日志

- **终端**：`agent_demo` 命名空间日志。
- **文件**：`agent_demo/demo_log.txt`（UTF-8 追加）；`AGENT_DEMO_LOG_FILE` 可改路径。
- **级别**：`AGENT_DEMO_LOG_LEVEL=DEBUG` 可查看更细消息类型与 `query` 预览。

## 数据文件

- 会话与消息：`agent_demo/conversations.json`。
- **inject_history** 与长度上限见 `agent_service.py` 中 `MAX_INJECT_CHARS`。

## 说明

- 本 demo 仅用于学习 SDK 设计；生产环境需自行处理安全、配额与审计。
- CLI 与模型计费以 Anthropic / Claude Code 为准。
