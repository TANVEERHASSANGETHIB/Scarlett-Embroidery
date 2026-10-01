(function () {
  "use strict";

  var root = document.querySelector("[data-settings]");
  if (!root) return;

  // ── Tabs ────────────────────────────────────────────────
  var tabs = Array.prototype.slice.call(root.querySelectorAll("[data-tab]"));
  var panels = Array.prototype.slice.call(root.querySelectorAll("[data-panel]"));

  function show(slug, push) {
    var known = tabs.some(function (t) { return t.getAttribute("data-tab") === slug; });
    if (!known) return;
    tabs.forEach(function (t) {
      var on = t.getAttribute("data-tab") === slug;
      t.classList.toggle("is-active", on);
      t.setAttribute("aria-current", on ? "true" : "false");
    });
    panels.forEach(function (p) { p.hidden = p.getAttribute("data-panel") !== slug; });
    if (push) {
      var url = new URL(window.location.href);
      url.searchParams.set("tab", slug);
      window.history.replaceState({}, "", url);
    }
  }

  tabs.forEach(function (t) {
    t.addEventListener("click", function () { show(t.getAttribute("data-tab"), true); });
  });

  // ── Repeatable rows ─────────────────────────────────────
  root.querySelectorAll("[data-rows]").forEach(function (group) {
    var prefix = group.getAttribute("data-prefix");
    var list = group.querySelector("[data-row-list]");
    var template = group.querySelector("[data-row-template]");
    var addBtn = group.querySelector("[data-add-row]");
    var totalInput = group.querySelector('input[name="' + prefix + '-TOTAL_FORMS"]');
    var emptyNote = group.querySelector("[data-rows-empty]");

    function visibleRows() {
      return Array.prototype.filter.call(list.querySelectorAll("[data-row]"), function (row) {
        var del = row.querySelector('input[type=checkbox][name$="-DELETE"]');
        return !del || !del.checked;
      });
    }

    function refreshEmpty() {
      if (emptyNote) emptyNote.hidden = visibleRows().length > 0;
    }

    function markDirty() {
      var form = group.closest("form");
      if (form) form.dispatchEvent(new Event("change", { bubbles: true }));
    }

    if (addBtn && template && totalInput) {
      addBtn.addEventListener("click", function () {
        var index = parseInt(totalInput.value, 10) || 0;
        var html = template.innerHTML.replace(/__prefix__/g, String(index));
        var holder = document.createElement("div");
        holder.innerHTML = html.trim();
        var row = holder.firstElementChild;
        row.classList.add("is-new");
        list.appendChild(row);
        totalInput.value = String(index + 1);
        var first = row.querySelector("input:not([type=hidden]):not([type=checkbox]), select");
        if (first) first.focus();
        refreshEmpty();
        markDirty();
      });
    }

    // Removing a brand-new row takes it out entirely; an existing row is
    // flagged for deletion so the server removes it on save.
    list.addEventListener("change", function (e) {
      if (!e.target.matches('input[type=checkbox][name$="-DELETE"]')) return;
      var row = e.target.closest("[data-row]");
      row.classList.toggle("is-deleted", e.target.checked);
      if (e.target.checked && row.classList.contains("is-new")) {
        row.remove();
        reindex();
      }
      refreshEmpty();
    });

    // Keep form indexes contiguous after removing an unsaved row.
    function reindex() {
      var rows = list.querySelectorAll("[data-row]");
      rows.forEach(function (row, i) {
        row.querySelectorAll("input, select, textarea, label").forEach(function (el) {
          ["name", "id", "for"].forEach(function (attr) {
            var v = el.getAttribute(attr);
            if (v) el.setAttribute(attr, v.replace(new RegExp(prefix + "-\\d+-"), prefix + "-" + i + "-"));
          });
        });
      });
      if (totalInput) totalInput.value = String(rows.length);
    }

    refreshEmpty();
  });

  // ── Unsaved-changes hint ────────────────────────────────
  root.querySelectorAll("form").forEach(function (form) {
    var bar = form.querySelector("[data-save-bar]");
    var hint = form.querySelector("[data-save-hint]");
    if (!bar || !hint || hint.textContent.trim() === "") return;
    var touch = function () {
      bar.classList.add("is-dirty");
      hint.textContent = "Unsaved changes";
    };
    form.addEventListener("input", touch);
    form.addEventListener("change", touch);
    form.addEventListener("submit", function () { bar.classList.remove("is-dirty"); });
  });

  show(root.getAttribute("data-active-tab") || "pricing", false);
})();
