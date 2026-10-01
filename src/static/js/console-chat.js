(function () {
  "use strict";

  var ws = document.querySelector("[data-chat-ws]");
  if (!ws) return;

  var activeId = ws.getAttribute("data-active") || "";
  var list = ws.querySelector("[data-chat-list]");
  var thread = ws.querySelector("[data-thread]");
  var form = ws.querySelector("[data-reply-form]");
  var statusEl = document.querySelector("[data-ws-status]");
  var baseUrl = ws.getAttribute("data-base-url");
  var retry = 0;
  var socket;

  if (thread) thread.scrollTop = thread.scrollHeight;

  function setLive(live) {
    if (!statusEl) return;
    statusEl.classList.toggle("is-live", live);
    statusEl.lastChild.textContent = live ? " live" : " reconnecting…";
  }

  function appendMessage(m) {
    if (!thread || String(m.session) !== String(activeId)) return;
    var wrap = document.createElement("div");
    wrap.className = "msg " + (m.sender === "staff" ? "from-staff" : "from-visitor");
    var bubble = document.createElement("div");
    bubble.className = "msg-bubble";
    var text = document.createElement("div");
    text.className = "msg-text";
    text.textContent = m.body;
    var meta = document.createElement("div");
    meta.className = "msg-meta";
    meta.textContent = (m.sender === "visitor" ? (ws.getAttribute("data-active-name") || "Visitor") : m.who) + " · " + m.time;
    bubble.appendChild(text);
    bubble.appendChild(meta);
    wrap.appendChild(bubble);
    thread.appendChild(wrap);
    thread.scrollTop = thread.scrollHeight;
  }

  function upsertSession(s) {
    if (!list || !s) return;
    var item = list.querySelector('[data-session="' + s.id + '"]');
    if (!item) {
      item = document.createElement("a");
      item.className = "chat-item";
      item.setAttribute("data-session", s.id);
      item.href = baseUrl + "?s=" + s.id;
      item.innerHTML = '<div class="row" style="justify-content:space-between;gap:8px;margin-bottom:3px">' +
        '<span class="name"></span><span class="time"></span></div><div class="preview"></div>' +
        '<div class="row" style="gap:8px;margin-top:8px"><span class="tag"></span><span class="time ip"></span></div>';
      var empty = list.querySelector("[data-empty]");
      if (empty) empty.remove();
    }
    item.querySelector(".name").textContent = s.name;
    item.querySelector(".time").textContent = s.time;
    item.querySelector(".preview").textContent = s.preview;
    var tag = item.querySelector(".tag");
    tag.textContent = s.statusLabel;
    tag.className = "tag tag-" + s.status;
    item.querySelector(".ip").textContent = s.ip;
    if (String(s.id) === String(activeId)) item.classList.add("is-active");
    list.insertBefore(item, list.firstChild);
    if (String(s.id) === String(activeId)) {
      var pageEl = document.querySelector("[data-active-page]");
      if (pageEl) pageEl.textContent = s.page;
    }
  }

  function connect() {
    var proto = window.location.protocol === "https:" ? "wss://" : "ws://";
    socket = new WebSocket(proto + window.location.host + "/ws/console/chat/");
    socket.addEventListener("open", function () { retry = 0; setLive(true); });
    socket.addEventListener("message", function (e) {
      var data;
      try { data = JSON.parse(e.data); } catch (err) { return; }
      if (data.session) upsertSession(data.session);
      if (data.event === "message") {
        appendMessage(data.message);
        if (data.message.sender === "visitor" && document.hidden && document.title.indexOf("● ") !== 0) {
          document.title = "● " + document.title;
        }
      }
    });
    socket.addEventListener("close", function () {
      setLive(false);
      retry = Math.min(retry + 1, 6);
      setTimeout(connect, 1000 * Math.pow(1.6, retry));
    });
  }

  if (form) {
    form.addEventListener("submit", function (e) {
      var input = form.querySelector("input[name=body]");
      var text = input.value.trim();
      if (!text) { e.preventDefault(); return; }
      if (socket && socket.readyState === WebSocket.OPEN) {
        e.preventDefault();
        socket.send(JSON.stringify({ type: "message", session: activeId, body: text }));
        input.value = "";
        input.focus();
      }
      // Otherwise fall back to the normal POST form submit.
    });
  }

  document.addEventListener("visibilitychange", function () {
    if (!document.hidden && document.title.indexOf("● ") === 0) document.title = document.title.slice(2);
  });

  connect();
})();
