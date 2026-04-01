## `examples/include_partial_messages.py`

这个示例演示 `ClaudeAgentOptions.include_partial_messages=True`：让 SDK 在 `receive_response()` 流里插入 `StreamEvent`（部分消息增量事件），用于实时 UI。

---

### 顶部导入

- `asyncio`
- `ClaudeSDKClient`
- 从 `claude_agent_sdk.types` 导入：
  - `ClaudeAgentOptions`
  - `StreamEvent` / `AssistantMessage` / `UserMessage` / `SystemMessage` / `ResultMessage`

> 注意：示例里导入了这些类型，但在循环里直接 `print(message)`，并未按类型分支处理；这是为了让你看到原始对象形态。

---

### `async def main()`

**用途**

- 开启 partial message streaming，发送一个 prompt，然后把 `receive_response()` 的每条消息对象原样打印出来。

**关键配置**

- `options = ClaudeAgentOptions(...)`：
  - `include_partial_messages=True`
  - `model="claude-sonnet-4-5"`
  - `max_turns=2`
  - `env={"MAX_THINKING_TOKENS": "8000"}`：通过环境变量调 thinking（示例用途）

**运行逻辑**

- `client = ClaudeSDKClient(options)`
- `await client.connect()`
- `await client.query(prompt)`
- `async for message in client.receive_response(): print(message)`
- `finally: await client.disconnect()`

---

### 你怎么用于自用智能体 UI

- 把 `print(message)` 换成：
  - 遇到 `StreamEvent`：把 `event` 里的增量文本拼到 UI（例如打字机效果）
  - 遇到 `AssistantMessage`：展示最终整段块内容
  - 遇到 `ToolUseBlock/ToolResultBlock`：在 UI 展示“正在执行工具/工具返回”
  - 遇到 `ResultMessage`：展示 cost、耗时等

