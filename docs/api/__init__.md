## `claude_agent_sdk.__init__`

这个模块的主要作用是：

- 作为 **SDK 的顶层入口**：把常用的类/函数/类型从子模块 re-export 出来（你通常只需要 `import claude_agent_sdk` 或 `from claude_agent_sdk import ...`）。
- 提供 **SDK MCP（进程内 MCP 服务器）** 的便捷封装：`SdkMcpTool`、`tool()`、`create_sdk_mcp_server()`。

> 说明：本文件还导出了大量类型/函数（例如 session 列表/重命名等），它们本身的定义不在这里，而在 `types.py` 或 `_internal/*`。本文只解释 **在本文件中定义的类/函数**。

---

## `@dataclass class SdkMcpTool(Generic[T])`

**用途**

- 描述一个“可被 Claude 调用的工具”的定义对象（名字、描述、入参 schema、处理函数、注解）。
- 它是 `tool()` 装饰器的返回物，也是 `create_sdk_mcp_server(..., tools=[...])` 的输入。

**字段**

- **`name: str`**：工具名。Claude 侧会以这个名字调用工具（在 MCP 里相当于 tool id）。
- **`description: str`**：工具描述，帮助模型判断何时调用。
- **`input_schema: type[T] | dict[str, Any]`**：入参 schema。
  - 简单用法是 `{"a": float, "b": float}` 这种 “字段→类型” 映射；
  - 也可以直接给 JSON Schema dict（当它同时包含 `type` 和 `properties` 时，会被当成 JSON Schema 处理）。
- **`handler: Callable[[T], Awaitable[dict[str, Any]]]`**：真正执行工具的 async 函数。入参是 `arguments`，返回一个 dict（通常含 `content`）。
- **`annotations: ToolAnnotations | None`**：MCP 的工具注解（只读/破坏性/open-world 等）。

**返回格式约定（handler 返回）**

- 典型格式：`{"content": [{"type": "text", "text": "..."}]}`
- 错误：可返回 `{"content": [...], "is_error": True}`（是否真的被 CLI/上层以“错误”处理取决于整个工具链，但这是常见约定）。

---

## `def tool(...) -> Callable[[handler], SdkMcpTool]`

**用途**

- 一个装饰器工厂：把你写的 `async def my_tool(args): ...` 包装成 `SdkMcpTool`，并把 schema/描述一起绑定。
- 目标是：让“进程内工具”以 MCP 的形式暴露给 Claude，但工具代码直接跑在你的 Python 进程里（无需另起 MCP 子进程）。

**签名（关键参数）**

- **`name: str`**：工具名（必须唯一，否则调用时会冲突）。
- **`description: str`**：描述。
- **`input_schema: type | dict[str, Any]`**：入参 schema（见 `SdkMcpTool.input_schema`）。
- **`annotations: ToolAnnotations | None`**：工具注解。

**返回值**

- 返回一个装饰器；装饰器接收你的 async handler，并输出 `SdkMcpTool` 实例。

**常见坑**

- **handler 必须是 async**（`Awaitable[...]`）。
- `input_schema` 如果是简单 dict 映射，SDK 会把所有键都当成 required；如果你需要可选字段，考虑直接提供 JSON Schema。

---

## `def create_sdk_mcp_server(name, version="1.0.0", tools=None) -> McpSdkServerConfig`

**用途**

- 创建一个“进程内 MCP 服务器”配置，让 Claude Code CLI 通过 SDK 控制协议把工具调用路由到你的 Python 进程里执行。
- 你会把返回值塞进 `ClaudeAgentOptions.mcp_servers`，例如：
  - `ClaudeAgentOptions(mcp_servers={"tools": server_config})`

**关键参数**

- **`name: str`**：服务器标识（在 `mcp_servers` 字典里的 key 是别名；而这里的 `name` 是 MCP Server 自身的名字，会出现在状态/握手里）。
- **`version: str`**：仅信息用途。
- **`tools: list[SdkMcpTool] | None`**：该 server 暴露的工具集合。

**内部机制（你理解即可，不需要手动调用）**

- 内部创建 `mcp.server.Server(name, version=...)`。
- 注册两个 MCP handler：
  - **`list_tools()`**：把 `tools` 转成 MCP `Tool` 列表，并把 `input_schema` 转成 JSON Schema 形态。
  - **`call_tool(name, arguments)`**：按 name 找到 tool，执行 `tool.handler(arguments)`，把返回结果转成 MCP 的 `TextContent`/`ImageContent` 列表。
- 最终返回 `McpSdkServerConfig(type="sdk", name=name, instance=server)`，其中 `instance` 会被 `ClaudeSDKClient.connect()` 抽取出来用于路由。

**常见坑**

- 你在 `allowed_tools` 里要写的通常是形如 `mcp__<server_alias>__<tool_name>`（具体前缀约定以 CLI/SDK 组合为准；README 示例里是 `mcp__tools__greet`）。
- `input_schema` 的转换逻辑对非基础类型会退化为 string（默认兜底）。复杂 schema 建议直接给 JSON Schema dict。

