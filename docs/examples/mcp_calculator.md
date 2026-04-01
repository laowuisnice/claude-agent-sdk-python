## `examples/mcp_calculator.py`

这个示例演示了如何用 **SDK MCP（进程内 MCP 服务器）** 把一组 Python 函数暴露为 Claude 可调用的计算器工具，并通过 `ClaudeSDKClient` 在对话中使用这些工具。

---

### 顶部导入

- 标准库：
  - `asyncio`
  - `typing.Any`
- 从 `claude_agent_sdk` 导入：
  - `ClaudeAgentOptions`
  - `create_sdk_mcp_server`
  - `tool`（装饰器）

在 `display_message` 和 `main` 里，会额外从 SDK 导入消息/内容块类型和 `ClaudeSDKClient`。

---

### 一组用 `@tool` 定义的计算器工具

每个工具函数都遵循同一模式：

- 使用 `@tool("name", "description", {"param": type, ...})` 装饰
- `async def func(args: dict[str, Any]) -> dict[str, Any]:`
- 返回形如 `{"content": [{"type": "text", "text": "..."}], "is_error": True?}` 的 dict

#### `add_numbers`

- 装饰器：`@tool("add", "Add two numbers", {"a": float, "b": float})`
- 功能：返回 `"a + b = 结果"`

#### `subtract_numbers`

- 装饰器：`@tool("subtract", "Subtract one number from another", {"a": float, "b": float})`
- 功能：返回 `"a - b = 结果"`

#### `multiply_numbers`

- 装饰器：`@tool("multiply", "Multiply two numbers", {"a": float, "b": float})`
- 功能：返回 `"a × b = 结果"`

#### `divide_numbers`

- 装饰器：`@tool("divide", "Divide one number by another", {"a": float, "b": float})`
- 特殊处理：
  - 若 `b == 0`，返回 `is_error=True` 并输出错误文本；
  - 否则返回 `"a ÷ b = 结果"`。

#### `square_root`

- 装饰器：`@tool("sqrt", "Calculate square root", {"n": float})`
- 特殊处理：
  - 若 `n < 0`，返回错误信息并 `is_error=True`；
  - 否则使用 `math.sqrt` 计算平方根。

#### `power`

- 装饰器：`@tool("power", "Raise a number to a power", {"base": float, "exponent": float})`
- 功能：返回 `"base^exponent = 结果"`。

**你可以如何扩展**

- 按照同样的签名再加其它函数（例如三角函数、统计函数等），然后在 `create_sdk_mcp_server(..., tools=[...])` 里把它们加入列表即可。

---

### `def display_message(msg)`

**用途**

- 把从 `ClaudeSDKClient.receive_response()` 拿到的各种消息类型格式化输出成可读文本，方便在终端观察。

**内部逻辑（根据类型分支）**

- `UserMessage`：
  - 遍历 `msg.content`：
    - `TextBlock` → 打印 `"User: ..."`
    - `ToolResultBlock` → 打印截断的 tool 结果（前 100 字符）
- `AssistantMessage`：
  - 遍历 `msg.content`：
    - `TextBlock` → 打印 `"Claude: ..."`
    - `ToolUseBlock` → 打印使用的工具名以及输入参数
- `SystemMessage`：
  - 直接忽略（pass）
- `ResultMessage`：
  - 打印 `"Result ended"`，若有 `total_cost_usd` 则打印花费

**你在自己的项目里可以照抄/改造这段逻辑来调试复杂对话。**

---

### `async def main()`

**用途**

- 把上面定义的所有工具注册到一个进程内 MCP server，然后通过 `ClaudeSDKClient` 在若干 prompt 中使用这些工具。

**关键步骤**

1. 导入 `ClaudeSDKClient`
2. 创建 MCP server：
   - ```python
     calculator = create_sdk_mcp_server(
         name="calculator",
         version="2.0.0",
         tools=[add_numbers, subtract_numbers, multiply_numbers, divide_numbers, square_root, power],
     )
     ```
3. 构造 `ClaudeAgentOptions`：
   - `mcp_servers={"calc": calculator}`：把这个服务器挂到别名 `"calc"` 上
   - `allowed_tools=[ "mcp__calc__add", ..., "mcp__calc__power" ]`：预批准所有计算器工具
4. 准备一组 `prompts`（“列出工具”、“计算表达式”等）。
5. 对每个 prompt：
   - 打印分隔线和 prompt 文本
   - `async with ClaudeSDKClient(options=options) as client:`
     - `await client.query(prompt)`：发起一次 query
     - `async for message in client.receive_response(): display_message(message)`

**你在自己的项目里如何迁移**

- 把 `calculator` 换成你的业务工具 server（例如访问数据库、调用内部 HTTP API 等）。
- 用类似 `mcp__<alias>__<tool_name>` 的名字添加到 `allowed_tools`。
- 把 `prompts` 换成与你业务相关的自然语言任务。

---

### `if __name__ == "__main__": asyncio.run(main())`

**用途**

- 让你直接通过 `python examples/mcp_calculator.py` 运行示例。

**在你的项目中**

- 若你已经在用 `anyio.run`，也可以改成用 `anyio.run(main)`；核心是入口的 async event loop 实现，无关 SDK 本身。  

