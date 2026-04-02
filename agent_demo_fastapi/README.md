# agent_demo_fastapi：基于 Claude Agent SDK 的网页对话 Demo

本目录是一个**教学/演示用**的小型 Web 应用：浏览器里多轮聊天、流式显示助手回复，并在需要时让你**人工批准或拒绝** Claude Code 发起的工具调用（例如读写文件、执行命令等）。  

它不依赖仓库里的 `agent_demo/`（Gradio 版），可独立运行；与模型、CLI 的实际交互全部由本仓库的 **`claude_agent_sdk`**（通过子进程调用 **Claude Code CLI**）完成。

---

## 这个 Demo 在做什么？（概念）

1. **前端（HTML + JS）**  
   - 左侧：历史会话列表，可新建、切换会话。  
   - 右侧上方：**权限/确认区**。当 Agent 要执行某个工具时，后端会把请求推到这里，你点「允许」或「拒绝」。  
   - 右侧中间：**对话区**，显示用户消息和助手回复（流式更新）。  
   - 底部：输入框 + 发送按钮（**Enter 发送**，Shift+Enter 换行）。

2. **后端（FastAPI）**  
   - 使用 SDK 的 **`ClaudeSDKClient`** 与 CLI 建立长连接，按轮次发送用户输入，并接收流式事件与完整消息。  
   - 通过 **`ClaudeAgentOptions(can_use_tool=...)`** 注册回调：每次 CLI 询问「是否允许某工具」时，回调会挂起，直到你在网页上点允许/拒绝（内部用 `asyncio.Future` 桥接 HTTP）。

3. **数据**  
   - 会话标题、消息列表等保存在本目录下的 **`data/conversations.json`**（首次运行后生成），写入采用临时文件再替换，减少损坏风险。  
   - Agent 实际读写代码/执行命令的工作目录默认是 **`workspace/`**，避免直接动整个仓库根目录。

4. **实时推送**  
   - 使用 **SSE（Server-Sent Events）**：浏览器用 `EventSource` 连接 `GET /api/conversations/{id}/events`，服务端持续推送 JSON 事件（流式文本、权限请求、结束等）。  
   - 发送消息、确认权限使用普通 **REST POST**。

---

## 你需要准备什么？

| 项目 | 说明 |
|------|------|
| Python | 建议 3.10+（与 SDK 要求一致）。 |
| 本仓库 SDK | 在仓库根目录执行 `pip install -e .`，以便 `import claude_agent_sdk`。 |
| Claude Code CLI | 本 Demo **不会**自己实现大模型调用，而是通过 SDK 启动 **Claude Code** 子进程。你需要已按官方文档安装并能在本机正常使用 Claude Code（登录、网络、模型权限等）。若 CLI 不可用，浏览器里会表现为连接失败、无回复或错误日志。 |
| 依赖 | `pip install -r agent_demo_fastapi/requirements.txt`（FastAPI、Uvicorn）。 |

官方 SDK / Claude Code 文档入口（安装与排错以最新文档为准）：  
<https://docs.anthropic.com/en/docs/claude-code/sdk>

---

## 目录结构（本 Demo）

```
agent_demo_fastapi/
├── README.md              # 本说明
├── 计划表.md              # SDK 公开 API 迭代清单（后续功能可对照勾选）
├── requirements.txt       # FastAPI / Uvicorn
├── main.py                # FastAPI 路由、静态资源、SSE
├── agent_service.py       # ClaudeSDKClient 封装、多轮与流式、会话管理
├── permission_bridge.py   # 工具权限：Future + HTTP 允许/拒绝
├── options.py             # ClaudeAgentOptions 组装（cwd、partial messages 等）
├── storage.py             # JSON 读写与原子保存
├── data/                  # conversations.json 存放处（可 gitignore）
├── workspace/             # 交给 CLI 的默认工作目录（Agent 工具多作用于此）
└── static/                # 前端
    ├── index.html
    ├── app.js
    └── style.css
```

---

## 安装与启动

在**仓库根目录**执行（路径请按你的机器调整）：

```bash
# 1. 安装本仓库 SDK（可编辑模式）
pip install -e .

# 2. 安装 Demo 依赖
pip install -r agent_demo_fastapi/requirements.txt

# 3. 启动服务（任选一种）
python -m uvicorn agent_demo_fastapi.main:app --host 127.0.0.1 --port 8000
# 或
python -m agent_demo_fastapi.main
```

浏览器打开：**http://127.0.0.1:8000/**  

若修改了代码，可改用 Uvicorn 的 `--reload` 做开发热重载（仅本地调试时使用）。

---

## 使用说明（界面流程）

1. **新建对话**  
   点击「新建对话」，左侧会出现新会话；此时会选中该会话并尝试建立 SSE 连接。

2. **切换会话**  
   点击左侧某条会话，会：  
   - 将该会话设为当前活跃会话；  
   - **断开其他会话在内存中的 CLI 连接**（节省资源）；  
   - 从 JSON 加载历史消息并重新连接 SSE。

3. **发送消息**  
   在底部输入文字，点发送按钮或按 **Enter**。  
   用户消息会先显示在对话区，然后后端异步跑一轮 Agent；助手回复通过 SSE **流式**追加显示。

4. **工具权限（重要）**  
   当 Claude 要执行工具时，上方黄色 **权限条** 会出现工具名、参数摘要等。  
   - 点 **允许**：当前这一次工具调用继续执行。  
   - 点 **拒绝**：拒绝本次调用（具体行为以 SDK/CLI 为准）。  
   若长时间不操作，服务端会对挂起的权限请求做**超时拒绝**（避免永久占住进程），详见 `permission_bridge.py` 中的超时设置。

5. **建议操作顺序（避免漏事件）**  
   先让页面完成**会话切换**（从而建立 SSE），再发送消息，这样流式与权限事件不会丢。若网络断开，SSE 可能中断，可刷新页面或重新点选会话。

---

## 后端行为摘要（便于排查）

- **多轮上下文**：首轮若 JSON 里已有历史，会把历史摘要注入到用户消息前（与 `examples/streaming_mode.py` 里「多轮」思路类似）；同一浏览器会话内 CLI 连接会复用，直到切换会话或进程退出。  
- **`can_use_tool` 与 `connect()`**：启用权限回调时，SDK 要求**不能**用字符串形式在 `connect()` 里带初始 prompt；本 Demo 使用 `await client.connect()`（无字符串），再通过 `query(...)` 发消息。  
- **工作目录**：`ClaudeAgentOptions(cwd=...)` 指向 `agent_demo_fastapi/workspace/`，请把「允许 Agent 改动的试验文件」放在该目录下更安全。  
- **关闭服务**：Uvicorn 退出时，`lifespan` 会尝试 **disconnect** 所有 `ClaudeSDKClient`，并取消未决的权限等待。

---

## HTTP API 一览（调试或二次开发）

| 方法 | 路径 | 作用 |
|------|------|------|
| GET | `/api/conversations` | 会话列表与当前 `active_id` |
| POST | `/api/conversations` | 新建会话（可选 JSON body：`{"title": "..."}`） |
| GET | `/api/conversations/{id}` | 单个会话详情（含 `messages`） |
| DELETE | `/api/conversations/{id}` | 删除会话并释放内存中的会话对象 |
| POST | `/api/conversations/{id}/active` | 设为活跃并断开其他会话的 CLI |
| POST | `/api/conversations/{id}/messages` | 发送用户消息，body：`{"text": "..."}` |
| POST | `/api/conversations/{id}/permission` | 权限结果，body：`{"allow": true}` 或 `false` |
| GET | `/api/conversations/{id}/events` | **SSE** 事件流 |

SSE 每条 `data:` 后是一段 JSON，常见字段：  

- `type: "delta"`：助手当前累积文本（`text`）。  
- `type: "permission_request"`：需要用户确认的工具调用。  
- `type: "result"`：本轮结束及费用等信息。  
- `type: "error"`：错误信息。  
- `type: "done"`：本轮事件结束标记。

---

## 常见问题

**Q：页面空白或接口 404？**  
确认从仓库根目录启动 Uvicorn，且 URL 为 `http://127.0.0.1:8000/`（根路径返回 `index.html`，静态资源在 `/static/`）。

**Q：一直没有助手回复？**  
检查本机 Claude Code CLI 是否可用、终端里 Uvicorn 日志是否有 `CLIConnectionError` 等；确认网络与账号权限。

**Q：`data/conversations.json` 能否删？**  
可以；删后相当于清空本地会话记录。`workspace/` 里文件是否保留由你决定。

**Q：和 `agent_demo/` 什么关系？**  
没有关系；本 Demo **不 import** `agent_demo`。删除 `agent_demo` 不影响本目录。

---

## 后续迭代

更完整的 SDK 能力（`query()`、Hooks、MCP、`list_sessions` 等）可按 **[计划表.md](./计划表.md)** 逐项接入本 Demo；表中标注了建议阶段与示例文件路径。

---

## 许可

与本仓库 **claude-agent-sdk-python** 一致（见仓库根目录 `LICENSE` / `README.md`）。
