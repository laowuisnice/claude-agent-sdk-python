## `examples/setting_sources.py`

这个示例演示 `ClaudeAgentOptions.setting_sources`：控制 Claude Code 会从哪些来源加载配置（slash commands、agents、hooks 等）。

示例强调了一个关键规则：

- 当 `setting_sources` 为 `None`（未提供）时，**默认不加载任何 settings**，从而形成“隔离环境”。

---

### `def extract_slash_commands(msg: SystemMessage) -> list[str]`

**用途**

- 从 init 系统消息里提取 slash command 名称列表（`msg.data["slash_commands"]`）。

---

### `async def example_default()`

**用途**

- 演示默认隔离：不设置 `setting_sources`。

**逻辑**

- `options = ClaudeAgentOptions(cwd=sdk_dir)`（无 setting_sources）
- 发一个简单 query
- 在 init 消息里读取 commands 并检查是否包含 `"commit"`：
  - 期望：**不包含**（因为项目级 `.claude/commands/commit.md` 不应被加载）

---

### `async def example_user_only()`

**用途**

- 只加载 user 级设置，仍然不加载 project 级设置。

**关键点**

- `setting_sources=["user"]`
- 期望：`"commit"` 仍然不出现。

---

### `async def example_project_and_user()`

**用途**

- 同时加载 user + project 设置。

**关键点**

- `setting_sources=["user", "project"]`
- 期望：`"commit"` 出现。

---

### `async def main()` / `asyncio.run(main())`

该脚本支持命令行参数：

- 不带参数：列出可用 example 名称
- `all`：依次运行全部
- 指定某个 key：运行对应 example

---

### 你怎么用在自己的智能体里

- 如果你想让“自用智能体”不受本机全局配置影响（可复现/可移植），可以保持 `setting_sources=None`。
- 如果你想利用项目中的 `.claude/` 配置（自定义 slash commands/agents），就显式设置 `setting_sources=["project"]` 或 `["user","project"]`。

