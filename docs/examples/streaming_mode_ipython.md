## `examples/streaming_mode_ipython.py`

这个文件不是“可直接运行的完整脚本”，而是一组 **IPython 友好** 的代码片段，设计目标是让你在 IPython/Jupyter 环境里**复制粘贴就能跑**，快速体验 `ClaudeSDKClient` 的 streaming 能力。

它覆盖了以下片段：

- 基础 streaming
- 实时显示（封装 `send_and_receive`）
- 持久 client（多次提问后再 disconnect）
- interrupt（中断）模式
- 错误处理（timeout）
- 发送 AsyncIterable 消息流
- 收集所有消息到 list 后再处理

---

### BASIC STREAMING 段

**用途**

- `async with ClaudeSDKClient()` → `await client.query(...)` → `async for msg in client.receive_response(): ...`

**你该怎么用**

- 在 IPython 里确保能直接运行 `await`（或使用 `anyio`/`nest_asyncio` 方案），然后粘贴整段。

---

### STREAMING WITH REAL-TIME DISPLAY 段

**用途**

- 定义 `send_and_receive(prompt)` helper，多次复用同一个 client。

---

### PERSISTENT CLIENT FOR MULTIPLE QUESTIONS 段

**用途**

- 演示不用上下文管理器，手动 `client = ClaudeSDKClient(); await client.connect(); ...; await client.disconnect()`。

**价值**

- 适合 notebook 中“长时间保持连接”的工作流。

---

### WITH INTERRUPT CAPABILITY 段

**关键点**

- 示范了一个重要原则：**interrupt 需要有活跃的消息消费**（后台 `consume_messages()`）。

---

### ERROR HANDLING PATTERN 段

**用途**

- `asyncio.timeout(...)` 包裹 `receive_response()`，演示如何做超时兜底。

---

### SENDING ASYNC ITERABLE OF MESSAGES 段

**用途**

- 用 `async def message_generator(): yield {...}` 一次性发送多条 user 消息。

---

### COLLECTING ALL MESSAGES INTO A LIST 段

**用途**

- `messages = [msg async for msg in client.receive_response()]` 收集后处理。

---

### 你怎么把它改造成自己的 notebook 工作流

- 把这些片段变成 notebook 里的“工具函数单元格”（例如 `get_response()`、`send_and_receive()`）。
- 结合 `include_partial_messages`（见另一个示例）做实时 UI/日志。

