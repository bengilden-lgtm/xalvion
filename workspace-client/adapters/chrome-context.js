/**
 * Chrome extension context: tabs, scripting. Safe no-op outside extension.
 */

export function createChromeContext(chromeApi = typeof chrome !== "undefined" ? chrome : null) {
  if (!chromeApi?.tabs) {
    return {
      queryTabs: null,
      executeScript: null,
      insertReply: async () => ({ ok: false, reason: "not_extension" }),
    };
  }

  return {
    queryTabs: (query) =>
      new Promise((resolve, reject) => {
        try {
          chromeApi.tabs.query(query || {}, (tabs) => {
            const err = chromeApi.runtime?.lastError;
            if (err) reject(new Error(err.message));
            else resolve(tabs || []);
          });
        } catch (e) {
          reject(e);
        }
      }),

    executeScript: (tabId, details) =>
      new Promise((resolve, reject) => {
        try {
          chromeApi.scripting.executeScript(
            { target: { tabId }, ...details },
            (results) => {
              const err = chromeApi.runtime?.lastError;
              if (err) reject(new Error(err.message));
              else resolve(results);
            }
          );
        } catch (e) {
          reject(e);
        }
      }),

    async insertReply(tabId, text) {
      if (!text) return { ok: false, reason: "empty" };
      try {
        await this.executeScript(tabId, {
          func: (reply) => {
            const el =
              document.querySelector('[role="textbox"][contenteditable="true"]') ||
              document.querySelector("textarea") ||
              document.querySelector('[g_editable="true"]');
            if (el) {
              if (el.tagName === "TEXTAREA") {
                el.value = reply;
                el.dispatchEvent(new Event("input", { bubbles: true }));
              } else {
                el.textContent = reply;
              }
              return true;
            }
            return false;
          },
          args: [text],
        });
        return { ok: true };
      } catch (e) {
        return { ok: false, reason: e?.message || "insert_failed" };
      }
    },
  };
}
