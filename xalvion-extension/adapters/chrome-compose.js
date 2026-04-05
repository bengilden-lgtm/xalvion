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

      function getComposer() {
        return (
          document.querySelector('div[aria-label="Message Body"]') ||
          document.querySelector('div[aria-label^="Message Body"]') ||
          document.querySelector('div[role="textbox"][g_editable="true"]') ||
          document.querySelector('div[contenteditable="true"][role="textbox"]') ||
          document.querySelector('div[contenteditable="true"][aria-label*="Message Body"]') ||
          document.querySelector('div[contenteditable="true"]')
        );
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

        for (const selector of selectors) {
          const found = document.querySelector(selector);
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
          document.querySelector('[aria-label="Compose"]')
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

          for (let i = 0; i < 8; i += 1) {
            await wait(250);
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

          for (let i = 0; i < 10; i += 1) {
            await wait(300);
            composer = getComposer();
            if (composer) break;
          }
        }
      }

      if (!composer) {
        return {
          ok: false,
          detail: "No Gmail reply composer found.",
        };
      }

      insertTextIntoComposer(composer, reply);

      return { ok: true };
    },
  });

  return res?.result || { ok: false, detail: "Insert failed." };
}
