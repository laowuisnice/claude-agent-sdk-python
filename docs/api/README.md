## 这套文档是什么

这里是对 `src/claude_agent_sdk/` **对外 API** 的“逐符号（每个类/函数）解释”。

- 面向目标：你想用本仓库 + Claude Agent SDK 写一个自用智能体，能快速知道每个入口符号的职责、在运行时出现的位置、以及常见配置/坑。
- 范围：只覆盖你会在业务代码里直接 `import` 的模块（以及这些模块里定义的类/函数/方法）。

## 目录

- [__init__.md](__init__.md)：顶层导出、SDK MCP（进程内工具）相关：`SdkMcpTool`、`tool()`、`create_sdk_mcp_server()`
- [query.md](query.md)：一次性查询入口：`query()`
- [client.md](client.md)：交互式客户端：`ClaudeSDKClient`（及其所有公开方法）
- [types.md](types.md)：核心类型与配置：`ClaudeAgentOptions`、消息/内容块、Hooks、权限、MCP 配置等
- [errors.md](errors.md)：错误类型：`ClaudeSDKError` 等

## 阅读顺序建议

1. [query.md](query.md)（先跑通一次性调用）
2. [client.md](client.md)（需要多轮/可中断/动态发送消息时）
3. [types.md](types.md)（你需要认真配 `ClaudeAgentOptions` 时）
4. [__init__.md](__init__.md)（自定义工具、进程内 MCP）
5. [errors.md](errors.md)（上线前的异常处理）

