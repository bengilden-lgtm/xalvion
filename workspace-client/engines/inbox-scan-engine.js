/**
 * Extension inbox scan sequencing — used from sidepanel when scan is initiated.
 */

export function createInboxScanEngine({ chromeContext } = {}) {
  return {
    async runScanSequence(tabsQuery) {
      const q = chromeContext?.queryTabs || tabsQuery;
      if (typeof q !== "function") return { ok: false, error: "no_tabs_api" };
      return q({});
    },
  };
}
