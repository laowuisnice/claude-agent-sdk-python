## `examples/plugin_example.py`

这个示例演示如何用 `ClaudeAgentOptions.plugins` 加载一个**本地插件**（local plugin），并通过 init 的 `SystemMessage` 验证插件是否配置/加载成功。

示例中提供的 demo 插件目录是：`examples/plugins/demo-plugin/`，并声明提供了一个自定义 `/greet` 命令（具体插件内容不在本文件里）。

---

### `async def plugin_example()`

**用途**

- 配置并加载一个本地插件路径，然后跑一次 `query("Hello!")`，在 init 系统消息里检查 `message.data["plugins"]`。

**关键段落**

- `plugin_path = Path(__file__).parent / "plugins" / "demo-plugin"`
  - 以示例文件位置为基准计算插件目录路径。
- `options = ClaudeAgentOptions(plugins=[{"type": "local", "path": str(plugin_path)}], max_turns=1)`
  - `plugins` 是一个列表，每项是 `SdkPluginConfig` 形状的 dict。
- 遍历 `query(...)` 的消息：
  - 遇到 `SystemMessage(subtype="init")`：
    - 打印 `message.data` 的 keys
    - 尝试读取 `plugins` 字段并打印其中的 `name/path`
    - 若系统消息里没有 `plugins` 字段，也会提示“可能不会出现在 system message”，但仍认为配置成功（`found_plugins=True`）

---

### `async def main()` / `anyio.run(main)`

只运行 `plugin_example()`。

---

### 你如何用在自己的智能体里

- 把 `plugin_path` 换成你自己的插件目录（可以是仓库内路径，也可以是绝对路径）。
- 用 init 系统消息做一次“自检”，确认插件命令/agent/skill 是否被加载到 CLI 环境中。

