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

  // Header dropdowns (Services, More)
  var dropdowns = document.querySelectorAll("[data-dropdown]");
  function closeDropdowns(except) {
    dropdowns.forEach(function (d) {
      if (d === except) return;
      d.classList.remove("is-open");
      var b = d.querySelector(".nav-drop-btn");
      if (b) b.setAttribute("aria-expanded", "false");
    });
  }
  dropdowns.forEach(function (d) {
    var btn = d.querySelector(".nav-drop-toggle, button.nav-drop-btn");
    if (!btn) return;
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      closeDropdowns(d);
      var open = d.classList.toggle("is-open");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    });
  });
  document.addEventListener("click", function () { closeDropdowns(null); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeDropdowns(null); });

  // Pricing tabs (home)
  document.querySelectorAll("[data-price-tabs]").forEach(function (root) {
    var tabs = Array.prototype.slice.call(root.querySelectorAll("[data-price-tab]"));
    var panels = Array.prototype.slice.call(root.querySelectorAll("[data-price-panel]"));
    function select(name, focus) {
      tabs.forEach(function (t) {
        var on = t.getAttribute("data-price-tab") === name;
        t.classList.toggle("is-active", on);
        t.setAttribute("aria-selected", on ? "true" : "false");
        t.tabIndex = on ? 0 : -1;
        if (on && focus) t.focus();
      });
      panels.forEach(function (p) { p.hidden = p.getAttribute("data-price-panel") !== name; });
    }
    tabs.forEach(function (t, i) {
      t.addEventListener("click", function () { select(t.getAttribute("data-price-tab")); });
      t.addEventListener("keydown", function (e) {
        var next = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : null;
        if (next === null) return;
        e.preventDefault();
        select(tabs[(next + tabs.length) % tabs.length].getAttribute("data-price-tab"), true);
      });
    });
  });

  // Hero numbers count up when the page opens: "18,400+", "4 hrs", "99.2%", "34"
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  document.querySelectorAll("[data-count-up]").forEach(function (el) {
    var original = el.textContent.trim();
    var m = original.match(/^(\D*)([\d,]*\.?\d+)(.*)$/);
    if (!m || reduceMotion) return;
    var target = parseFloat(m[2].replace(/,/g, ""));
    var decimals = (m[2].split(".")[1] || "").length;
    var grouped = m[2].indexOf(",") !== -1;
    var duration = 1800;
    var format = function (n) {
      var text = n.toFixed(decimals);
      if (grouped) {
        var parts = text.split(".");
        parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        text = parts.join(".");
      }
      return m[1] + text + m[3];
    };
    el.setAttribute("aria-label", original);
    el.textContent = format(0);
    var start = null;
    function frame(ts) {
      if (start === null) start = ts;
      var t = Math.min(1, (ts - start) / duration);
      var eased = 1 - Math.pow(1 - t, 3);
      el.textContent = format(target * eased);
      if (t < 1) window.requestAnimationFrame(frame);
      else el.textContent = original;
    }
    window.requestAnimationFrame(frame);
  });

  // Before / after sliders: the invisible range input does the dragging (mouse, touch, keyboard).
  document.querySelectorAll("[data-before-after]").forEach(function (box) {
    var range = box.querySelector(".ba-range");
    if (!range) return;
    var set = function (v) { box.style.setProperty("--pos", v + "%"); };
    range.addEventListener("input", function () { set(range.value); });
    set(range.value);
    // A short nudge on first view so visitors see it is draggable.
    if (!reduceMotion && "IntersectionObserver" in window) {
      var played = false;
      new IntersectionObserver(function (entries, obs) {
        if (played || !entries[0].isIntersecting) return;
        played = true; obs.disconnect();
        var t0 = null;
        (function step(ts) {
          if (t0 === null) t0 = ts;
          var t = Math.min(1, (ts - t0) / 1400);
          if (document.activeElement === range) return;
          var v = 50 + Math.sin(t * Math.PI * 2) * 18 * (1 - t);
          range.value = v; set(v);
          if (t < 1) window.requestAnimationFrame(step);
        })(performance.now());
      }, { threshold: 0.6 }).observe(box);
    }
  });

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
    var listSelector = zone.getAttribute("data-dropzone");
    var list = (listSelector && document.querySelector(listSelector)) || zone.parentElement.querySelector("[data-file-list]");
    var maxBytes = Number(zone.getAttribute("data-max-bytes") || 0);
    if (!input) return;

    var renderList = function () {
      if (!list) return;
      list.innerHTML = "";
      Array.prototype.forEach.call(input.files, function (file) {
        var tooBig = maxBytes && file.size > maxBytes;
        var row = document.createElement("div");
        row.className = "file-row";
        row.innerHTML = '<div class="row" style="min-width:0;flex-wrap:nowrap"><div class="thumb placeholder-img"></div><div style="min-width:0"><div class="file-name"></div>' +
          '<div class="file-meta"></div><div class="file-progress" hidden><i></i></div></div></div><span class="badge"></span>';
        row.querySelector(".file-name").textContent = file.name;
        row.querySelector(".file-meta").textContent = formatBytes(file.size) + (tooBig ? " · too large" : " · attached");
        var badge = row.querySelector(".badge");
        badge.textContent = tooBig ? "Too large" : "Attached ✓";
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

  // Forms with files: send them with a progress bar, then show the page the server answers with.
  // <form data-progress> — falls back to a normal submit when no file is chosen.
  document.querySelectorAll("form[data-progress]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (e.defaultPrevented) return;
      var files = [];
      form.querySelectorAll("input[type=file]").forEach(function (input) {
        if (!input.disabled) Array.prototype.forEach.call(input.files, function (f) { files.push(f); });
      });
      if (!files.length || !window.XMLHttpRequest || !window.FormData) return;
      e.preventDefault();

      var submit = e.submitter || form.querySelector("button[type=submit], button:not([type])");
      var body;
      try { body = new FormData(form, e.submitter || undefined); } catch (err) { body = new FormData(form); }
      var rows = Array.prototype.slice.call(form.querySelectorAll("[data-file-list] .file-row"));

      var bar = form.querySelector(".upload-bar");
      if (!bar) {
        bar = document.createElement("div");
        bar.className = "upload-bar";
        bar.setAttribute("role", "progressbar");
        bar.setAttribute("aria-valuemin", "0");
        bar.setAttribute("aria-valuemax", "100");
        bar.innerHTML = '<div class="upload-bar-top"><span class="upload-bar-text"></span><span class="upload-bar-pct"></span></div>' +
          '<div class="upload-bar-track"><div class="upload-bar-fill"></div></div>';
        if (submit && submit.parentNode) submit.parentNode.insertBefore(bar, submit);
        else form.appendChild(bar);
      }
      var fill = bar.querySelector(".upload-bar-fill");
      var text = bar.querySelector(".upload-bar-text");
      var pctEl = bar.querySelector(".upload-bar-pct");
      var setBar = function (pct, label, state) {
        fill.style.width = pct + "%";
        pctEl.textContent = Math.round(pct) + "%";
        text.textContent = label;
        bar.setAttribute("aria-valuenow", String(Math.round(pct)));
        bar.classList.toggle("is-done", state === "done");
        bar.classList.toggle("is-error", state === "error");
      };
      bar.hidden = false;
      setBar(0, "Uploading " + files.length + " file" + (files.length === 1 ? "" : "s") + "…");
      if (submit) { submit.disabled = true; }
      rows.forEach(function (row) {
        var meta = row.querySelector(".file-meta");
        var prog = row.querySelector(".file-progress");
        if (prog) { prog.hidden = false; prog.firstChild.style.width = "0%"; }
        var badge = row.querySelector(".badge");
        if (badge) { badge.textContent = "Uploading"; badge.className = "badge badge-soft"; }
        if (meta) meta.dataset.base = meta.textContent.replace(/ · attached$/, "");
      });

      var total = files.reduce(function (n, f) { return n + f.size; }, 0) || 1;
      var xhr = new XMLHttpRequest();
      xhr.open((form.method || "POST").toUpperCase(), form.getAttribute("action") || window.location.href);
      xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");

      xhr.upload.addEventListener("progress", function (ev) {
        if (!ev.lengthComputable) return;
        var pct = Math.min(99, (ev.loaded / ev.total) * 100);
        setBar(pct, "Uploading… " + formatBytes(Math.min(total, Math.round(total * ev.loaded / ev.total))) + " of " + formatBytes(total));
        var sent = (ev.loaded / ev.total) * total, offset = 0;
        files.forEach(function (f, i) {
          var share = Math.max(0, Math.min(1, (sent - offset) / (f.size || 1)));
          offset += f.size;
          var row = rows[i];
          if (!row) return;
          var prog = row.querySelector(".file-progress");
          if (prog) prog.firstChild.style.width = Math.round(share * 100) + "%";
          if (share >= 1) {
            var badge = row.querySelector(".badge");
            if (badge) { badge.textContent = "Uploaded ✓"; badge.className = "badge badge-gold"; }
          }
        });
      });
      xhr.upload.addEventListener("load", function () { setBar(99, "Upload complete — saving…"); });

      var fail = function (message) {
        setBar(0, message, "error");
        if (submit) submit.disabled = false;
        rows.forEach(function (row) {
          var prog = row.querySelector(".file-progress");
          if (prog) prog.hidden = true;
          var badge = row.querySelector(".badge");
          if (badge) { badge.textContent = "Attached ✓"; badge.className = "badge badge-gold"; }
        });
      };
      xhr.addEventListener("error", function () { fail("Upload failed. Check your connection and try again."); });
      xhr.addEventListener("abort", function () { fail("Upload cancelled."); });
      xhr.addEventListener("load", function () {
        if (xhr.status >= 500) { fail("The server could not save the upload. Please try again."); return; }
        setBar(100, "All files uploaded ✓", "done");
        rows.forEach(function (row) {
          var prog = row.querySelector(".file-progress");
          if (prog) prog.firstChild.style.width = "100%";
          var badge = row.querySelector(".badge");
          if (badge) { badge.textContent = "Uploaded ✓"; badge.className = "badge badge-gold"; }
          var meta = row.querySelector(".file-meta");
          if (meta && meta.dataset.base) meta.textContent = meta.dataset.base + " · uploaded";
        });
        // The server already followed any redirect, so this is the page the visitor would have landed on.
        setTimeout(function () {
          try { if (xhr.responseURL) window.history.replaceState(null, "", xhr.responseURL); } catch (err) { /* cross-origin */ }
          document.open();
          document.write(xhr.responseText);
          document.close();
          window.scrollTo(0, 0);
        }, 500);
      });
      xhr.send(body);
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
