(() => {
  const root = document.querySelector("[data-lightbox-root]");
  if (!root) return;
  const img = root.querySelector("[data-lightbox-img]");
  const cap = root.querySelector("[data-lightbox-cap]");
  let opener = null;

  const open = (trigger) => {
    opener = trigger;
    img.src = trigger.dataset.lightbox;
    cap.textContent = trigger.dataset.caption || "";
    root.hidden = false;
    document.body.style.overflow = "hidden";
    root.querySelector("[data-lightbox-close]").focus();
  };
  const close = () => {
    root.hidden = true;
    img.removeAttribute("src");
    document.body.style.overflow = "";
    if (opener) opener.focus();
  };

  document.addEventListener("click", (e) => {
    const t = e.target.closest("[data-lightbox]");
    if (t) return open(t);
    if (!root.hidden && (e.target === root || e.target.closest("[data-lightbox-close]"))) close();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !root.hidden) close();
  });
})();
