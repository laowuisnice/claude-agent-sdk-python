## `examples/tool_permission_callback.py`

这个示例演示 `ClaudeAgentOptions.can_use_tool`：用一个 Python 回调函数在运行时**决定是否允许某次工具调用**，以及（可选）**修改工具输入**，并把请求记录下来。

它适合用来做你自用智能体的：

- 安全策略（禁用危险 bash、限制写路径、重定向输出）
- 审计日志（记录每次工具调用的 input 与 CLI 的建议）
- 人工审批（对未知工具要求你在终端输入 y/N）

---

### 全局变量 `tool_usage_log`

**用途**

- 用于记录每次工具权限请求：工具名、输入、建议（`context.suggestions`）。

---

### `async def my_permission_callback(tool_name, input_data, context) -> PermissionResultAllow | PermissionResultDeny`

**用途**

- 这是 `can_use_tool` 回调的实现：SDK/CLI 每当要执行工具时会调用它，让你决定 allow/deny，并可返回修改后的输入。

**逻辑分支（按示例）**

- 记录日志：把 `{tool, input, suggestions}` 追加到 `tool_usage_log`。
- 打印请求信息（工具名 + JSON 格式输入）。
- **读类工具自动允许**：`Read/Glob/Grep` → `PermissionResultAllow()`
- **写类工具的安全策略**：`Write/Edit/MultiEdit`
  - 若 `file_path` 以 `/etc/` 或 `/usr/` 开头 → 直接 deny（系统目录）
  - 若 `file_path` 不在 `/tmp/` 或 `./` 下 → 重定向到 `./safe_output/<basename>`（通过 `updated_input` 返回）
- **bash 安全策略**：
  - 若命令包含 `rm -rf` / `sudo` / `chmod 777` / `dd if=` / `mkfs` 等片段 → deny
  - 否则 allow
- **其他未知工具**：
  - 在终端询问 `Allow this tool? (y/N)`
  - y/yes → allow，否则 deny

**重要限制（从 SDK 行为推导）**

- 当你使用 `can_use_tool` 时，`ClaudeSDKClient.connect()` 要求 prompt 为 streaming（见 [docs/api/client.md](../api/client.md) 里的限制）；示例这里用 `ClaudeSDKClient(options)` 是正确方向。

---

### `async def main()`

**用途**

- 配置 `ClaudeAgentOptions(can_use_tool=..., permission_mode="default", cwd=".")`
- 通过 `ClaudeSDKClient` 发起一个会触发多种工具的任务（列目录、写 hello.py、运行它）
- 在 `receive_response()` 中打印 assistant 文本和最终结果，并在最后输出工具使用汇总。

**关键点**

- `permission_mode="default"`：示例强调用默认模式以确保回调被调用（具体依赖 CLI 的权限协议实现）。

---

### `if __name__ == "__main__": asyncio.run(main())`

标准入口。

---

### 你在自用智能体里如何落地

- 把“危险命令模式”换成你自己的策略（例如禁网、禁 docker、禁修改某些目录）。
- 把“写路径重定向”改成你自己的沙盒目录（比如 `./agent_output/`）。
- 把日志写入文件或数据库，形成可追溯的审计记录。

