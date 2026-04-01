## `claude_agent_sdk.client`

本模块定义 **交互式/双向** 客户端 `ClaudeSDKClient`。它的核心价值是：

- 连接保持：一次 `connect()` 后保持控制通道不断开
- 随时发送：随时 `query(...)` 追加新消息
- 随时接收：用 `receive_messages()` 或 `receive_response()` 消费消息流
- 运行时控制：中断、切换权限模式、切换模型、重连/禁用 MCP server、停止任务、rewind 文件等

---

## `class ClaudeSDKClient`

### `__init__(self, options=None, transport=None)`

**用途**

- 创建客户端实例，但不会立刻连接；连接在 `connect()` 或 `async with ...` 时发生。

**参数**

- **`options: ClaudeAgentOptions | None`**：客户端配置。`None` 时用默认 `ClaudeAgentOptions()`。
- **`transport: Transport | None`**：自定义 transport（高级用法）。不传则默认用子进程 transport。

**重要字段（实例属性）**

- **`self.options`**：最终使用的配置。
- **`self._custom_transport`**：你传入的 transport。
- **`self._transport`**：真正连接后使用的 transport。
- **`self._query`**：内部控制协议处理器（`_internal.query.Query`），负责读写控制消息、初始化、hook 回调等。

---

### `_convert_hooks_to_internal_format(self, hooks) -> dict[str, list[dict[str, Any]]]`

**用途**

- 把 `types.HookMatcher` 的结构转换成内部 Query 所需的 dict 结构（给 CLI 控制协议用）。

**你需要关心吗**

- 一般不需要直接调用；它解释了为什么 `ClaudeAgentOptions.hooks` 要用 `HookMatcher` 列表组织。

---

### `async def connect(self, prompt=None) -> None`

**用途**

- 连接 Claude Code（启动/连接 CLI、初始化控制协议、准备接收消息）。

**参数**

- **`prompt: str | AsyncIterable[dict] | None`**
  - `None`：客户端会用一个“永不 yield 的空流”保持连接打开（适合交互式场景：先连上，等你后续不断 `query()`）。
  - `str`：会在连接后立即发出一条 user 消息（但注意：`can_use_tool` 回调要求 streaming 输入流，见下方限制）。
  - `AsyncIterable[dict]`：连接后会把这个输入流持续推给 CLI（ClaudeSDKClient 总是 streaming 模式）。

**关键行为/限制**

- 如果你设置了 `options.can_use_tool`：
  - **prompt 必须是 AsyncIterable**（否则会 `ValueError`）。
  - 且 `can_use_tool` 与 `permission_prompt_tool_name` **互斥**（同时设置会 `ValueError`）。
  - SDK 会自动把 `permission_prompt_tool_name` 设为 `"stdio"` 以启用权限控制协议。
- MCP（进程内 SDK server）：
  - `connect()` 会从 `options.mcp_servers` 里挑出 `type=="sdk"` 的配置，把其中 `instance` 抽出来交给内部 Query。
- 初始化超时：
  - 会读环境变量 `CLAUDE_CODE_STREAM_CLOSE_TIMEOUT`（毫秒），并折算出一个至少 60 秒的初始化超时。

---

### `async def receive_messages(self) -> AsyncIterator[Message]`

**用途**

- 持续接收消息流（不会自动停止）。

**行为**

- 如果未连接（`_query` 为空）：抛 `CLIConnectionError("Not connected...")`
- 内部会调用 `_internal.message_parser.parse_message(...)` 把原始 dict 转成 `types.Message`（`UserMessage`/`AssistantMessage`/`SystemMessage`/`ResultMessage`/...）。

**适合场景**

- 你要自己控制“什么时候停止接收”。

---

### `async def query(self, prompt, session_id="default") -> None`

**用途**

- 在 streaming 模式下向当前连接发送新消息。

**参数**

- **`prompt: str | AsyncIterable[dict]`**
  - `str`：会被包装成 `{"type": "user", "message": {...}, "session_id": ...}` 并写入 transport。
  - `AsyncIterable[dict]`：会逐条写入；若某条没有 `session_id` 字段，会自动补上参数 `session_id`。
- **`session_id: str`**：会话标识。默认 `"default"`。

**适合场景**

- 交互式对话：你可以收一段消息、再发下一段 prompt。

---

### `async def interrupt(self) -> None`

**用途**

- 发送中断信号（仅 streaming 模式有效；`ClaudeSDKClient` 本来就总是 streaming）。

**适合场景**

- Claude 正在长时间执行工具/输出，你希望中止并换个问题。

---

### `async def set_permission_mode(self, mode: str) -> None`

**用途**

- 会话进行中动态切换 `permission_mode`（例如从默认提示切换到自动接受 edits）。

**mode 常见值**

- `"default"` / `"acceptEdits"` / `"bypassPermissions"`

---

### `async def set_model(self, model: str | None = None) -> None`

**用途**

- 会话进行中动态切换模型（或传 `None` 回到默认）。

**注意**

- 具体 model 字符串由 Claude Code/平台支持决定；示例里给了若干形如 `claude-sonnet-...` 的值。

---

### `async def rewind_files(self, user_message_id: str) -> None`

**用途**

- 把“被追踪的文件”回滚到某个 **用户消息** 对应的文件快照。

**前置条件（缺一不可）**

- `ClaudeAgentOptions.enable_file_checkpointing=True`
- `ClaudeAgentOptions.extra_args={"replay-user-messages": None}`（这样消息流里会带 `UserMessage.uuid`，你才能拿到 `user_message_id`）

---

### `async def reconnect_mcp_server(self, server_name: str) -> None`

**用途**

- 对某个 MCP server 进行重连（例如状态为 failed / disconnected）。

---

### `async def toggle_mcp_server(self, server_name: str, enabled: bool) -> None`

**用途**

- 启用/禁用某个 MCP server：
  - 禁用会断开并移除其工具
  - 启用会重新连接并恢复其工具

---

### `async def stop_task(self, task_id: str) -> None`

**用途**

- 停止一个正在运行的“任务”（task）。

**结果**

- CLI 随后会在消息流里发出一个 `task_notification`（`TaskNotificationMessage`），其 `status` 为 `"stopped"`。

---

### `async def get_mcp_status(self) -> McpStatusResponse`

**用途**

- 查询当前配置的所有 MCP server 的连接状态、工具列表、错误信息等。

**返回**

- `McpStatusResponse`（形状见 `types.md`：包含 `mcpServers: list[McpServerStatus]`）。

---

### `async def get_server_info(self) -> dict[str, Any] | None`

**用途**

- 获取 connect 时初始化返回的 server 信息（例如可用命令、输出风格等）。

**行为**

- 返回内部 Query 上缓存的 `_initialization_result`。

---

### `async def receive_response(self) -> AsyncIterator[Message]`

**用途**

- 一个便利迭代器：接收消息直到（并包含）一个 `ResultMessage`，然后自动停止。

**适合场景**

- “我发一次 query，就收这一轮完整回复” 的常见用法。

---

### `async def disconnect(self) -> None`

**用途**

- 关闭内部 Query/transport 并清理状态。

---

### `async def __aenter__(self) -> ClaudeSDKClient`

**用途**

- 支持 `async with ClaudeSDKClient(...) as client:`。
- 进入上下文时会自动 `connect()`（默认用空流保持连接）。

---

### `async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool`

**用途**

- 退出上下文时总会 `disconnect()`。
- 返回 `False` 表示不吞异常（异常会正常向外抛）。

