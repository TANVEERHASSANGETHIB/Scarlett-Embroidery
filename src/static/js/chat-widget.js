(function () {
  "use strict";

  var root = document.querySelector("[data-chat-widget]");
  if (!root) return;

  var panel = root.querySelector("[data-chat-panel]");
  var launch = root.querySelector("[data-chat-launch]");
  var closeBtn = root.querySelector("[data-chat-close]");
  var body = root.querySelector("[data-chat-body]");
  var form = root.querySelector("[data-chat-form]");
  var input = form.querySelector("input[name=body]");
  var identity = root.querySelector("[data-chat-identity]");
  var stateEl = root.querySelector("[data-chat-state]");
  var unreadEl = root.querySelector("[data-chat-unread]");
  var sessionUrl = root.getAttribute("data-session-url");
  var isAuthenticated = root.getAttribute("data-authenticated") === "1";

  var socket = null;
  var loaded = false;
  var unread = 0;
  var retry = 0;
  var queue = [];
  var STORAGE_KEY = "se-chat-open";

  function setState(text) { stateEl.textContent = text || ""; }

  function bubble(msg) {
    var mine = msg.sender === "visitor";
    var el = document.createElement("div");
    el.className = "bubble " + (mine ? "bubble-me" : "bubble-them");
    el.textContent = msg.body;
    var meta = document.createElement("span");
    meta.className = "bubble-meta";
    meta.textContent = (mine ? "You" : msg.who) + " · " + msg.time;
    el.appendChild(meta);
    body.appendChild(el);
    body.scrollTop = body.scrollHeight;
  }

  function greet() {
    bubble({ sender: "staff", who: "Scarlett Embroidery", time: "now",
      body: "Hi! Send your artwork details and the fabric it's sewing on — a digitizer will reply right here." });
  }

  function setUnread(n) {
    unread = n;
    unreadEl.hidden = n === 0;
    unreadEl.textContent = String(n);
  }

  function isOpen() { return !panel.hidden; }

  function connect() {
    var proto = window.location.protocol === "https:" ? "wss://" : "ws://";
    socket = new WebSocket(proto + window.location.host + "/ws/chat/");
    socket.addEventListener("open", function () {
      retry = 0;
      setState("");
      socket.send(JSON.stringify({ type: "page", path: window.location.pathname, referrer: document.referrer }));
      while (queue.length) socket.send(queue.shift());
    });
    socket.addEventListener("message", function (e) {
      var data;
      try { data = JSON.parse(e.data); } catch (err) { return; }
      if (data.event === "message") {
        if (data.message.sender === "visitor") return; // already rendered optimistically
        bubble(data.message);
        if (!isOpen()) setUnread(unread + 1);
      } else if (data.event === "error") {
        setState(data.error);
      }
    });
    socket.addEventListener("close", function (e) {
      if (e.code === 4403) { setState("Chat is unavailable. Please email us instead."); form.hidden = true; return; }
      retry = Math.min(retry + 1, 6);
      setState("Reconnecting…");
      setTimeout(connect, 1000 * Math.pow(1.6, retry));
    });
  }

  function load() {
    if (loaded) return Promise.resolve();
    loaded = true;
    return fetch(sessionUrl, { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.blocked) { setState("Chat is unavailable. Please email us instead."); form.hidden = true; return; }
        greet();
        (data.messages || []).forEach(bubble);
        if (identity) identity.hidden = isAuthenticated || data.knownVisitor;
        connect();
      })
      .catch(function () { loaded = false; setState("Couldn't reach chat. Try again shortly."); });
  }

  function open() {
    panel.hidden = false;
    launch.setAttribute("aria-expanded", "true");
    setUnread(0);
    try { sessionStorage.setItem(STORAGE_KEY, "1"); } catch (e) { /* ignore */ }
    load().then(function () { input.focus(); });
  }

  function close() {
    panel.hidden = true;
    launch.setAttribute("aria-expanded", "false");
    try { sessionStorage.removeItem(STORAGE_KEY); } catch (e) { /* ignore */ }
  }

  launch.addEventListener("click", function () { isOpen() ? close() : open(); });
  closeBtn.addEventListener("click", close);

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var text = input.value.trim();
    if (!text) return;
    var payload = { type: "message", body: text, path: window.location.pathname, referrer: document.referrer };
    if (identity && !identity.hidden) {
      payload.name = identity.querySelector("input[name=name]").value.trim();
      payload.email = identity.querySelector("input[name=email]").value.trim();
    }
    var raw = JSON.stringify(payload);
    if (socket && socket.readyState === WebSocket.OPEN) socket.send(raw); else queue.push(raw);
    bubble({ sender: "visitor", body: text, time: new Date().toTimeString().slice(0, 5) });
    input.value = "";
    if (identity) identity.hidden = true;
  });

  try { if (sessionStorage.getItem(STORAGE_KEY)) open(); } catch (e) { /* ignore */ }
})();
