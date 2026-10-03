/* Visual blog editor: a toolbar over a contenteditable area, with an HTML tab, like WordPress.
   Any <textarea data-rich-editor> is upgraded; its value stays the source of truth (HTML). */
(function () {
  "use strict";
  var area = document.querySelector("textarea[data-rich-editor]");
  if (!area) return;
  var form = area.closest("form");
  var token = form && form.querySelector("[name=csrfmiddlewaretoken]");
  var uploadUrl = area.getAttribute("data-upload-url");

  var wrap = document.createElement("div");
  wrap.className = "rte";
  wrap.innerHTML =
    '<div class="rte-bar" role="toolbar" aria-label="Formatting">' +
    '<select class="rte-block" aria-label="Paragraph style"><option value="p">Paragraph</option><option value="h2">Heading 2</option><option value="h3">Heading 3</option><option value="h4">Heading 4</option><option value="blockquote">Quote</option></select>' +
    btn("bold", "<b>B</b>", "Bold") + btn("italic", "<i>I</i>", "Italic") + btn("underline", "<u>U</u>", "Underline") +
    '<span class="rte-sep"></span>' +
    btn("insertUnorderedList", "• List", "Bulleted list") + btn("insertOrderedList", "1. List", "Numbered list") +
    btn("justifyLeft", "⟸", "Align left") + btn("justifyCenter", "≡", "Align centre") +
    '<span class="rte-sep"></span>' +
    btn("link", "Link", "Insert link") + btn("image", "Image", "Upload and insert an image") + btn("hr", "—", "Divider") + btn("clear", "Clear", "Clear formatting") +
    '<span class="rte-tabs"><button type="button" data-mode="visual" class="is-on">Visual</button><button type="button" data-mode="html">HTML</button></span>' +
    '<input type="file" accept="image/*" hidden class="rte-file"></div>' +
    '<div class="rte-surface" contenteditable="true" spellcheck="true" data-placeholder="Write the article… use the toolbar for headings, bold text and images."></div>' +
    '<div class="rte-status" aria-live="polite"></div>';
  function btn(cmd, label, title) {
    return '<button type="button" class="rte-btn" data-cmd="' + cmd + '" title="' + title + '" aria-label="' + title + '">' + label + "</button>";
  }
  area.parentNode.insertBefore(wrap, area);
  area.classList.add("rte-html");
  area.hidden = true;

  var surface = wrap.querySelector(".rte-surface");
  var status = wrap.querySelector(".rte-status");
  var fileInput = wrap.querySelector(".rte-file");
  var mode = "visual";
  surface.innerHTML = area.value;

  function sync() { if (mode === "visual") area.value = surface.innerHTML; }
  surface.addEventListener("input", sync);
  if (form) {
    form.addEventListener("formdata", function (e) { sync(); e.formData.set(area.name, area.value); });
  }
  function say(msg) { status.textContent = msg || ""; }

  function exec(cmd, val) { surface.focus(); document.execCommand(cmd, false, val || null); sync(); }
  var selection = null;
  function saveSel() { var s = window.getSelection(); if (s.rangeCount && surface.contains(s.anchorNode)) selection = s.getRangeAt(0); }
  function restoreSel() { if (!selection) return; var s = window.getSelection(); s.removeAllRanges(); s.addRange(selection); }
  surface.addEventListener("keyup", saveSel); surface.addEventListener("mouseup", saveSel);

  wrap.querySelector(".rte-block").addEventListener("change", function (e) {
    exec("formatBlock", e.target.value === "p" ? "p" : e.target.value);
  });

  wrap.querySelectorAll(".rte-btn").forEach(function (b) {
    b.addEventListener("mousedown", function (e) { e.preventDefault(); saveSel(); });
    b.addEventListener("click", function () {
      var cmd = b.getAttribute("data-cmd");
      if (mode !== "visual") return;
      surface.focus(); restoreSel();
      if (cmd === "link") {
        var url = window.prompt("Link address (https://…)", "https://");
        if (url && /^(https?:|mailto:|tel:|\/)/i.test(url)) exec("createLink", url);
      } else if (cmd === "image") {
        fileInput.click();
      } else if (cmd === "hr") {
        exec("insertHorizontalRule");
      } else if (cmd === "clear") {
        exec("removeFormat"); exec("formatBlock", "p");
      } else {
        exec(cmd);
      }
    });
  });

  fileInput.addEventListener("change", function () {
    var f = fileInput.files[0];
    if (!f) return;
    if (!uploadUrl) { say("Image upload is not available."); return; }
    var fd = new FormData(); fd.append("image", f);
    say("Uploading " + f.name + "…");
    fetch(uploadUrl, { method: "POST", body: fd, headers: { "X-CSRFToken": token ? token.value : "" }, credentials: "same-origin" })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!res.ok) { say(res.j.error || "Upload failed."); return; }
        surface.focus(); restoreSel();
        var alt = window.prompt("Describe the picture (alt text, helps search engines)", f.name.replace(/\.[^.]+$/, "")) || "";
        exec("insertHTML", '<figure><img src="' + res.j.url + '" alt="' + alt.replace(/"/g, "&quot;") + '"></figure><p><br></p>');
        say("Image inserted.");
      })
      .catch(function () { say("Upload failed. Check your connection."); })
      .then(function () { fileInput.value = ""; });
  });

  wrap.querySelectorAll(".rte-tabs button").forEach(function (t) {
    t.addEventListener("click", function () {
      var to = t.getAttribute("data-mode");
      if (to === mode) return;
      if (to === "html") { area.value = surface.innerHTML; area.hidden = false; surface.hidden = true; }
      else { surface.innerHTML = area.value; area.hidden = true; surface.hidden = false; }
      mode = to;
      wrap.classList.toggle("is-html", mode === "html");
      wrap.querySelectorAll(".rte-tabs button").forEach(function (o) { o.classList.toggle("is-on", o === t); });
      say(mode === "html" ? "HTML mode: paste or write your own markup. Scripts are removed when the post is shown." : "");
    });
  });
})();
