## `examples/max_budget_usd.py`

这个示例演示 `ClaudeAgentOptions.max_budget_usd`：用美元预算对单次 query 的成本做上限控制。

核心要点（来自示例说明）：

- 预算检查通常发生在 **每次 API 调用完成之后**，所以最终成本可能会略微超过设定预算（最多超出一次调用的成本量级）。

---

### `async def without_budget()`

**用途**

- 不设置预算，展示正常情况下 `ResultMessage.total_cost_usd` 和 `ResultMessage.subtype`。

**逻辑**

- `query("What is 2 + 2?")`
- `AssistantMessage/TextBlock`：打印回答
- `ResultMessage`：
  - 打印 `total_cost_usd`（若有）
  - 打印 `subtype`（状态）

---

### `async def with_reasonable_budget()`

**用途**

- 设置一个“不会被轻易超出”的预算（示例用 `$0.10`）。

**关键点**

- `options = ClaudeAgentOptions(max_budget_usd=0.10)`
- 其余处理逻辑同上。

---

### `async def with_tight_budget()`

**用途**

- 设置一个非常紧的预算（示例用 `$0.0001`），并让任务更耗费（读 README 并总结），从而触发预算错误。

**关键点**

- `options = ClaudeAgentOptions(max_budget_usd=0.0001)`
- 对 `ResultMessage.subtype == "error_max_budget_usd"` 做特殊提示。

---

### `async def main()` / `anyio.run(main)`

按顺序运行三个子示例，并在末尾打印预算机制的注意事项。

**你怎么用在自己的智能体里**

- 对“自用智能体”来说，建议默认给一个保守的 `max_budget_usd`，并在 UI/日志里暴露 `ResultMessage.total_cost_usd`，方便你长期控成本。

