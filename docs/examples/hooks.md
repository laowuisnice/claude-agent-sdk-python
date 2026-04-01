## `examples/hooks.py`

这个示例演示如何通过 `ClaudeAgentOptions.hooks` + `HookMatcher` 在不同事件点注入 Hook 回调，以实现：

- 工具调用前的拦截/审批（PreToolUse）
- 工具调用后的复核/反馈（PostToolUse）
- 用户提交 prompt 时追加上下文（UserPromptSubmit）
- 用 `continue_=False` 停止后续执行（控制流程）

脚本支持命令行参数：列出可用示例/运行全部/运行单个。

---

### `def display_message(msg: Message) -> None`

**用途**

- 统一打印 `AssistantMessage/TextBlock`，并在 `ResultMessage` 时打印 `"Result ended"`。

---

## Hook 回调函数（核心）

### `async def check_bash_command(input_data, tool_use_id, context) -> HookJSONOutput`

**用途**

- 在 `PreToolUse` 阶段阻止某些 Bash 命令（示例阻止包含 `"foo.sh"` 的命令）。

**返回**

- 命中阻止规则时返回 `hookSpecificOutput`：
  - `hookEventName="PreToolUse"`
  - `permissionDecision="deny"`
  - `permissionDecisionReason=...`
- 不相关工具或未命中时返回 `{}`（不干预）。

---

### `async def add_custom_instructions(...) -> HookJSONOutput`

**用途**

- 演示向会话注入额外上下文（示例返回 `hookEventName="SessionStart"` + `additionalContext`）。

> 注意：本仓库的 `HookEvent` union 里没有 `SessionStart`，但类型里定义了 `SessionStartHookSpecificOutput`，这更像是“兼容/预留”示例；实际行为取决于 CLI 是否接受该事件名。

---

### `async def review_tool_output(...) -> HookJSONOutput`

**用途**

- 在 `PostToolUse` 阶段复核工具输出，如果发现包含 error 文本则：
  - 返回 `systemMessage`（提示用户）
  - 返回 `reason`（给 Claude 的反馈）
  - 返回 `hookSpecificOutput.additionalContext`（给 Claude 的附加上下文）

---

### `async def strict_approval_hook(...) -> HookJSONOutput`

**用途**

- 演示用 `permissionDecision="allow"/"deny"` 做精细审批。
- 示例策略：如果 `tool_name == "Write"` 且路径包含 `"important"`，则 deny；否则明确 allow。

---

### `async def stop_on_error_hook(...) -> HookJSONOutput`

**用途**

- 演示用 `continue_=False` 停止执行。
- 示例策略：如果 `tool_response` 包含 `"critical"`，则停止并给出 `stopReason/systemMessage`。

---

## 每个可运行示例

### `async def example_pretooluse()`

**展示点**

- `hooks={"PreToolUse":[HookMatcher(matcher="Bash", hooks=[check_bash_command])]}`  
- 发两条 bash 指令：一条应被 hook 阻止、一条应放行。

---

### `async def example_userpromptsubmit()`

**展示点**

- `hooks={"UserPromptSubmit":[HookMatcher(matcher=None, hooks=[add_custom_instructions])]}`  
- 发送 “What's my favorite color?” 并观察 hook 注入的上下文是否影响回答。

---

### `async def example_posttooluse()`

**展示点**

- `hooks={"PostToolUse":[HookMatcher(matcher="Bash", hooks=[review_tool_output])]}`  
- 运行一个会报错的命令（`ls /nonexistent_directory`），观察 hook 的反馈字段。

---

### `async def example_decision_fields()`

**展示点**

- `PreToolUse` hook 对 `Write` 做 allow/deny 决策字段演示。
- 示例还显式设置了 `model="claude-sonnet-4-5-20250929"`。

---

### `async def example_continue_control()`

**展示点**

- `PostToolUse` hook 根据输出内容决定是否 `continue_`。

---

### `async def main()`

**用途**

- 根据 `sys.argv` 选择运行哪个示例，或列出帮助信息。

---

### 你怎么把 hooks 用在自用智能体里

- **安全**：对 `Bash`、`Write/Edit` 做 deny/allow 白名单策略。
- **可控性**：对高风险输出 `continue_=False` 直接刹车，避免连锁操作。
- **可观测性**：在 `PostToolUse` 里把错误输出转成结构化告警/日志，并把“下一步建议”写进 `additionalContext` 提示模型自救。

