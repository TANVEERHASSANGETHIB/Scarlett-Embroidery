/* Console appearance toggle: flips the theme at once, then saves the choice. */
(function () {
  "use strict";

  var form = document.querySelector("[data-theme-form]");
  if (!form) return;

  var toggle = form.querySelector("[data-theme-toggle]");
  var input = form.querySelector("[data-theme-input]");
  var text = form.querySelector("[data-theme-text]");
  if (!toggle || !input) return;

  function paint(theme) {
    var light = theme === "light";
    document.body.setAttribute("data-theme", theme);
    toggle.setAttribute("aria-checked", light ? "true" : "false");
    if (text) text.textContent = light ? "Light mode" : "Dark mode";
    // What a no-JS submit would send next, and what we post below.
    input.value = light ? "dark" : "light";
  }

  toggle.addEventListener("click", function (e) {
    var next = document.body.getAttribute("data-theme") === "light" ? "dark" : "light";
    if (!window.fetch) return; // no fetch: let the form post and reload

    e.preventDefault();
    paint(next);

    var body = new FormData(form);
    body.set("theme", next);
    fetch(form.action, {
      method: "POST",
      body: body,
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" },
    }).catch(function () {
      // Saving failed (offline?); the page still shows the chosen theme and
      // the next full load falls back to the stored preference.
    });
  });
})();
