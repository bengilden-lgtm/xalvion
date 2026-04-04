/**
 * Chrome extension tab context — used by sidepanel for active tab access.
 */

export function createChromeContext(chromeApi = typeof chrome !== "undefined" ? chrome : null) {
  if (!chromeApi?.tabs) {
    return {
      getActiveTab: async () => null,
      queryTabs: async () => [],
    };
  }

  return {
    async getActiveTab() {
      const tabs = await chromeApi.tabs.query({ active: true, currentWindow: true });
      return tabs[0] || null;
    },
    async queryTabs(query) {
      return chromeApi.tabs.query(query || {});
    },
  };
}
