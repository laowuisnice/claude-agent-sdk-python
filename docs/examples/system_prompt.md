## `examples/system_prompt.py`

这个示例演示 `ClaudeAgentOptions.system_prompt` 的常见配置方式：

- 不设置 system prompt
- system prompt 直接给字符串
- 用 preset（`{"type": "preset", "preset": "claude_code"}`）
- preset + append（在预设后追加额外要求）

---

### `async def no_system_prompt()`

**用途**

- 不传 `options`，相当于“原生/默认”行为。

**逻辑**

- `query(prompt="What is 2 + 2?")` 并打印 `AssistantMessage` 中的 `TextBlock`。

---

### `async def string_system_prompt()`

**用途**

- 用字符串 system prompt 指定角色/风格（例：海盗口吻）。

**关键点**

- `options = ClaudeAgentOptions(system_prompt="You are a pirate assistant...")`
- 其余与 `no_system_prompt` 相同。

---

### `async def preset_system_prompt()`

**用途**

- 使用 Claude Code 默认预设 system prompt（通常更贴近“代码工具助理”的行为）。

**关键点**

- `system_prompt={"type": "preset", "preset": "claude_code"}`

---

### `async def preset_with_append()`

**用途**

- 在预设基础上追加约束（例：每次回复末尾加一个 fun fact）。

**关键点**

- `system_prompt={"type":"preset","preset":"claude_code","append":"..."}`。

---

### `async def main()` / `anyio.run(main)`

依次运行四个子示例。

**注意**

- 本文件末尾是 `anyio.run(main)`（传函数本身，不是 `main()`）。这在 anyio 里是正确的用法。

