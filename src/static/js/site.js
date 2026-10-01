(function () {
  "use strict";

  // Mobile navigation
  var header = document.querySelector("[data-site-header]");
  var toggle = document.querySelector("[data-nav-toggle]");
  if (header && toggle) {
    toggle.addEventListener("click", function () {
      var open = header.classList.toggle("nav-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  // Flash messages: dismiss + auto-hide
  document.querySelectorAll("[data-flash]").forEach(function (el) {
    var close = function () { el.remove(); };
    var btn = el.querySelector("button");
    if (btn) btn.addEventListener("click", close);
    if (!el.classList.contains("flash-error")) setTimeout(close, 7000);
  });

  // Home showcase switcher
  var showcaseData = document.getElementById("showcase-data");
  if (showcaseData) {
    var items = JSON.parse(showcaseData.textContent);
    var root = document.querySelector("[data-showcase]");
    var render = function (index) {
      var item = items[index];
      if (!item) return;
      root.querySelectorAll("[data-sc-name]").forEach(function (n) { n.textContent = item.name; });
      root.querySelector("[data-sc-tag]").textContent = item.tag;
      var img = root.querySelector("[data-sc-img]");
      if (item.image) { img.src = item.image; img.alt = item.name; img.hidden = false; }
      else { img.hidden = true; img.removeAttribute("src"); }
      var specs = root.querySelector("[data-sc-specs]");
      specs.innerHTML = "";
      item.specs.forEach(function (row) {
        var div = document.createElement("div");
        div.className = "spec-row";
        var k = document.createElement("span"); k.className = "label"; k.textContent = row[0];
        var v = document.createElement("span"); v.className = "v"; v.textContent = row[1];
        div.appendChild(k); div.appendChild(v); specs.appendChild(div);
      });
      root.querySelectorAll("[data-sc-thumb]").forEach(function (t) {
        var active = Number(t.getAttribute("data-sc-thumb")) === index;
        t.classList.toggle("is-active", active);
        t.setAttribute("aria-pressed", active ? "true" : "false");
      });
    };
    root.querySelectorAll("[data-sc-thumb]").forEach(function (t) {
      t.addEventListener("click", function () { render(Number(t.getAttribute("data-sc-thumb"))); });
    });
  }

  // File drop zones: <div data-dropzone> containing an <input type=file> and a [data-file-list]
  function formatBytes(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1048576).toFixed(1) + " MB";
  }
  document.querySelectorAll("[data-dropzone]").forEach(function (zone) {
    var input = zone.querySelector("input[type=file]");
    var list = document.querySelector(zone.getAttribute("data-dropzone")) || zone.parentElement.querySelector("[data-file-list]");
    var maxBytes = Number(zone.getAttribute("data-max-bytes") || 0);
    if (!input) return;

    var renderList = function () {
      if (!list) return;
      list.innerHTML = "";
      Array.prototype.forEach.call(input.files, function (file) {
        var tooBig = maxBytes && file.size > maxBytes;
        var row = document.createElement("div");
        row.className = "file-row";
        row.innerHTML = '<div class="row"><div class="thumb placeholder-img"></div><div><div class="file-name"></div>' +
          '<div class="file-meta"></div></div></div><span class="badge"></span>';
        row.querySelector(".file-name").textContent = file.name;
        row.querySelector(".file-meta").textContent = formatBytes(file.size) + (tooBig ? " · too large" : " · ready to upload");
        var badge = row.querySelector(".badge");
        badge.textContent = tooBig ? "Too large" : "Ready";
        badge.className = "badge " + (tooBig ? "badge-danger" : "badge-gold");
        list.appendChild(row);
      });
    };

    zone.querySelectorAll("[data-browse]").forEach(function (b) {
      b.addEventListener("click", function (e) { e.preventDefault(); input.click(); });
    });
    input.addEventListener("change", renderList);
    ["dragenter", "dragover"].forEach(function (ev) {
      zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.add("is-over"); });
    });
    ["dragleave", "drop"].forEach(function (ev) {
      zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.remove("is-over"); });
    });
    zone.addEventListener("drop", function (e) {
      if (!e.dataTransfer || !e.dataTransfer.files.length) return;
      var dt = new DataTransfer();
      Array.prototype.forEach.call(input.files, function (f) { dt.items.add(f); });
      Array.prototype.forEach.call(e.dataTransfer.files, function (f) { dt.items.add(f); });
      input.files = dt.files;
      renderList();
    });
  });

  // Prevent double submits
  document.querySelectorAll("form[data-once]").forEach(function (form) {
    form.addEventListener("submit", function () {
      form.querySelectorAll("button[type=submit]").forEach(function (b) {
        setTimeout(function () { b.setAttribute("aria-disabled", "true"); }, 0);
      });
    });
  });

  // Confirm dangerous actions
  document.addEventListener("click", function (e) {
    var el = e.target.closest("[data-confirm]");
    if (el && !window.confirm(el.getAttribute("data-confirm"))) { e.preventDefault(); e.stopPropagation(); }
  }, true);
})();
