## `examples/streaming_mode.py`

这是 `ClaudeSDKClient` 的“综合示例合集”，覆盖了 streaming 模式下最常见的应用模式：

- 基础 streaming
- 多轮对话
- 并发收发
- interrupt（中断）
- 手动消费消息流
- 带 options（工具、system prompt、env）
- AsyncIterable prompt（一次发送多条消息）
- bash 工具调用时的 ToolUse/ToolResult 观测
- 控制协议能力（server info、interrupt）
- 错误处理模式（超时、断开、finally disconnect）

脚本还支持命令行参数：列出示例/运行全部/运行单个示例。

---

### `def display_message(msg)`

**用途**

- 把常见消息类型统一格式化输出（User/Assistant 文本、忽略 System、Result 结束）。

**注意**

- 这里只展示了 TextBlock；如果你要调试工具调用，建议参考 `example_bash_command()` 的更完整分支。

---

### `async def example_basic_streaming()`

**用途**

- 最小 streaming：`async with ClaudeSDKClient() as client` → `client.query(...)` → `client.receive_response()`。

---

### `async def example_multi_turn_conversation()`

**用途**

- 同一个 client 里连续两轮 `query()`，展示上下文保留与 follow-up。

---

### `async def example_concurrent_responses()`

**用途**

- 展示“后台持续接收消息”与“前台持续发送问题”并发运行。

**关键点**

- `asyncio.create_task(receive_messages())`
- 最后 `cancel()` 并抑制 `CancelledError`。

---

### `async def example_with_interrupt()`

**用途**

- 演示 interrupt：先发一个长输出任务，再等待一会儿 `client.interrupt()`，然后继续发新问题。

**关键提示（示例自己也强调了）**

- **要让 interrupt 生效，必须在后台持续消费消息**（否则中断可能无法被处理/传递）。

---

### `async def example_manual_message_handling()`

**用途**

- 用 `receive_messages()` 手动处理流，做自定义逻辑（示例：从文本里提取语言名并计数）。

---

### `async def example_with_options()`

**用途**

- 展示 `ClaudeAgentOptions` 在 client 场景的用法：
  - `allowed_tools=["Read","Write"]`
  - `system_prompt="..."`
  - `env={"ANTHROPIC_MODEL":"claude-sonnet-4-5"}`

**额外逻辑**

- 统计本轮 assistant 中出现过的工具名（通过检查 block 是否有 `name` 且不是 `TextBlock` 来近似识别 ToolUseBlock）。

---

### `async def example_async_iterable_prompt()`

**用途**

- 展示 `client.query(prompt_async_iterable)`：一次性发送一个异步消息流（包含 3 条 user 消息），然后分别调用 3 次 `receive_response()` 来取三次回答。

---

### `async def example_bash_command()`

**用途**

- 更完整地观察工具调用相关块：
  - `AssistantMessage` 里可能出现 `ToolUseBlock`
  - `UserMessage` 里可能出现 `ToolResultBlock`

---

### `async def example_control_protocol()`

**用途**

- 获取 `client.get_server_info()`（init 结果），并演示 interrupt。

---

### `async def example_error_handling()`

**用途**

- 展示连接错误捕获、对 `receive_response()` 做超时处理、以及 `finally: disconnect()` 的标准模式。

---

### `async def main()`

**用途**

- 通过 `sys.argv` 选择运行哪一个示例：
  - 无参数：列出 key
  - `all`：全部运行
  - `<key>`：运行单个

---

### 你如何把它改成自己的“终端自用智能体”

- 保留 `ClaudeSDKClient` + `receive_messages()` 的并发结构（类似 `example_concurrent_responses`），把“发送消息”替换成读取用户输入（REPL）。
- 用 `include_partial_messages` 做实时输出（参考另一个示例）。
- 用 `interrupt` 实现 Ctrl+C 风格的“打断当前任务”体验。

