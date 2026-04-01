## `examples/stderr_callback_example.py`

这个示例演示如何用 `ClaudeAgentOptions.stderr` **捕获 Claude Code CLI 的 stderr 调试输出**，便于你在集成 SDK 时做诊断、日志采集或告警。

---

### 顶部导入

- `asyncio`：运行 `async def main()`。
- 从 `claude_agent_sdk` 导入：
  - `ClaudeAgentOptions`：配置
  - `query`：一次性调用入口

---

### `async def main()`

**用途**

- 注册一个 `stderr_callback`，把 CLI 的 stderr 每行都收集起来，并可选择性打印包含 `[ERROR]` 的行。

**关键段落**

- `stderr_messages = []`：用于收集所有 stderr 行。
- `def stderr_callback(message: str): ...`：
  - 追加到 `stderr_messages`
  - 若包含 `[ERROR]` 则打印
- `options = ClaudeAgentOptions(stderr=stderr_callback, extra_args={"debug-to-stderr": None})`：
  - `stderr=...`：设置回调
  - `extra_args={"debug-to-stderr": None}`：给 CLI 打开“把 debug 打到 stderr”的开关（具体 flag 由 CLI 定义）
- `async for message in query(prompt="What is 2+2?", options=options): ...`：
  - 这里用 `hasattr(message, 'content')` 做了很宽松的输出展示（更推荐你按 `AssistantMessage/TextBlock` 解析，见 `quick_start` 示例）。
- 最后打印捕获到的 stderr 行数，以及第一行的前 100 字符。

**你怎么用在自己的智能体里**

- 把 `stderr_callback` 改成写入日志系统/文件（例如按级别过滤、做结构化日志）。
- 在排查 “为什么 CLI 没按预期工作/为什么解析失败” 时，这个回调非常关键。

---

### `if __name__ == "__main__": asyncio.run(main())`

标准脚本入口。

