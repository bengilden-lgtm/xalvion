export function createCrmStore() {
  let state = {
    leads: [],
    followups: [],
    dailySummary: null,
    revenueMetrics: null,
    loaded: false,
  };
  const listeners = new Set();

  return {
    get: () => ({ ...state }),
    set(patch) {
      state = { ...state, ...patch };
      listeners.forEach((fn) => {
        try {
          fn(state);
        } catch {
          /* no-op */
        }
      });
    },
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
  };
}
