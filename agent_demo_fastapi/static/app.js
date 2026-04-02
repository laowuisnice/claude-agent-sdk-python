/* global EventSource */

const $ = (id) => document.getElementById(id);

let activeConvId = null;
let pollAbort = null;
let pendingPermission = null;

function setStatus(text) {
  $("status").textContent = text || "";
}

async function api(path, options = {}) {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  if (r.status === 204) return null;
  return r.json();
}

function renderMessages(messages) {
  const area = $("chat-area");
  area.innerHTML = "";
  for (const m of messages || []) {
    const div = document.createElement("div");
    const role = m.role === "user" ? "user" : "assistant";
    div.className = `msg ${role}`;
    div.textContent = m.content || "";
    area.appendChild(div);
  }
  area.scrollTop = area.scrollHeight;
}

async function loadConversations() {
  const data = await api("/api/conversations");
  const list = $("conv-list");
  list.innerHTML = "";
  for (const c of data.conversations) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className =
      "conv-item" + (c.id === data.active_id ? " active" : "");
    btn.dataset.id = c.id;
    const title = document.createElement("div");
    title.className = "conv-title";
    title.textContent = c.title || c.id;
    const meta = document.createElement("div");
    meta.className = "conv-meta";
    meta.textContent = c.updated_at || "";
    btn.appendChild(title);
    btn.appendChild(meta);
    btn.addEventListener("click", () => selectConversation(c.id));
    list.appendChild(btn);
  }
  if (data.active_id && !activeConvId) {
    await selectConversation(data.active_id);
  }
}

function stopPolling() {
  if (pollAbort) {
    pollAbort.abort();
    pollAbort = null;
  }
}

async function selectConversation(convId) {
  activeConvId = convId;
  stopPolling();
  await api(`/api/conversations/${encodeURIComponent(convId)}/active`, {
    method: "POST",
  });
  const conv = await api(`/api/conversations/${encodeURIComponent(convId)}`);
  renderMessages(conv.conversation.messages);
  await loadConversations();
  startPolling(convId);
  hidePermission();
}

function hidePermission() {
  pendingPermission = null;
  $("permission-bar").classList.remove("visible");
  $("permission-detail").textContent = "";
}

function showPermission(payload) {
  pendingPermission = payload;
  $("permission-bar").classList.add("visible");
  const lines = [
    `tool: ${payload.tool_name}`,
    `request_id: ${payload.request_id}`,
    `tool_use_id: ${payload.tool_use_id || ""}`,
    JSON.stringify(payload.input, null, 2),
  ];
  $("permission-detail").textContent = lines.join("\n");
}

async function startPolling(convId) {
  stopPolling();
  pollAbort = new AbortController();
  const signal = pollAbort.signal;

  let since = 0;
  let streamingAssistant = null;

  async function handleEvent(data) {
    const chat = $("chat-area");
    if (data.type === "delta") {
      if (!streamingAssistant) {
        streamingAssistant = document.createElement("div");
        streamingAssistant.className = "msg assistant";
        chat.appendChild(streamingAssistant);
      }
      streamingAssistant.textContent = data.text || "";
      chat.scrollTop = chat.scrollHeight;
    } else if (data.type === "permission_request") {
      showPermission(data);
    } else if (data.type === "result") {
      setStatus(
        data.total_cost_usd != null
          ? `完成 · 约 $${Number(data.total_cost_usd).toFixed(4)}`
          : "完成"
      );
      streamingAssistant = null;
    } else if (data.type === "error") {
      setStatus(`错误: ${data.message}`);
      const err = document.createElement("div");
      err.className = "msg system";
      err.textContent = data.message;
      chat.appendChild(err);
      streamingAssistant = null;
    } else if (data.type === "done") {
      streamingAssistant = null;
    }
  }

  async function loop() {
    while (!signal.aborted && activeConvId === convId) {
      try {
        const r = await fetch(
          `/api/conversations/${encodeURIComponent(convId)}/events_poll?since=${since}&timeout_sec=2`,
          { signal }
        );
        if (r.status === 503) {
          setStatus("服务正在关闭，已停止轮询");
          stopPolling();
          return;
        }
        if (!r.ok) throw new Error(await r.text());
        const payload = await r.json();
        const events = payload.events || [];
        for (const ev of events) {
          since = Math.max(since, Number(ev._seq || 0));
          await handleEvent(ev);
        }
        // 心跳：即便 events 为空，也会在 2s 内返回一次，然后继续下一轮
      } catch (e) {
        if (signal.aborted) return;
        setStatus(`连接异常: ${String(e)}`);
        // 简单退避
        await new Promise((res) => setTimeout(res, 800));
      }
    }
  }

  loop();
}

async function newConversation() {
  const data = await api("/api/conversations", {
    method: "POST",
    body: JSON.stringify({}),
  });
  activeConvId = data.conversation.id;
  await selectConversation(activeConvId);
}

async function sendMessage() {
  const input = $("input");
  const text = input.value.trim();
  if (!text || !activeConvId) return;
  input.value = "";
  setStatus("…");
  const userDiv = document.createElement("div");
  userDiv.className = "msg user";
  userDiv.textContent = text;
  $("chat-area").appendChild(userDiv);
  $("chat-area").scrollTop = $("chat-area").scrollHeight;
  try {
    await api(
      `/api/conversations/${encodeURIComponent(activeConvId)}/messages`,
      { method: "POST", body: JSON.stringify({ text }) }
    );
  } catch (e) {
    setStatus(String(e));
  }
}

async function postPermission(allow) {
  if (!activeConvId || !pendingPermission) return;
  try {
    await api(
      `/api/conversations/${encodeURIComponent(activeConvId)}/permission`,
      { method: "POST", body: JSON.stringify({ allow }) }
    );
    hidePermission();
  } catch (e) {
    setStatus(String(e));
  }
}

$("btn-new").addEventListener("click", () => newConversation().catch((e) => setStatus(String(e))));
$("btn-send").addEventListener("click", () => sendMessage());
$("btn-allow").addEventListener("click", () => postPermission(true));
$("btn-deny").addEventListener("click", () => postPermission(false));

$("input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

loadConversations().catch((e) => setStatus(String(e)));
