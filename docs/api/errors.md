## `claude_agent_sdk._errors`

这个模块定义 SDK 的异常层次。你在业务里通常会 `except ClaudeSDKError` 做兜底，并对一些常见故障做更细粒度处理。

---

## `class ClaudeSDKError(Exception)`

**用途**

- SDK 自己抛出的异常基类。建议你捕获它作为“SDK 相关错误”的统一入口。

---

## `class CLIConnectionError(ClaudeSDKError)`

**用途**

- 与 Claude Code CLI 的连接/通信阶段出问题时抛出。
- 例如：还没 `connect()` 就调用需要连接的 API；或底层 transport 断开。

---

## `class CLINotFoundError(CLIConnectionError)`

**用途**

- 找不到 Claude Code CLI（未安装、路径错误、不可执行）时抛出。

**`__init__(message="Claude Code not found", cli_path=None)`**

- 如果提供 `cli_path`，异常消息会拼上路径，便于定位到底用的是哪个 CLI。

---

## `class ProcessError(ClaudeSDKError)`

**用途**

- CLI 子进程运行失败时抛出（例如退出码非 0）。

**属性**

- **`exit_code: int | None`**：退出码。
- **`stderr: str | None`**：stderr 文本（如果 SDK 捕获到了）。

**`__init__(message, exit_code=None, stderr=None)`**

- 会把 `exit_code` 和 `stderr` 追加到异常 message 中，方便直接打印排障。

---

## `class CLIJSONDecodeError(ClaudeSDKError)`

**用途**

- SDK 在读 CLI 输出时，某一行 JSON 解析失败。

**属性**

- **`line: str`**：解析失败的原始行（异常 message 里只截取前 100 字符）。
- **`original_error: Exception`**：底层 JSON 解析异常。

---

## `class MessageParseError(ClaudeSDKError)`

**用途**

- JSON 虽然能解析，但不符合 SDK 期望的消息结构（解析/归一化失败）。

**属性**

- **`data: dict[str, Any] | None`**：相关原始数据（若有）。

