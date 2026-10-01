(function () {
  "use strict";

  var form = document.querySelector("[data-order-form]");
  var dataEl = document.getElementById("pricing-data");
  if (!form || !dataEl) return;

  var pricing = JSON.parse(dataEl.textContent);
  var money = function (n) { return "$" + n.toFixed(2); };
  var byId = function (list, id) {
    for (var i = 0; i < list.length; i++) if (String(list[i].id) === String(id)) return list[i];
    return null;
  };
  var checked = function (name) {
    var el = form.querySelector('input[name="' + name + '"]:checked');
    return el ? el.value : "";
  };
  var value = function (name) {
    var el = form.querySelector('[name="' + name + '"]');
    return el ? el.value : "";
  };
  var setText = function (key, text) {
    var el = document.querySelector('[data-summary="' + key + '"]');
    if (el) el.textContent = text;
  };
  var setRowVisible = function (key, visible) {
    var el = document.querySelector('[data-summary-row="' + key + '"]');
    if (el) el.hidden = !visible;
  };

  function applyService(service) {
    form.querySelectorAll("[data-service-only]").forEach(function (el) {
      var services = el.getAttribute("data-service-only").split(" ");
      var show = services.indexOf(service) !== -1;
      el.style.display = show ? "" : "none";
      // Disable hidden inputs so the browser doesn't validate them
      el.querySelectorAll("input, select, textarea").forEach(function (input) {
        if (!show) {
          if (!input.disabled) input.setAttribute("data-auto-disabled", "1");
          input.disabled = true;
        } else if (input.getAttribute("data-auto-disabled")) {
          input.disabled = false;
          input.removeAttribute("data-auto-disabled");
        }
      });
    });
    // Only show tiers belonging to the selected service
    form.querySelectorAll("[data-tier-service]").forEach(function (label) {
      var match = label.getAttribute("data-tier-service") === service;
      label.style.display = match ? "" : "none";
      var input = label.querySelector("input");
      if (!match && input.checked) input.checked = false;
    });
    if (service !== "patches" && !checked("tier")) {
      var first = form.querySelector('[data-tier-service="' + service + '"] input');
      if (first) first.checked = true;
    }
  }

  function selectedFormats(service) {
    var name = service === "vector" ? "vector_formats" : "embroidery_formats";
    return Array.prototype.map.call(form.querySelectorAll('input[name="' + name + '"]:checked'), function (i) {
      return i.value;
    });
  }

  function update() {
    var service = checked("service") || "digitizing";
    var serviceLabel = form.querySelector('input[name="service"]:checked');
    setText("service", serviceLabel ? serviceLabel.getAttribute("data-label") : service);

    var isPatch = service === "patches";
    ["tier", "turnaround", "fabric", "placement", "formats"].forEach(function (k) { setRowVisible(k, !isPatch); });
    ["category", "quantity", "backing", "ship"].forEach(function (k) { setRowVisible(k, isPatch); });
    setRowVisible("fabric", service === "digitizing");
    setRowVisible("placement", service === "digitizing");

    var estimate = null;
    var note = "Final price confirmed after we review the artwork. No charge if you don't approve the proof.";

    if (isPatch) {
      var cat = byId(pricing.patchCategories, checked("patch-category"));
      var qty = parseInt(value("patch-quantity"), 10) || 0;
      var backing = form.querySelector('input[name="patch-backing"]:checked');
      setText("category", cat ? cat.name : "—");
      setText("quantity", qty ? qty + " pcs · " + (value("patch-width_in") || "?") + " × " + (value("patch-height_in") || "?") + " in" : "—");
      setText("backing", backing ? backing.getAttribute("data-label") : "—");
      var city = value("patch-city");
      setText("ship", city ? city + (value("patch-country") ? ", " + value("patch-country") : "") : "—");
      if (cat && qty) estimate = parseFloat(cat.unitPrice) * qty;
      note = "Starting price per piece × quantity. Final quote depends on size and detail.";
    } else {
      var tier = byId(pricing.tiers, checked("tier"));
      var ta = byId(pricing.turnarounds, checked("turnaround"));
      setText("tier", tier ? tier.name + " · $" + parseFloat(tier.price).toFixed(0) : "—");
      setText("turnaround", ta ? ta.name + (parseFloat(ta.surcharge) > 0 ? " (+$" + parseFloat(ta.surcharge).toFixed(0) + ")" : "") : "—");
      var size = value("height_in") && value("width_in") ? " · " + value("height_in") + " × " + value("width_in") + " in" : "";
      setText("fabric", value("fabric") || "—");
      setText("placement", (value("placement") || "—") + size);
      var fmts = selectedFormats(service);
      setText("formats", fmts.length ? fmts.join(", ") : "—");
      if (tier) estimate = parseFloat(tier.price) + (ta ? parseFloat(ta.surcharge) : 0);
    }

    setText("estimate", estimate === null ? "—" : money(estimate));
    setText("note", note);
  }

  form.querySelectorAll('input[name="service"]').forEach(function (input) {
    input.addEventListener("change", function () { applyService(input.value); update(); });
  });
  form.addEventListener("change", update);
  form.addEventListener("input", update);

  applyService(checked("service") || "digitizing");
  update();
})();

/* Sign-in gate: shown when a visitor submits an order before signing in. */
(function () {
  "use strict";

  var gate = document.querySelector("[data-login-gate]");
  if (!gate) return;

  var card = gate.querySelector(".gate-card");
  var lastFocus = null;

  function close() {
    gate.hidden = true;
    document.body.style.overflow = "";
    if (lastFocus) lastFocus.focus();
  }

  function open() {
    lastFocus = document.activeElement;
    gate.hidden = false;
    document.body.style.overflow = "hidden";
    if (card) card.focus();
  }

  gate.querySelectorAll("[data-gate-close]").forEach(function (b) {
    b.addEventListener("click", close);
  });
  gate.addEventListener("click", function (e) {
    if (e.target === gate) close();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !gate.hidden) close();
  });

  // Keep tabbing inside the dialog while it is open.
  document.addEventListener("keydown", function (e) {
    if (gate.hidden || e.key !== "Tab" || !card) return;
    var focusable = card.querySelectorAll("a[href], button:not([disabled])");
    if (!focusable.length) return;
    var first = focusable[0];
    var last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  });

  if (!gate.hidden) open();
})();

/* Removing a file that was saved with a guest draft. */
(function () {
  "use strict";

  var form = document.getElementById("remove-saved-form");
  if (!form) return;
  document.querySelectorAll("[data-remove-saved]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      form.action = btn.getAttribute("data-remove-saved");
      form.submit();
    });
  });
})();
