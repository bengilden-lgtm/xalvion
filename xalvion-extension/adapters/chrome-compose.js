/**
 * Gmail compose / reply insertion via chrome.scripting (active tab).
 * Injected function must stay self-contained — no closure captures from the extension world.
 */

export async function insertIntoGmail(tabId, text, chromeApi = typeof chrome !== "undefined" ? chrome : null) {
  if (!chromeApi?.scripting) {
    return { ok: false, detail: "Chrome scripting API unavailable." };
  }

  const [res] = await chromeApi.scripting.executeScript({
    target: { tabId },
    args: [text],
    func: async (reply) => {
      const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

      function collectDocuments(root, depth = 0, maxDepth = 4) {
        const out = [root];
        if (depth >= maxDepth) return out;
        const frames = root.querySelectorAll("iframe");
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

      function getComposerFromDocument(doc) {
        if (!doc || !doc.querySelector) return null;
        const selectors = [
          'div[aria-label="Message Body"]',
          'div[aria-label^="Message Body"]',
          'div[aria-label*="Message Body"]',
          'div[role="textbox"][g_editable="true"]',
          'div[contenteditable="true"][role="textbox"]',
          'div[contenteditable="true"][aria-label*="Message Body"]',
          'div[contenteditable="true"][aria-label*="Compose"]',
        ];
        for (let s = 0; s < selectors.length; s += 1) {
          const el = doc.querySelector(selectors[s]);
          if (el && el.getAttribute("contenteditable") !== "false") return el;
        }
        const editable = doc.querySelector('div[contenteditable="true"]');
        if (editable && editable.getAttribute("contenteditable") !== "false") return editable;
        return null;
      }

      function getComposer() {
        const docs = collectDocuments(document);
        for (let d = 0; d < docs.length; d += 1) {
          const c = getComposerFromDocument(docs[d]);
          if (c) return c;
        }
        return null;
      }

      function findReplyButton() {
        const selectors = [
          'div[role="button"][aria-label="Reply"]',
          'div[role="button"][aria-label^="Reply"]',
          'span[role="button"][aria-label="Reply"]',
          'span[role="button"][aria-label^="Reply"]',
          '[data-tooltip="Reply"]',
          '[aria-label*="Reply"]',
        ];

        for (let i = 0; i < selectors.length; i += 1) {
          const found = document.querySelector(selectors[i]);
          if (found) return found;
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

      function insertTextIntoComposer(composer, value) {
        composer.focus();

        try {
          composer.click();
        } catch (_) {}

        try {
          if (document.getSelection) {
            const selection = document.getSelection();
            const range = document.createRange();
            range.selectNodeContents(composer);
            range.collapse(true);
            selection.removeAllRanges();
            selection.addRange(range);
          }
        } catch (_) {}

        let inserted = false;

        try {
          inserted = document.execCommand("insertText", false, value);
        } catch (_) {}

        if (!inserted) {
          try {
            composer.innerHTML = "";
          } catch (_) {}

          try {
            composer.textContent = value;
          } catch (_) {}
        }

        composer.dispatchEvent(
          new InputEvent("input", {
            bubbles: true,
            cancelable: true,
            inputType: "insertText",
            data: value,
          })
        );

        composer.dispatchEvent(new Event("change", { bubbles: true }));
      }

      let composer = getComposer();

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
            composer = getComposer();
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
            composer = getComposer();
            if (composer) break;
          }
        }
      }

      if (!composer) {
        return {
          ok: false,
          detail: "No Gmail compose field found — open Reply or Compose, click into the message body, then retry.",
        };
      }

      insertTextIntoComposer(composer, reply);

      try {
        composer.scrollIntoView({ block: "nearest", inline: "nearest" });
      } catch (_) {}

      return { ok: true };
    },
  });

  return res?.result || { ok: false, detail: "Insert failed." };
}
