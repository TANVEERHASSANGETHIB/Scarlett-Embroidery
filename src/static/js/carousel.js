/* Horizontal carousel: native scroll-snap for touch, buttons and dots for the rest. */
(function () {
  "use strict";

  document.querySelectorAll("[data-carousel]").forEach(function (root) {
    var track = root.querySelector("[data-track]");
    var nav = root.querySelector("[data-nav]");
    var prev = root.querySelector("[data-prev]");
    var next = root.querySelector("[data-next]");
    var dotsBox = root.querySelector("[data-dots]");
    if (!track || !nav) return;

    var items = Array.prototype.slice.call(track.children);
    var dots = [];
    var delay = parseInt(root.getAttribute("data-autoplay"), 10) || 0;
    var calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var timer = null;

    function perView() {
      if (!items.length) return 1;
      var step = items[0].offsetWidth + gap();
      return Math.max(1, Math.round(track.clientWidth / step));
    }

    function gap() {
      var value = parseFloat(getComputedStyle(track).columnGap || getComputedStyle(track).gap || "0");
      return isNaN(value) ? 0 : value;
    }

    function pageCount() {
      return Math.max(1, Math.ceil(items.length / perView()));
    }

    function currentPage() {
      var step = track.clientWidth;
      return step ? Math.round(track.scrollLeft / step) : 0;
    }

    function buildDots() {
      dotsBox.innerHTML = "";
      dots = [];
      for (var i = 0; i < pageCount(); i++) {
        var dot = document.createElement("button");
        dot.type = "button";
        dot.className = "carousel-dot";
        dot.setAttribute("aria-label", "Go to review page " + (i + 1));
          dot.addEventListener("click", function (page) {
          goTo(page);
          restart();
        }.bind(null, i));
        dotsBox.appendChild(dot);
        dots.push(dot);
      }
    }

    function goTo(page) {
      track.scrollTo({ left: page * track.clientWidth, behavior: "smooth" });
    }

    function sync() {
      // One screenful of cards fits everything: no controls needed.
      var needed = items.length > perView();
      nav.hidden = !needed;
      if (!needed) return;

      if (dots.length !== pageCount()) buildDots();
      var page = currentPage();
      dots.forEach(function (dot, i) {
        dot.classList.toggle("is-active", i === page);
        dot.setAttribute("aria-current", i === page ? "true" : "false");
      });
      prev.disabled = track.scrollLeft <= 2;
      next.disabled = track.scrollLeft + track.clientWidth >= track.scrollWidth - 2;
    }

    // ── Auto-scroll ───────────────────────────────────────
    function atEnd() {
      return track.scrollLeft + track.clientWidth >= track.scrollWidth - 2;
    }

    function advance() {
      if (atEnd()) {
        track.scrollTo({ left: 0, behavior: "smooth" });  // back round to the first
      } else {
        track.scrollBy({ left: track.clientWidth, behavior: "smooth" });
      }
    }

    function play() {
      if (!delay || calm || nav.hidden || timer) return;
      timer = window.setInterval(advance, delay);
    }

    function pause() {
      window.clearInterval(timer);
      timer = null;
    }

    function restart() {
      pause();
      play();
    }

    // Stop while someone is reading, hovering, or has the tab in the background.
    root.addEventListener("mouseenter", pause);
    root.addEventListener("mouseleave", play);
    root.addEventListener("focusin", pause);
    root.addEventListener("focusout", play);
    track.addEventListener("pointerdown", pause);
    track.addEventListener("touchstart", pause, { passive: true });
    track.addEventListener("touchend", function () { window.setTimeout(play, 1500); }, { passive: true });
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) pause(); else play();
    });

    prev.addEventListener("click", function () {
      track.scrollBy({ left: -track.clientWidth, behavior: "smooth" });
      restart();  // give them a full interval before it moves on its own
    });
    next.addEventListener("click", function () {
      advance();
      restart();
    });
    track.addEventListener("keydown", function (e) {
      if (e.key === "ArrowRight") { e.preventDefault(); next.click(); }
      if (e.key === "ArrowLeft") { e.preventDefault(); prev.click(); }
    });

    var ticking;
    track.addEventListener("scroll", function () {
      window.clearTimeout(ticking);
      ticking = window.setTimeout(sync, 80);
    });
    window.addEventListener("resize", function () {
      window.clearTimeout(ticking);
      ticking = window.setTimeout(sync, 120);
    });

    sync();
    play();
  });
})();
