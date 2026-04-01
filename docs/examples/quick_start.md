## `examples/quick_start.py`

这个示例展示了如何用 **`query()`** 在三种典型场景下调用 Claude：

- 最简单的一次性问答
- 带自定义 `ClaudeAgentOptions` 的问答
- 允许 Claude 使用工具（例如读写文件）的问答

---

### 顶部导入

- `anyio`：用来运行顶层 `async def main()`
- 从 `claude_agent_sdk` 导入：
  - `AssistantMessage`：回答消息类型
  - `ClaudeAgentOptions`：配置结构
  - `ResultMessage`：单轮结束消息（含开销）
  - `TextBlock`：内容块，用来从 `AssistantMessage.content` 中抽文本
  - `query`：一次性调用入口

在你自己的项目里，一般也会以类似方式导入这些符号。

---

### `async def basic_example()`

**用途**

- 最小用法：只给一个字符串 prompt，不传 options。

**逻辑**

- 打印标题 `"=== Basic Example ==="`
- `async for message in query(prompt="What is 2 + 2?")`
  - 如果是 `AssistantMessage`：
    - 遍历 `message.content`
    - 对于 `TextBlock`，打印 `Claude: {block.text}`
- 末尾 `print()` 输出空行。

**改成你自己的版本**

- 把 `prompt` 换成你的问题；
- 或者直接把这个函数删掉，当模板看就行。

---

### `async def with_options_example()`

**用途**

- 展示如何配置 `ClaudeAgentOptions`（系统提示词 + 最大轮数）。

**逻辑**

- 打印标题 `"=== With Options Example ==="`
- 构造 `options = ClaudeAgentOptions(...)`：
  - `system_prompt`: 给模型的人设/任务说明
  - `max_turns=1`: 控制对话轮数
- 调用：
  - `async for message in query(prompt="Explain what Python is in one sentence.", options=options):`
  - 与 `basic_example` 类似，只是多了 options。

**你可以怎么用**

- 在你自己的脚本里，把这个函数改成：
  - 根据你的应用场景设置 `system_prompt`
  - 按需设置 `max_turns`/其他选项（见 `docs/api/types.md`）。

---

### `async def with_tools_example()`

**用途**

- 演示如何允许 Claude 使用工具（例如 `Read` / `Write`）。

**逻辑**

- 打印标题 `"=== With Tools Example ==="`
- `options = ClaudeAgentOptions(allowed_tools=["Read", "Write"], system_prompt="You are a helpful file assistant.")`
  - `allowed_tools`：自动批准这些工具；不动 CLI 工具全集，只是减少权限弹窗。
- 调用：
  - `async for message in query(prompt="当前文件夹中有哪些智能体", options=options):`
  - 对 `AssistantMessage` / `TextBlock` 打印文本
  - 对 `ResultMessage` 且 `total_cost_usd > 0` 时打印花费

**为什么重要**

- 这是你最常用的“代码助手/文件助手”模板：给定一个 `cwd`（可通过 `ClaudeAgentOptions.cwd` 设置）和一个带工具权限的 options，让 Claude 自动读/写项目文件。

---

### `async def main()`

**用途**

- 顺序跑完三个示例。

**逻辑**

- `await basic_example()`
- `await with_options_example()`
- `await with_tools_example()`

---

### `if __name__ == "__main__": anyio.run(main)`

**用途**

- 让你可以直接 `python examples/quick_start.py` 运行示例。

**你可以怎么改造成自己的脚本**

- 把上面的某一个/几个 example 函数改成你自己的逻辑，然后仍然用 `anyio.run(main)` 跑
- 或者在你的项目中新建一个 `my_agent.py`，直接复制这段结构作为骨架。

