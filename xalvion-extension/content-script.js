/**
 * Gmail / helpdesk page context — single-init guard and optional isolation host.
 * Heavy lifting (read thread, insert reply) uses chrome.scripting from the popup; this script
 * stays lightweight to avoid observer loops or duplicate UI on SPA rerenders.
 */
(function xalvionContentScriptInit() {
  const w = typeof window !== "undefined" ? window : null;
  if (!w || w.__XALVION_CONTENT_INIT__) return;
  w.__XALVION_CONTENT_INIT__ = true;

  const HOST_ATTR = "data-xalvion-host";
  const HOST_ID = "xalvion-extension-host";

  function removeDuplicateHosts() {
    const nodes = document.querySelectorAll(`[${HOST_ATTR}="1"]`);
    for (let i = 1; i < nodes.length; i += 1) {
      try {
        nodes[i].remove();
      } catch (_) {}
    }
  }

  function ensureIsolationHost() {
    removeDuplicateHosts();
    let host = document.getElementById(HOST_ID);
    if (host && host.isConnected && host.getAttribute(HOST_ATTR) === "1") {
      return host;
    }
    if (host && !host.isConnected) {
      try {
        host.remove();
      } catch (_) {}
      host = null;
    }

    host = document.createElement("div");
    host.id = HOST_ID;
    host.setAttribute(HOST_ATTR, "1");
    host.setAttribute("aria-hidden", "true");
    host.setAttribute("data-extension", "xalvion");
    Object.assign(host.style, {
      all: "initial",
      position: "fixed",
      inset: "0",
      width: "0",
      height: "0",
      margin: "0",
      padding: "0",
      border: "none",
      overflow: "hidden",
      pointerEvents: "none",
      zIndex: "2147483646",
      visibility: "hidden",
    });

    const root = document.documentElement;
    if (root) root.appendChild(host);

    try {
      if (!host.shadowRoot) {
        const shadow = host.attachShadow({ mode: "closed" });
        const slot = document.createElement("div");
        slot.style.cssText = "display:block;width:0;height:0;overflow:hidden;";
        shadow.appendChild(slot);
      }
    } catch (_) {
      /* attachShadow unsupported — host still acts as a single sentinel node */
    }

    return host;
  }

  try {
    ensureIsolationHost();
  } catch (_) {}

  if (typeof console !== "undefined" && console.log) {
    console.log("Xalvion Assist content script initialized");
  }
})();
