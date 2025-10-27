// simple websocket chat client
let currentChannel = "general";
let ws = null;

function connectWebSocket(channel = "general") {
  if (ws) ws.close();
  ws = new WebSocket((location.protocol === "https:" ? "wss" : "ws") + "://" + location.host + "/ws/" + channel);

  ws.onopen = () => console.log("WS connected to", channel);
  ws.onmessage = (e) => {
    try {
      const d = JSON.parse(e.data);
      const box = document.getElementById("chatbox");
      if (!box) return;
      const el = document.createElement("div");
      el.textContent = `[${d.time}] ${d.user}: ${d.text}`;
      box.appendChild(el);
      box.scrollTop = box.scrollHeight;
    } catch (err) {
      console.error("ws parse error", err);
    }
  };
  ws.onclose = () => console.log("WS closed");
}

function sendMessage() {
  const user = document.getElementById("username")?.value || "anon";
  const text = document.getElementById("message")?.value || document.getElementById("msg")?.value;
  if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ user: user, text: text }));
  const input = document.getElementById("message") || document.getElementById("msg");
  if (input) input.value = "";
}

function switchChannel(name) {
  currentChannel = name;
  document.getElementById("chatbox").innerHTML = "";
  document.getElementById("channelTitle").innerText = "#" + name;
  connectWebSocket(name);
}

function createChannel() {
  const name = document.getElementById("newChannelName").value.trim();
  if (!name) return;
  const ul = document.getElementById("channelsList");
  const li = document.createElement("li");
  li.textContent = name;
  li.onclick = () => switchChannel(name);
  ul.appendChild(li);
  document.getElementById("newChannelName").value = "";
  // local channels list only; no server persistence in this dev build
}

window.addEventListener("load", () => connectWebSocket("general"));
