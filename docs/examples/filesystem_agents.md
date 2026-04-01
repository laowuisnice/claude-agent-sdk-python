## `examples/filesystem_agents.py`

这个示例演示如何通过 `ClaudeAgentOptions.setting_sources=["project"]` 加载**磁盘上的 agent 定义文件**（例如 `.claude/agents/*.md`），而不是在代码里内联 `AgentDefinition`。

它还用于验证一个特定问题场景：在某些环境中，项目级（project）settings 的 filesystem agents 可能会“静默加载失败”。

---

### `def extract_agents(msg: SystemMessage) -> list[str]`

**用途**

- 从 init 的 `SystemMessage` 里提取当前加载到的 agent 名称列表。

**逻辑**

- 仅在 `msg.subtype == "init"` 时读取 `msg.data["agents"]`：
  - agents 可能是字符串列表，或包含 `{"name": ...}` 的 dict 列表
  - 统一提取成 `list[str]` 返回
- 非 init 消息返回空列表。

---

### `async def main()`

**用途**

- 以 SDK 仓库根目录作为 `cwd`，开启 `setting_sources=["project"]`，然后发一个简单 query，检查 init 消息中是否出现 `test-agent`。

**关键段落**

- `sdk_dir = Path(__file__).parent.parent`：定位到仓库根目录（该目录预期包含 `.claude/agents/test-agent.md`）。
- `options = ClaudeAgentOptions(setting_sources=["project"], cwd=sdk_dir)`：
  - 显式加载 project 设置源
  - 在该 `cwd` 下让 CLI 找到 `.claude/agents/`
- 用 `ClaudeSDKClient` 发送一次 query，并在 `receive_response()` 中：
  - 记录消息类型顺序
  - 在 init 系统消息时提取 agents 并打印
  - 在 assistant 消息时打印文本
  - 在 result 消息时打印 subtype/cost
- 结束后做一系列布尔检查并输出 SUCCESS/WARNING：
  - 是否收到了 init/assistant/result
  - 是否加载到了 `test-agent`

---

### `if __name__ == "__main__": asyncio.run(main())`

标准入口。

---

### 你怎么用在自己的项目里

- 把 `cwd` 指向你的项目根目录，并在该目录下放置 `.claude/agents/*.md`。
- 用 `setting_sources=["project"]`（或与 `["user","project"]` 组合）来加载这些 agent 文件。
- 用 init 系统消息里的 `agents` 字段做一次“自检”，避免你以为 agent 生效了但实际上没加载到。

