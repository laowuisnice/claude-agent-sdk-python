# Examples 文档索引（`docs/examples/`）

这里把 `examples/` 下的所有示例按“你要做的能力”分组，方便你按需阅读与复用。每个条目都对应一份同名说明文档（逐函数/关键段落讲解）。

---

## 入门：先跑通一次最小调用

- **`quick_start`**：`docs/examples/quick_start.md`
  - 适合：第一次跑 SDK；理解 `query()`、`ClaudeAgentOptions`、`allowed_tools`、`ResultMessage`。

---

## 交互式/多轮：`ClaudeSDKClient` streaming 模式

- **`streaming_mode`**：`docs/examples/streaming_mode.md`
  - 适合：做终端助手/聊天 UI/多轮会话；包含并发收发、interrupt、错误处理、控制协议等“大全”。
- **`streaming_mode_ipython`**：`docs/examples/streaming_mode_ipython.md`
  - 适合：IPython/Jupyter 里快速试用（复制粘贴片段）。
- **`streaming_mode_trio`**：`docs/examples/streaming_mode_trio.md`
  - 适合：你的应用栈是 trio 时参考（其余逻辑同 streaming）。
- **`include_partial_messages`**：`docs/examples/include_partial_messages.md`
  - 适合：做实时 UI（打字机效果、增量展示），会看到 `StreamEvent`。

---

## 自定义工具：MCP（进程内/外部）与工具集合控制

- **`mcp_calculator`**：`docs/examples/mcp_calculator.md`
  - 适合：把你的 Python 函数做成 Claude 可调用工具（进程内 MCP server）；最接近“自用智能体 + 自定义能力”的落地模板。
- **`tools_option`**：`docs/examples/tools_option.md`
  - 适合：严格控制“可用工具集合”（`tools`），并从 init `SystemMessage` 验证配置生效。

> 常见混淆提醒：  
>
> - `tools` 更像“定义可用工具集合”  
> - `allowed_tools` 更像“自动批准哪些工具调用（减少权限提示）”

---

## 自定义角色/子智能体：Agents

- **`agents`**：`docs/examples/agents.md`
  - 适合：用 `ClaudeAgentOptions.agents` + `AgentDefinition` 在代码里内联定义多个角色。
- **`filesystem_agents`**：`docs/examples/filesystem_agents.md`
  - 适合：把 agents 放在磁盘（`.claude/agents/*.md`）并通过 `setting_sources` 加载；并包含“加载是否成功”的自检思路。

---

## 安全与治理：权限回调、Hooks、可中断执行

- **`tool_permission_callback`**：`docs/examples/tool_permission_callback.md`
  - 适合：用 `can_use_tool` 做 allow/deny、重写 input（路径重定向）、危险命令阻断、人工审批与审计日志。
- **`hooks`**：`docs/examples/hooks.md`
  - 适合：在 PreToolUse/PostToolUse/UserPromptSubmit 等事件点注入确定性策略（更像“拦截器/中间件”）。
- **`streaming_mode`**（interrupt 相关部分）：`docs/examples/streaming_mode.md`
  - 适合：实现“打断当前任务/输出”的体验；注意 interrupt 需要持续消费消息流。

---

## 设置与扩展：setting_sources、plugins

- **`setting_sources`**：`docs/examples/setting_sources.md`
  - 适合：理解“默认隔离环境”（不加载任何设置）与显式加载 user/project/local 配置的差异；通过 init `SystemMessage` 验证 slash commands 是否加载。
- **`plugin_example`**：`docs/examples/plugin_example.md`
  - 适合：加载本地插件目录，并用 init 系统消息做自检。

---

## 成本与可观测性：预算、stderr 调试、仓库速览

- **`max_budget_usd`**：`docs/examples/max_budget_usd.md`
  - 适合：给自用智能体加成本上限，避免跑飞。
- **`stderr_callback_example`**：`docs/examples/stderr_callback_example.md`
  - 适合：捕获 CLI stderr（debug/错误），接入你自己的日志体系。
- **`practical_repo_brief`**：`docs/examples/practical_repo_brief.md`
  - 适合：把 Claude 当成“仓库速览生成器”；提示词里包含工具/文件读取约束，迁移到新仓库也能复用。

---

## 推荐阅读路径（按“做自用智能体”）

1. `quick_start`（跑通一次调用）
2. `streaming_mode`（确定你是否需要长连接/多轮/中断）
3. `mcp_calculator`（把你的业务能力做成工具）
4. `tool_permission_callback` 或 `hooks`（加安全边界与审计）
5. `setting_sources` / `filesystem_agents`（如果你想用 `.claude/` 生态配置）
6. `include_partial_messages`（如果你要做 UI）
7. `max_budget_usd` + `stderr_callback_example`（上线前补齐成本与诊断）
