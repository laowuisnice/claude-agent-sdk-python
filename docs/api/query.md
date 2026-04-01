## `claude_agent_sdk.query`

这个模块只提供一个对外函数：`query()`，用于**一次性/单向**的调用。

---

## `async def query(*, prompt, options=None, transport=None) -> AsyncIterator[Message]`

**用途**

- 用于“把输入一次性发给 Claude Code CLI，然后把返回的消息流读出来”。
- 适合：脚本、批处理、CI、一次性问答、一次性生成/分析。
- 不适合：需要随时插话/打断/根据回复再发送下一条消息的交互式应用（那类用 `ClaudeSDKClient`）。

**参数**

- **`prompt: str | AsyncIterable[dict[str, Any]]`**
  - `str`：最常见，一次性 prompt。
  - `AsyncIterable[dict]`：所谓“streaming mode 的输入流”（仍然是**单向**：把流输入完，再收输出流）。dict 的形状在 docstring 里给了示例（包含 `type/message/session_id/...`）。
- **`options: ClaudeAgentOptions | None`**
  - 不传会默认 `ClaudeAgentOptions()`。
  - 你最常调的通常是：
    - `system_prompt`：系统提示词
    - `cwd`：工作目录（Claude Code 工具读写时的基准目录）
    - `permission_mode` / `allowed_tools` / `disallowed_tools`：工具权限策略
    - `mcp_servers`：自定义工具（MCP）
- **`transport: Transport | None`**
  - 高级用法：自定义与 CLI 的传输实现。
  - 一般不需要；不传时会走默认的传输选择逻辑。

**返回**

- `AsyncIterator[Message]`：异步迭代器，逐条产出消息对象（`Message` 是一个 union，见 `types.md`）。

**内部流程（理解即可）**

- 如果 `options` 为空：创建默认配置。
- 创建 `InternalClient()`，调用其 `process_query(...)`，逐条 `yield` 出来。

**常见坑**

- 你终端里看到的错误 `Claude: Not logged in · Please run /login` 并不是 Python 代码错，而是 **Claude Code CLI 没登录**（需要先完成 CLI 登录流程）。
- 如果你要做交互式体验（边收边发、或中途打断），不要用 `query()`，用 `ClaudeSDKClient`。

