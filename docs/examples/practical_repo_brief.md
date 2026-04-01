## `examples/practical_repo_brief.py`

这个示例是一个“实用仓库速览脚本”：给 Claude 一个严格约束的提示词，让它只用少量必要文件快速概括当前仓库，并用中文输出给新开发者的上手建议。

它很适合改造成你自己的：

- “项目自助说明/Repo Brief” 命令
- “新成员一键上手” 助手
- 轻量级 codebase 总览工具

---

### 顶部导入

- `anyio`：运行 async main
- `sys`：配置 stdout 编码
- 从 `claude_agent_sdk` 导入：
  - `AssistantMessage` / `ResultMessage`：解析消息流
  - `ClaudeAgentOptions`：控制 cwd/工具/轮数
  - `TextBlock`：抽文本
  - `query`：一次性调用入口

---

### 常量 `PROMPT`

**用途**

- 提示词里明确了输出结构与约束：
  - 用中文输出
  - 3–5 个要点概括项目
  - 给一个可运行的第一步
  - 给一个今天就能做的小任务
- 并且强制“先只读少量必要文件”，且“只用 Read/Glob 工具”。

**关键价值**

- 这类 PROMPT 是“可重复执行”的：每次对一个新仓库跑一下，就能得到一致格式的速览报告。

---

### `async def main() -> None`

**用途**

- 配好 options，调用 `query(prompt=PROMPT, options=options)`，把 assistant 文本打印到控制台。

**关键段落**

- `sys.stdout.reconfigure(encoding="utf-8")`：确保 Windows/终端中文输出正常。
- `options = ClaudeAgentOptions(...)`：
  - `cwd="."`：以当前目录作为工作目录
  - `allowed_tools=["Read", "Glob"]`：自动批准 Read/Glob（并不等价于“禁止其他工具”，但配合提示词可约束）
  - `max_turns=12`：允许多轮以完成“读少量文件 → 总结”
- 遍历消息流：
  - `AssistantMessage/TextBlock`：打印文本
  - `ResultMessage`：打印 `[result] subtype=..., duration_ms=..., cost_usd=...`
- 若未收到任何文本：提示检查登录（`claude login`）。

---

### `if __name__ == "__main__": anyio.run(main)`

标准入口。

---

### 你怎么改造成自己的“自用智能体”

- 把 `PROMPT` 改成你想要的固定格式（例如“输出依赖图、入口点、测试命令、风险点”）。
- 把 `allowed_tools` 限制到你允许的范围（例如只读模式：`["Read", "Glob", "Grep"]`）。
- 把 `cwd` 指向你想分析的仓库路径（绝对路径或相对路径）。

