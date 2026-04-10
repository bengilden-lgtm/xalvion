/**
 * Gmail compose / reply insertion via chrome.scripting (active tab).
 * Injected function must stay self-contained — no closure captures from the extension world.
 *
 * Reliability notes:
 * - Compose surfaces often live in iframes; selection / execCommand must use composer.ownerDocument.
 * - Multiple textboxes may exist; we score candidates (visibility, labels, focus) and pick best.
 */

export async function insertIntoGmail(tabId, text, chromeApi = typeof chrome !== "undefined" ? chrome : null) {
  if (!chromeApi?.scripting) {
    return {
      ok: false,
      code: "no_scripting",
      detail: "Couldn’t reach Gmail from this extension. Try again after focusing the tab.",
    };
  }

  const [res] = await chromeApi.scripting.executeScript({
    target: { tabId },
    args: [text],
    func: async (reply) => {
      const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

      const FAIL_NO_COMPOSE =
        "Couldn’t find an active reply box. Open Reply or Compose in Gmail, click in the message body, then try again.";
      const FAIL_DISCONNECTED =
        "That compose window closed before we could finish. Open the reply again, then try Insert once more.";

      function collectDocuments(root, depth = 0, maxDepth = 5) {
        const out = [];
        if (!root) return out;
        out.push(root);
        if (depth >= maxDepth) return out;
        const frames = root.querySelectorAll ? root.querySelectorAll("iframe,frame") : [];
        for (let i = 0; i < frames.length; i += 1) {
          try {
            const doc = frames[i].contentDocument;
            if (doc) out.push(...collectDocuments(doc, depth + 1, maxDepth));
          } catch (_) {
            /* cross-origin */
          }
        }
        return out;
      }

      function getDeepActiveElement(startDoc) {
        const doc = startDoc;
        let el = doc && doc.activeElement;
        for (let guard = 0; guard < 12 && el; guard += 1) {
          const tag = (el.tagName || "").toUpperCase();
          if (tag === "IFRAME" || tag === "FRAME") {
            try {
              const inner = el.contentDocument;
              const innerActive = inner && inner.activeElement;
              if (inner && innerActive) {
                el = innerActive;
                continue;
              }
            } catch (_) {
              return el;
            }
          }
          return el;
        }
        return el;
      }

      function isSearchOrChromeField(el) {
        const al = String(el.getAttribute("aria-label") || "").toLowerCase();
        const id = String(el.id || "").toLowerCase();
        if (al.includes("search")) return true;
        if (id.includes("search")) return true;
        return false;
      }

      function isProbablyVisible(el) {
        if (!el || !el.isConnected) return false;
        const win = el.ownerDocument?.defaultView;
        if (!win) return false;
        let cur = el;
        while (cur && cur !== el.ownerDocument) {
          const st = win.getComputedStyle(cur);
          if (st.display === "none" || st.visibility === "hidden" || Number(st.opacity) === 0) return false;
          cur = cur.parentElement;
        }
        const r = el.getBoundingClientRect();
        return r.width >= 2 && r.height >= 2;
      }

      function scoreComposer(el, deepActive) {
        if (!el || el.getAttribute("contenteditable") === "false") return -1e9;
        if (isSearchOrChromeField(el)) return -1e9;

        let score = 0;
        const al = String(el.getAttribute("aria-label") || "").toLowerCase();
        if (al.includes("message body")) score += 220;
        if (al.includes("compose")) score += 40;
        if (el.getAttribute("g_editable") === "true") score += 100;
        if (el.getAttribute("role") === "textbox") score += 50;

        if (isProbablyVisible(el)) score += 80;

        if (deepActive) {
          if (el === deepActive) score += 200;
          else if (el.contains(deepActive)) score += 160;
        }

        const r = el.getBoundingClientRect();
        const area = Math.max(0, r.width) * Math.max(0, r.height);
        score += Math.min(120, Math.log10(area + 10) * 25);

        return score;
      }

      function listComposerCandidates(doc) {
        if (!doc || !doc.querySelectorAll) return [];
        const selectors = [
          'div[aria-label="Message Body"]',
          'div[aria-label^="Message Body"]',
          'div[aria-label*="Message Body"]',
          'div[role="textbox"][g_editable="true"]',
          'div[contenteditable="true"][role="textbox"]',
          'div[contenteditable="true"][aria-label*="Message Body"]',
          'div[contenteditable="true"][aria-label*="Compose"]',
        ];
        const seen = new Set();
        const out = [];
        for (let s = 0; s < selectors.length; s += 1) {
          doc.querySelectorAll(selectors[s]).forEach((el) => {
            if (!seen.has(el)) {
              seen.add(el);
              out.push(el);
            }
          });
        }
        doc.querySelectorAll('div[contenteditable="true"]').forEach((el) => {
          if (!seen.has(el)) {
            seen.add(el);
            out.push(el);
          }
        });
        return out;
      }

      function pickBestComposer() {
        const topDoc = document;
        const deepActive = getDeepActiveElement(topDoc);
        const docs = collectDocuments(topDoc);
        let best = null;
        let bestScore = -1e10;

        for (let d = 0; d < docs.length; d += 1) {
          const doc = docs[d];
          const docActive = doc === topDoc ? deepActive : getDeepActiveElement(doc);
          const candidates = listComposerCandidates(doc);
          for (let i = 0; i < candidates.length; i += 1) {
            const el = candidates[i];
            const sc = scoreComposer(el, docActive);
            if (sc > bestScore) {
              bestScore = sc;
              best = el;
            }
          }
        }

        if (!best || bestScore < -1e8) return null;
        return best;
      }

      function insertTextIntoComposer(composer, value) {
        if (!composer || !composer.isConnected) {
          return { ok: false, code: "compose_disconnected", detail: FAIL_DISCONNECTED };
        }

        const doc = composer.ownerDocument || document;
        const win = doc.defaultView || window;

        try {
          composer.scrollIntoView({ block: "nearest", inline: "nearest" });
        } catch (_) {}

        try {
          composer.focus();
        } catch (_) {}

        try {
          composer.click();
        } catch (_) {}

        try {
          const selection = win.getSelection && win.getSelection();
          if (selection && doc.createRange) {
            const range = doc.createRange();
            range.selectNodeContents(composer);
            range.collapse(true);
            selection.removeAllRanges();
            selection.addRange(range);
          }
        } catch (_) {}

        let inserted = false;

        try {
          inserted = doc.execCommand && doc.execCommand("insertText", false, value);
        } catch (_) {}

        if (!inserted) {
          try {
            composer.innerHTML = "";
          } catch (_) {}

          try {
            composer.textContent = value;
          } catch (_) {}
        }

        const InputEventCtor = win.InputEvent || InputEvent;
        try {
          composer.dispatchEvent(
            new InputEventCtor("input", {
              bubbles: true,
              cancelable: true,
              inputType: "insertText",
              data: value,
            })
          );
        } catch (_) {
          try {
            composer.dispatchEvent(new win.Event("input", { bubbles: true }));
          } catch (_) {}
        }

        try {
          composer.dispatchEvent(new win.Event("change", { bubbles: true }));
        } catch (_) {}

        if (!composer.isConnected) {
          return { ok: false, code: "compose_disconnected", detail: FAIL_DISCONNECTED };
        }

        return { ok: true };
      }

      function findReplyButton() {
        const selectors = [
          'div[role="button"][aria-label="Reply"]',
          'div[role="button"][aria-label^="Reply"]',
          'span[role="button"][aria-label="Reply"]',
          'span[role="button"][aria-label^="Reply"]',
          '[data-tooltip="Reply"]',
        ];

        for (let i = 0; i < selectors.length; i += 1) {
          const found = document.querySelector(selectors[i]);
          if (found && found.isConnected) return found;
        }

        const roleButtons = Array.from(document.querySelectorAll('[role="button"], [role="link"], button, span'));
        return (
          roleButtons.find((el) => {
            const aria = (el.getAttribute("aria-label") || "").trim().toLowerCase();
            const t = (el.textContent || "").trim().toLowerCase();
            const tooltip = (el.getAttribute("data-tooltip") || "").trim().toLowerCase();

            return (
              aria === "reply" ||
              aria.startsWith("reply") ||
              tooltip === "reply" ||
              t === "reply"
            );
          }) || null
        );
      }

      function findComposeButton() {
        return (
          document.querySelector('div[role="button"][gh="cm"]') ||
          document.querySelector('div[role="button"][aria-label="Compose"]') ||
          document.querySelector('div[role="button"][aria-label^="Compose"]') ||
          document.querySelector('[aria-label="Compose"]') ||
          document.querySelector('[aria-label^="Compose"]')
        );
      }

      let composer = pickBestComposer();

      if (!composer) {
        const replyButton = findReplyButton();

        if (replyButton) {
          try {
            replyButton.click();
          } catch (_) {
            try {
              replyButton.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
            } catch (_) {}
          }

          for (let i = 0; i < 14; i += 1) {
            await wait(i < 4 ? 120 : 220);
            composer = pickBestComposer();
            if (composer) break;
          }
        }
      }

      if (!composer) {
        const composeButton = findComposeButton();

        if (composeButton) {
          try {
            composeButton.click();
          } catch (_) {
            try {
              composeButton.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
            } catch (_) {}
          }

          for (let i = 0; i < 16; i += 1) {
            await wait(i < 4 ? 140 : 260);
            composer = pickBestComposer();
            if (composer) break;
          }
        }
      }

      if (!composer || !composer.isConnected) {
        return { ok: false, code: "no_compose", detail: FAIL_NO_COMPOSE };
      }

      const ins = insertTextIntoComposer(composer, reply);
      if (!ins.ok) return ins;

      try {
        composer.scrollIntoView({ block: "nearest", inline: "nearest" });
      } catch (_) {}

      return { ok: true };
    },
  });

  return (
    res?.result || {
      ok: false,
      code: "unknown",
      detail: "Insert didn’t finish. Copy the reply and paste it into Gmail manually.",
    }
  );
}
