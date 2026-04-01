## `examples/tools_option.py`

这个示例专门演示 `ClaudeAgentOptions.tools` 的三种形态，并通过 `SystemMessage(subtype="init")` 验证“实际可用工具列表”。

你会在以下场景用到它的思路：

- 想**限制** Claude 可用的内置工具集合（而不只是“自动批准”）
- 想验证配置生效（读 init 系统消息）

---

### `async def tools_array_example()`

**用途**

- `tools=["Read", "Glob", "Grep"]`：只给出一小部分工具名，作为可用工具集。

**关键点**

- 构造 `ClaudeAgentOptions(tools=[...], max_turns=1)`
- 在 `query(...)` 的消息流里：
  - 遇到 `SystemMessage` 且 `subtype == "init"`：
    - 从 `message.data["tools"]` 读取工具列表并打印
  - 遇到 `AssistantMessage`：打印文本
  - 遇到 `ResultMessage`：打印 cost

---

### `async def tools_empty_array_example()`

**用途**

- `tools=[]`：示例说明这是“禁用所有内置工具”（只剩下纯对话能力；是否还允许某些基础能力由 CLI 行为决定）。

**验证方式**

- 同样从 init 系统消息里读 `tools` 列表，应当为空或极小。

---

### `async def tools_preset_example()`

**用途**

- `tools={"type": "preset", "preset": "claude_code"}`：使用默认 Claude Code 工具预设（通常是“全量默认工具集”）。

**验证方式**

- 从 init 系统消息里读 `tools`，并展示前 5 个工具名。

---

### `async def main()` / `anyio.run(main)`

按顺序运行三个子示例。

---

### 常见混淆（很重要）

- `tools`：更像“**定义可用工具集合**”（控制工具集本身）。
- `allowed_tools`：是“**自动批准**哪些工具调用”（减少权限提示），并不会从工具集中移除未列出的工具。

