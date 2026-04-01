## `examples/agents.py`

这个示例演示如何通过 `ClaudeAgentOptions.agents` 定义多种“自定义 agent”（带不同的描述、提示词、工具和模型），然后用 `query()` 调用这些 agent 来完成特定任务。

---

### 顶部导入

- `anyio`：运行异步 main。
- 从 `claude_agent_sdk` 导入：
  - `AgentDefinition`：描述单个 agent 的配置
  - `AssistantMessage`：回答消息类型
  - `ClaudeAgentOptions`：配置结构
  - `ResultMessage`：结束消息
  - `TextBlock`：文本内容块
  - `query`：一次性调用入口

---

### `async def code_reviewer_example()`

**用途**

- 定义一个 `code-reviewer` agent，并用它来对特定文件做代码审查。

**步骤**

1. 打印标题 `"=== Code Reviewer Agent Example ==="`
2. 构造 `options = ClaudeAgentOptions(agents={...})`：
   - `agents` 字典里只有一个 entry：
     - 键 `"code-reviewer"`
     - 值为 `AgentDefinition(...)`：
       - `description`: 自然语言描述
       - `prompt`: 详细的系统/任务提示词（强调 bug、性能、安全、最佳实践）
       - `tools`: `["Read", "Grep"]`（适合作代码审查）
       - `model`: `"sonnet"`
3. 调用：
   - `async for message in query(prompt="Use the code-reviewer agent to review the code in src/claude_agent_sdk/types.py", options=options):`
4. 处理返回：
   - `AssistantMessage` + `TextBlock` → 打印 `Claude: ...`
   - `ResultMessage` 且有 `total_cost_usd` 时打印花费

**你可以怎么改成自己的代码审查工具**

- 把 prompt 中的“review the code in src/claude_agent_sdk/types.py”换成“review 当前项目的 X 子目录”等；
- 根据需要增加/减少 `tools`（比如加上 `Glob`、`Write` 用于自动修复）。

---

### `async def documentation_writer_example()`

**用途**

- 定义一个 `doc-writer` agent，专门写文档。

**步骤**

1. 打印标题 `"=== Documentation Writer Agent Example ==="`
2. 构造 `options = ClaudeAgentOptions(agents={"doc-writer": AgentDefinition(...)})`：
   - `description`: 说明写文档
   - `prompt`: 强调“技术文档、清晰、全面、有示例”
   - `tools`: `["Read", "Write", "Edit"]`（读代码、写文档、编辑文件）
   - `model`: `"sonnet"`
3. `query()`：
   - prompt 为 “Use the doc-writer agent to explain what AgentDefinition is used for”
4. 处理返回：
   - 与上一个 example 相同。

**如何用在你自己的项目**

- 把 prompt 改成“为我们项目中的 XXX 模块写一份 README”，让 agent 自动读取代码并写文档；
- 把 `cwd` 设置为你的项目根目录，让工具在正确的位置读写。

---

### `async def multiple_agents_example()`

**用途**

- 同时定义两个 agent（`analyzer`、`tester`），展示多 agent 配置与 `setting_sources`。

**步骤**

1. 打印 `"=== Multiple Agents Example ==="`
2. 构造 `options = ClaudeAgentOptions(agents={...}, setting_sources=["user", "project"])`：
   - `"analyzer"` agent：
     - `description`: 分析代码结构和模式
     - `prompt`: 强调结构/架构分析
     - `tools`: `["Read", "Grep", "Glob"]`
     - `model` 未指定（使用默认/继承）
   - `"tester"` agent：
     - `description`: 创建和运行测试
     - `prompt`: 强调写测试和保证质量
     - `tools`: `["Read", "Write", "Bash"]`
     - `model`: `"sonnet"`
   - `setting_sources=["user", "project"]`：指定从哪些设置源加载配置（与 Claude Code 的设置系统对应）。
3. `query()`：
   - prompt 为 “Use the analyzer agent to find all Python files in the examples/ directory”
4. 处理返回：
   - 同前两个例子。

**你可以怎么扩展**

- 为你的项目创建多个角色：
  - `"bug-fixer"`：专门修 bug，用 `Write`/`Edit`/`Bash`
  - `"refactorer"`：专门重构，用 `Read`/`Edit`
  - `"infra"`：专门看 CI/CD/脚本
- 在 prompt 里明确要求“使用某个 agent 来完成任务”，由 CLI/SDK 调度对应 agent。

---

### `async def main()`

**用途**

- 依次运行三个 agent 示例。

**逻辑**

- `await code_reviewer_example()`
- `await documentation_writer_example()`
- `await multiple_agents_example()`

---

### `if __name__ == "__main__": anyio.run(main)`

**用途**

- 运行示例脚本。

**迁移到你的项目**

- 把每个 `*_example` 改造成你实际要跑的场景（甚至只保留一两个），然后仍然用 `anyio.run(main)`；
- 也可以把某个 example 函数单独复制到你的业务代码中作为“特定 agent 工作流”。  

