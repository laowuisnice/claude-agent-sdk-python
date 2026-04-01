## `examples/streaming_mode_trio.py`

这个示例演示如何在 **trio** 运行时中使用 `ClaudeSDKClient` 做多轮对话（与 asyncio/anyio 类似，但 event loop 不同）。

---

### `def display_message(msg)`

**用途**

- 统一打印：
  - `UserMessage/TextBlock` → `User: ...`
  - `AssistantMessage/TextBlock` → `Claude: ...`
  - `SystemMessage` 忽略
  - `ResultMessage` 打印结束

---

### `async def multi_turn_conversation()`

**用途**

- 在一个 `async with ClaudeSDKClient(...)` 的上下文里连续发送 3 个问题，并逐轮 `receive_response()`。

**关键点**

- `ClaudeSDKClient(options=ClaudeAgentOptions(model="claude-sonnet-4-5"))`
  - 展示在 trio 下同样可以用 options 选模型。
- 每轮：
  - `await client.query(...)`
  - `async for message in client.receive_response(): display_message(message)`

---

### `if __name__ == "__main__": trio.run(multi_turn_conversation)`

**用途**

- trio 的标准启动方式。

---

### 你怎么用

- 如果你的应用（或你依赖的库）原生使用 trio，这个文件提供了最小可用模板。
- 如果你不需要 trio，直接用 `examples/streaming_mode.py`（asyncio）或你自己的 anyio 脚本即可。

