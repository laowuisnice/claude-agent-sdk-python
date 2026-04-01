## `claude_agent_sdk.types`

本模块几乎是整个 SDK 的“类型/配置中枢”，包含：

- **配置**：`ClaudeAgentOptions`（你最常改的就是它）
- **消息模型**：`UserMessage` / `AssistantMessage` / `SystemMessage` / `ResultMessage` / `StreamEvent` / `RateLimitEvent`
- **内容块**：`TextBlock` / `ThinkingBlock` / `ToolUseBlock` / `ToolResultBlock`
- **权限回调**：`CanUseTool`、`PermissionUpdate`、`PermissionResultAllow/Deny`
- **Hooks**：各种 HookInput/HookSpecificOutput、`HookMatcher`、`HookCallback`
- **MCP**：server config / status 返回结构
- **会话读取**：`SDKSessionInfo`、`SessionMessage`

你在“自用智能体”里最常直接用到的通常是：

- `ClaudeAgentOptions`
- `Message`（以及具体的 message dataclass）
- `ContentBlock`（以及具体 block dataclass）
- Hook / MCP / 权限这三块（当你开始做安全控制或自定义工具时）

> 说明：你要求“每个函数或类”。本文件里 **函数只有** `PermissionUpdate.to_dict()`；其余都是 `@dataclass` 或 `TypedDict` 类。下面逐个解释。

---

## Agent / 预设相关

### `class SystemPromptPreset(TypedDict)`

**用途**

- 用“预设”方式选择系统提示词模板（目前只看到 `preset: "claude_code"`），并可通过 `append` 追加文本。

**字段**

- `type`: `"preset"`
- `preset`: `"claude_code"`
- `append`（可选）：附加系统提示词文本

---

### `class ToolsPreset(TypedDict)`

**用途**

- 用“预设”方式选择工具集合模板（目前同样是 `preset: "claude_code"`）。

**字段**

- `type`: `"preset"`
- `preset`: `"claude_code"`

---

### `@dataclass class AgentDefinition`

**用途**

- 定义“自定义 agent”的配置对象，用于 `ClaudeAgentOptions.agents`。
- 你可以把它理解成“子智能体模板/画像”（描述、提示词、工具、模型偏好等）。

**字段**

- `description: str`：给人看的说明
- `prompt: str`：该 agent 的系统/任务提示词主体
- `tools: list[str] | None`：允许/使用的工具名列表（语义依赖 CLI 对 agents 的实现）
- `model: Literal["sonnet","opus","haiku","inherit"] | None`：模型选择（或继承）
- `skills: list[str] | None`：技能列表（语义依赖 CLI）
- `memory: Literal["user","project","local"] | None`：记忆层级
- `mcpServers: list[str | dict[str, Any]] | None`：MCP servers（可用 server 名或 inline 配置）

---

## 权限更新 / can_use_tool 回调相关

### `@dataclass class PermissionRuleValue`

**用途**

- 表示一条权限规则（面向某个 tool）。

**字段**

- `tool_name: str`
- `rule_content: str | None`：规则内容（例如路径/模式等，具体语义由 CLI 权限规则决定）

---

### `@dataclass class PermissionUpdate`

**用途**

- 表示一次“权限设置变更”的建议/指令（可加规则、替换规则、设置 mode、加目录等）。
- 通常出现在 `ToolPermissionContext.suggestions`，或者你返回 `PermissionResultAllow.updated_permissions`。

**字段**

- `type`: `"addRules" | "replaceRules" | "removeRules" | "setMode" | "addDirectories" | "removeDirectories"`
- `rules: list[PermissionRuleValue] | None`
- `behavior: "allow" | "deny" | "ask" | None`
- `mode: PermissionMode | None`
- `directories: list[str] | None`
- `destination: "userSettings" | "projectSettings" | "localSettings" | "session" | None`

#### `def to_dict(self) -> dict[str, Any]`

**用途**

- 把 `PermissionUpdate` 转成符合控制协议/CLI wire format 的 dict（例如 `toolName` 的 camelCase）。

**行为要点**

- 总会包含 `{"type": self.type}`；若 `destination` 非空也会带上。
- `addRules/replaceRules/removeRules`：会把 `rules` 转成 `{"toolName": ..., "ruleContent": ...}` 列表，并附 `behavior`。
- `setMode`：带 `mode`
- `addDirectories/removeDirectories`：带 `directories`

---

### `@dataclass class ToolPermissionContext`

**用途**

- 在 `can_use_tool` 回调被调用时提供上下文。

**字段**

- `signal: Any | None`：预留给未来的 abort signal
- `suggestions: list[PermissionUpdate]`：CLI 给出的权限建议（你可以采纳并返回）

---

### `@dataclass class PermissionResultAllow`

**用途**

- `can_use_tool` 回调的“允许执行”返回值结构。

**字段**

- `behavior: "allow"`（固定）
- `updated_input: dict[str, Any] | None`：你可以在允许前修改 tool input（例如清理危险参数）
- `updated_permissions: list[PermissionUpdate] | None`：你可以建议更新权限配置

---

### `@dataclass class PermissionResultDeny`

**用途**

- `can_use_tool` 回调的“拒绝执行”返回值结构。

**字段**

- `behavior: "deny"`（固定）
- `message: str`：拒绝原因
- `interrupt: bool`：是否中断当前流程

---

## Hooks 相关

### `class BaseHookInput(TypedDict)`

**用途**

- Hook input 的公共字段基类。

**字段**

- `session_id: str`
- `transcript_path: str`
- `cwd: str`
- `permission_mode`（可选）: `str`

---

### `class _SubagentContextMixin(TypedDict, total=False)`

**用途**

- 为“工具生命周期相关 hooks”提供可选的 sub-agent 归因信息（`agent_id`/`agent_type`）。

**字段（可选）**

- `agent_id: str`
- `agent_type: str`

---

### `class PreToolUseHookInput(BaseHookInput, _SubagentContextMixin)`

**用途**

- `PreToolUse` 事件输入：在工具执行前触发。

**字段**

- `hook_event_name: "PreToolUse"`
- `tool_name: str`
- `tool_input: dict[str, Any]`
- `tool_use_id: str`

---

### `class PostToolUseHookInput(BaseHookInput, _SubagentContextMixin)`

**用途**

- `PostToolUse` 事件输入：工具执行后触发（成功路径）。

**字段**

- `hook_event_name: "PostToolUse"`
- `tool_name: str`
- `tool_input: dict[str, Any]`
- `tool_response: Any`
- `tool_use_id: str`

---

### `class PostToolUseFailureHookInput(BaseHookInput, _SubagentContextMixin)`

**用途**

- `PostToolUseFailure`：工具执行失败后触发。

**字段**

- `hook_event_name: "PostToolUseFailure"`
- `tool_name: str`
- `tool_input: dict[str, Any]`
- `tool_use_id: str`
- `error: str`
- `is_interrupt`（可选）: `bool`

---

### `class UserPromptSubmitHookInput(BaseHookInput)`

**用途**

- `UserPromptSubmit`：用户提交 prompt 时触发（更偏“应用层事件”，不是模型）。

**字段**

- `hook_event_name: "UserPromptSubmit"`
- `prompt: str`

---

### `class StopHookInput(BaseHookInput)`

**用途**

- `Stop`：停止相关事件。

**字段**

- `hook_event_name: "Stop"`
- `stop_hook_active: bool`

---

### `class SubagentStopHookInput(BaseHookInput)`

**用途**

- `SubagentStop`：子智能体停止事件（含 transcript 位置）。

**字段**

- `hook_event_name: "SubagentStop"`
- `stop_hook_active: bool`
- `agent_id: str`
- `agent_transcript_path: str`
- `agent_type: str`

---

### `class PreCompactHookInput(BaseHookInput)`

**用途**

- `PreCompact`：会话压缩（compact）前触发。

**字段**

- `hook_event_name: "PreCompact"`
- `trigger: "manual" | "auto"`
- `custom_instructions: str | None`

---

### `class NotificationHookInput(BaseHookInput)`

**用途**

- `Notification`：通知类事件输入。

**字段**

- `hook_event_name: "Notification"`
- `message: str`
- `title`（可选）: `str`
- `notification_type: str`

---

### `class SubagentStartHookInput(BaseHookInput)`

**用途**

- `SubagentStart`：子智能体启动事件输入。

**字段**

- `hook_event_name: "SubagentStart"`
- `agent_id: str`
- `agent_type: str`

---

### `class PermissionRequestHookInput(BaseHookInput, _SubagentContextMixin)`

**用途**

- `PermissionRequest`：权限请求事件输入（当 CLI 需要权限决策时）。

**字段**

- `hook_event_name: "PermissionRequest"`
- `tool_name: str`
- `tool_input: dict[str, Any]`
- `permission_suggestions`（可选）: `list[Any]`

---

### `class PreToolUseHookSpecificOutput(TypedDict)`

**用途**

- Hook 回调返回值里的 `hookSpecificOutput` 之一：针对 PreToolUse 的细化控制（允许/拒绝/询问、更新 input、补充上下文等）。

**字段**

- `hookEventName: "PreToolUse"`
- `permissionDecision`（可选）: `"allow" | "deny" | "ask"`
- `permissionDecisionReason`（可选）: `str`
- `updatedInput`（可选）: `dict[str, Any]`
- `additionalContext`（可选）: `str`

---

### `class PostToolUseHookSpecificOutput(TypedDict)`

**用途**

- PostToolUse 的 hookSpecificOutput。

**字段**

- `hookEventName: "PostToolUse"`
- `additionalContext`（可选）
- `updatedMCPToolOutput`（可选）

---

### `class PostToolUseFailureHookSpecificOutput(TypedDict)`

**用途**

- PostToolUseFailure 的 hookSpecificOutput。

**字段**

- `hookEventName: "PostToolUseFailure"`
- `additionalContext`（可选）

---

### `class UserPromptSubmitHookSpecificOutput(TypedDict)`

**用途**

- UserPromptSubmit 的 hookSpecificOutput。

**字段**

- `hookEventName: "UserPromptSubmit"`
- `additionalContext`（可选）

---

### `class SessionStartHookSpecificOutput(TypedDict)`

**用途**

- SessionStart 的 hookSpecificOutput（注意：本模块里定义了类型，但 HookEvent union 里不包含 SessionStart；可能是兼容/预留）。

**字段**

- `hookEventName: "SessionStart"`
- `additionalContext`（可选）

---

### `class NotificationHookSpecificOutput(TypedDict)`

**用途**

- Notification 的 hookSpecificOutput。

**字段**

- `hookEventName: "Notification"`
- `additionalContext`（可选）

---

### `class SubagentStartHookSpecificOutput(TypedDict)`

**用途**

- SubagentStart 的 hookSpecificOutput。

**字段**

- `hookEventName: "SubagentStart"`
- `additionalContext`（可选）

---

### `class PermissionRequestHookSpecificOutput(TypedDict)`

**用途**

- PermissionRequest 的 hookSpecificOutput（包含一个 `decision` dict）。

**字段**

- `hookEventName: "PermissionRequest"`
- `decision: dict[str, Any]`

---

### `class AsyncHookJSONOutput(TypedDict)`

**用途**

- Hook 的“异步延迟执行”返回结构。

**字段**

- `async_: True`：注意这里用 `async_` 避免 Python 关键字；发送给 CLI 时会转成 `async`
- `asyncTimeout`（可选）: `int`（毫秒）

---

### `class SyncHookJSONOutput(TypedDict)`

**用途**

- Hook 的“同步”返回结构（最常用），用于控制是否继续、是否抑制输出、阻断原因、附加上下文、以及 hookSpecificOutput 等。

**关键字段**

- `continue_`（可选）: `bool`（会转成 `continue`）
- `suppressOutput`（可选）: `bool`
- `stopReason`（可选）: `str`
- `decision`（可选）: `"block"`（对多数 hooks 来说只有 block 有意义）
- `systemMessage`（可选）: `str`
- `reason`（可选）: `str`
- `hookSpecificOutput`（可选）: 各事件对应的 HookSpecificOutput

---

### `class HookContext(TypedDict)`

**用途**

- 传给 HookCallback 的上下文对象，目前只有 `signal` 预留字段。

**字段**

- `signal: Any | None`

---

### `@dataclass class HookMatcher`

**用途**

- 把某个 HookEvent 下的 hooks 按 matcher 分组（类似“匹配哪些工具名/事件再执行哪些 hooks”）。

**字段**

- `matcher: str | None`：例如 `"Bash"` 或 `"Write|MultiEdit|Edit"`（具体语法见官方 hooks 文档）
- `hooks: list[HookCallback]`：一组 Python 回调
- `timeout: float | None`：该 matcher 下所有 hooks 的总超时（秒）

---

## MCP 配置 / 状态

### `class McpStdioServerConfig(TypedDict)`

**用途**

- 配置一个通过 stdio 启动的外部 MCP server（子进程方式）。

**字段**

- `type`（可选）: `"stdio"`（为兼容可省略）
- `command: str`
- `args`（可选）: `list[str]`
- `env`（可选）: `dict[str, str]`

---

### `class McpSSEServerConfig(TypedDict)`

**用途**

- 配置 SSE 方式的 MCP server。

**字段**

- `type: "sse"`
- `url: str`
- `headers`（可选）

---

### `class McpHttpServerConfig(TypedDict)`

**用途**

- 配置 HTTP 方式的 MCP server。

**字段**

- `type: "http"`
- `url: str`
- `headers`（可选）

---

### `class McpSdkServerConfig(TypedDict)`

**用途**

- SDK 进程内 MCP server 的配置（由 `create_sdk_mcp_server()` 生成）。

**字段**

- `type: "sdk"`
- `name: str`
- `instance: McpServer`（运行时 server 实例）

---

### `class McpSdkServerConfigStatus(TypedDict)`

**用途**

- `get_mcp_status()` 返回中，对 SDK server 的“可序列化”配置形态（不包含 `instance`）。

**字段**

- `type: "sdk"`
- `name: str`

---

### `class McpClaudeAIProxyServerConfig(TypedDict)`

**用途**

- 状态返回中的 output-only 类型：表示通过 claude.ai 代理的 server 配置。

**字段**

- `type: "claudeai-proxy"`
- `url: str`
- `id: str`

---

### `class McpToolAnnotations(TypedDict, total=False)`

**用途**

- MCP tool 注解（wire format，camelCase），用于 status 返回。

**字段**

- `readOnly: bool`
- `destructive: bool`
- `openWorld: bool`

---

### `class McpToolInfo(TypedDict)`

**用途**

- 描述某个 MCP server 提供的一个 tool（用于 status 返回）。

**字段**

- `name: str`
- `description`（可选）
- `annotations`（可选）

---

### `class McpServerInfo(TypedDict)`

**用途**

- MCP handshake 的 server 信息（连接成功后可见）。

**字段**

- `name: str`
- `version: str`

---

### `class McpServerStatus(TypedDict)`

**用途**

- `get_mcp_status()` 返回里每个 server 的状态条目。

**字段**

- `name: str`
- `status: "connected" | "failed" | "needs-auth" | "pending" | "disabled"`
- `serverInfo`（可选）
- `error`（可选）
- `config`（可选）：可能是 stdio/sse/http/sdk/claudeai-proxy 的某种形态
- `scope`（可选）：project/user/local/claudeai/managed 等
- `tools`（可选）：`list[McpToolInfo]`

---

### `class McpStatusResponse(TypedDict)`

**用途**

- `ClaudeSDKClient.get_mcp_status()` 的返回外层结构。

**字段**

- `mcpServers: list[McpServerStatus]`

---

## 插件 / 沙盒

### `class SdkPluginConfig(TypedDict)`

**用途**

- SDK 插件配置（目前仅看到 `type: "local"`）。

**字段**

- `type: "local"`
- `path: str`

---

### `class SandboxNetworkConfig(TypedDict, total=False)`

**用途**

- bash sandbox 的网络相关配置。

**字段**

- `allowUnixSockets: list[str]`
- `allowAllUnixSockets: bool`
- `allowLocalBinding: bool`
- `httpProxyPort: int`
- `socksProxyPort: int`

---

### `class SandboxIgnoreViolations(TypedDict, total=False)`

**用途**

- 指定要忽略的 sandbox 违规项（文件/网络）。

**字段**

- `file: list[str]`
- `network: list[str]`

---

### `class SandboxSettings(TypedDict, total=False)`

**用途**

- bash sandbox 的总体设置（是否启用、是否自动放行、排除命令、网络配置等）。

**关键说明（来自 docstring）**

- 文件系统/网络访问的“允许/禁止”主要靠权限规则（Read/Edit/WebFetch），不靠这里。

**字段**

- `enabled: bool`
- `autoAllowBashIfSandboxed: bool`
- `excludedCommands: list[str]`
- `allowUnsandboxedCommands: bool`
- `network: SandboxNetworkConfig`
- `ignoreViolations: SandboxIgnoreViolations`
- `enableWeakerNestedSandbox: bool`

---

## 内容块（content blocks）

### `@dataclass class TextBlock`

**用途**

- Assistant 输出的文本块。

**字段**

- `text: str`

---

### `@dataclass class ThinkingBlock`

**用途**

- Assistant 输出的“思考”块（extended thinking）。

**字段**

- `thinking: str`
- `signature: str`

---

### `@dataclass class ToolUseBlock`

**用途**

- Assistant 发起一次工具调用的块。

**字段**

- `id: str`：tool use id
- `name: str`：工具名
- `input: dict[str, Any]`：工具入参

---

### `@dataclass class ToolResultBlock`

**用途**

- 工具调用结果块（通常在工具执行后返回给 assistant）。

**字段**

- `tool_use_id: str`
- `content: str | list[dict[str, Any]] | None`
- `is_error: bool | None`

---

## 消息（messages）

### `@dataclass class UserMessage`

**用途**

- 表示用户消息（在流里可能被 replay/回放，或用于 file checkpointing）。

**字段**

- `content: str | list[ContentBlock]`
- `uuid: str | None`：配合 `extra_args={"replay-user-messages": None}` 才能稳定拿到
- `parent_tool_use_id: str | None`
- `tool_use_result: dict[str, Any] | None`

---

### `@dataclass class AssistantMessage`

**用途**

- assistant 的消息（核心输出）。内容是 `list[ContentBlock]`，你通常会遍历其中的 `TextBlock`。

**字段**

- `content: list[ContentBlock]`
- `model: str`
- `parent_tool_use_id: str | None`
- `error: AssistantMessageError | None`
- `usage: dict[str, Any] | None`

---

### `@dataclass class SystemMessage`

**用途**

- CLI/系统侧的消息（任务通知、系统事件等），原始 payload 放在 `data`。

**字段**

- `subtype: str`
- `data: dict[str, Any]`

---

### `class TaskUsage(TypedDict)`

**用途**

- 任务进行中/结束时附带的用量统计。

**字段**

- `total_tokens: int`
- `tool_uses: int`
- `duration_ms: int`

---

### `@dataclass class TaskStartedMessage(SystemMessage)`

**用途**

- task 启动时的系统消息（仍然是 `SystemMessage` 的子类，便于 pattern matching）。

**字段**

- `task_id: str`
- `description: str`
- `uuid: str`
- `session_id: str`
- `tool_use_id: str | None`
- `task_type: str | None`

---

### `@dataclass class TaskProgressMessage(SystemMessage)`

**用途**

- task 进行中定期发送的系统消息。

**字段**

- `task_id: str`
- `description: str`
- `usage: TaskUsage`
- `uuid: str`
- `session_id: str`
- `tool_use_id: str | None`
- `last_tool_name: str | None`

---

### `@dataclass class TaskNotificationMessage(SystemMessage)`

**用途**

- task 完成/失败/停止时的系统消息。

**字段**

- `task_id: str`
- `status: "completed" | "failed" | "stopped"`
- `output_file: str`
- `summary: str`
- `uuid: str`
- `session_id: str`
- `tool_use_id: str | None`
- `usage: TaskUsage | None`

---

### `@dataclass class ResultMessage`

**用途**

- 一轮对话/一次响应的“结束标志”消息，包含成本/时长/usage/stop_reason 等。
- `ClaudeSDKClient.receive_response()` 会在拿到它后自动停止迭代。

**字段**

- `subtype: str`
- `duration_ms: int`
- `duration_api_ms: int`
- `is_error: bool`
- `num_turns: int`
- `session_id: str`
- `stop_reason: str | None`
- `total_cost_usd: float | None`
- `usage: dict[str, Any] | None`
- `result: str | None`
- `structured_output: Any`

---

### `@dataclass class StreamEvent`

**用途**

- partial message streaming（部分消息增量）时的事件承载。

**字段**

- `uuid: str`
- `session_id: str`
- `event: dict[str, Any]`：原始 API stream event
- `parent_tool_use_id: str | None`

---

### `@dataclass class RateLimitInfo`

**用途**

- 速率限制状态信息（CLI 状态变化时发出）。

**字段（常用）**

- `status: "allowed" | "allowed_warning" | "rejected"`
- `resets_at: int | None`
- `rate_limit_type: ... | None`
- `utilization: float | None`
- `overage_status: ... | None`
- `raw: dict[str, Any]`：未建模字段的原始信息

---

### `@dataclass class RateLimitEvent`

**用途**

- 当 rate limit 状态变化时发出的事件。

**字段**

- `rate_limit_info: RateLimitInfo`
- `uuid: str`
- `session_id: str`

---

## Session 列表/读取

### `@dataclass class SDKSessionInfo`

**用途**

- `list_sessions()` 返回的会话元信息（无需解析整份 transcript）。

**字段（常用）**

- `session_id: str`
- `summary: str`
- `last_modified: int`
- `file_size: int | None`
- `custom_title: str | None`
- `first_prompt: str | None`
- `git_branch: str | None`
- `cwd: str | None`
- `tag: str | None`
- `created_at: int | None`

---

### `@dataclass class SessionMessage`

**用途**

- `get_session_messages()` 返回的“历史用户/assistant 消息”条目。

**字段**

- `type: "user" | "assistant"`
- `uuid: str`
- `session_id: str`
- `message: Any`：原始 message dict（role/content 等）
- `parent_tool_use_id: None`：顶层消息固定为 None（工具 sidechain 已过滤）

---

## Thinking 配置

### `class ThinkingConfigAdaptive(TypedDict)`

**用途**

- `thinking={"type": "adaptive"}`：让系统自适应 extended thinking 行为。

---

### `class ThinkingConfigEnabled(TypedDict)`

**用途**

- `thinking={"type": "enabled", "budget_tokens": ...}`：显式开启并给预算。

---

### `class ThinkingConfigDisabled(TypedDict)`

**用途**

- `thinking={"type": "disabled"}`：显式关闭。

---

## `@dataclass class ClaudeAgentOptions`

**用途**

- 控制一次 query 或一个 client 会话的全部行为：系统提示词、工具集、权限、MCP、模型、预算、沙盒、插件、hooks、stderr 回调等。

**字段（按“最常用 → 高级”分组）**

- **工具与权限**
  - `tools: list[str] | ToolsPreset | None`：工具集（或预设）
  - `allowed_tools: list[str]`：自动批准的工具白名单（注意：它不等价于“只允许这些工具存在”）
  - `disallowed_tools: list[str]`：显式禁止的工具
  - `permission_mode: PermissionMode | None`：默认/自动接受 edits/计划/绕过权限等
  - `can_use_tool: CanUseTool | None`：权限回调（与 `ClaudeSDKClient.connect()` 的限制强相关）
  - `permission_prompt_tool_name: str | None`：权限提示工具名（与 `can_use_tool` 互斥）

- **提示词与工作目录**
  - `system_prompt: str | SystemPromptPreset | None`
  - `cwd: str | Path | None`

- **MCP / 插件 / hooks**
  - `mcp_servers: dict[str, McpServerConfig] | str | Path`
  - `hooks: dict[HookEvent, list[HookMatcher]] | None`
  - `plugins: list[SdkPluginConfig]`

- **会话与预算**
  - `continue_conversation: bool`
  - `resume: str | None`
  - `fork_session: bool`
  - `max_turns: int | None`
  - `max_budget_usd: float | None`

- **模型**
  - `model: str | None`
  - `fallback_model: str | None`
  - `betas: list[SdkBeta]`

- **CLI/环境**
  - `cli_path: str | Path | None`
  - `settings: str | None`
  - `add_dirs: list[str | Path]`
  - `env: dict[str, str]`
  - `extra_args: dict[str, str | None]`：透传任意 CLI flags
  - `max_buffer_size: int | None`

- **stderr/调试**
  - `debug_stderr: Any`：已标注 deprecated
  - `stderr: Callable[[str], None] | None`：stderr 回调（推荐用它收集 CLI stderr）

- **流式/结构化输出**
  - `include_partial_messages: bool`
  - `output_format: dict[str, Any] | None`：结构化输出配置（messages API 形状）

- **agent 定义 / setting sources**
  - `agents: dict[str, AgentDefinition] | None`
  - `setting_sources: list[SettingSource] | None`

- **sandbox**
  - `sandbox: SandboxSettings | None`

- **file checkpointing**
  - `enable_file_checkpointing: bool`

---

## SDK 控制协议（TypedDict）

这些类型用于 SDK 和 CLI 的“控制通道”消息结构。你通常**不会直接构造它们**，但理解它们有助于你读懂高级能力（interrupt、权限回调、rewind、MCP 控制等）底层在干什么。

### `class SDKControlInterruptRequest(TypedDict)`
- `subtype: "interrupt"`

### `class SDKControlPermissionRequest(TypedDict)`
- `subtype: "can_use_tool"`
- `tool_name: str`
- `input: dict[str, Any]`
- `permission_suggestions: list[Any] | None`
- `blocked_path: str | None`

### `class SDKControlInitializeRequest(TypedDict)`
- `subtype: "initialize"`
- `hooks: dict[HookEvent, Any] | None`
- `agents`（可选）: `dict[str, dict[str, Any]]`

### `class SDKControlSetPermissionModeRequest(TypedDict)`
- `subtype: "set_permission_mode"`
- `mode: str`

### `class SDKHookCallbackRequest(TypedDict)`
- `subtype: "hook_callback"`
- `callback_id: str`
- `input: Any`
- `tool_use_id: str | None`

### `class SDKControlMcpMessageRequest(TypedDict)`
- `subtype: "mcp_message"`
- `server_name: str`
- `message: Any`

### `class SDKControlRewindFilesRequest(TypedDict)`
- `subtype: "rewind_files"`
- `user_message_id: str`

### `class SDKControlMcpReconnectRequest(TypedDict)`
- `subtype: "mcp_reconnect"`
- `serverName: str`（wire format camelCase）

### `class SDKControlMcpToggleRequest(TypedDict)`
- `subtype: "mcp_toggle"`
- `serverName: str`
- `enabled: bool`

### `class SDKControlStopTaskRequest(TypedDict)`
- `subtype: "stop_task"`
- `task_id: str`

### `class SDKControlRequest(TypedDict)`
- `type: "control_request"`
- `request_id: str`
- `request: (...)`（上述各种 request union）

### `class ControlResponse(TypedDict)`
- `subtype: "success"`
- `request_id: str`
- `response: dict[str, Any] | None`

### `class ControlErrorResponse(TypedDict)`
- `subtype: "error"`
- `request_id: str`
- `error: str`

### `class SDKControlResponse(TypedDict)`
- `type: "control_response"`
- `response: ControlResponse | ControlErrorResponse`

