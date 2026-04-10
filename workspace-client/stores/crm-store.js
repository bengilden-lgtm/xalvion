export function createCrmStore(initial = {}) {
  let state = {
    leads: [],
    followups: [],
    dailySummary: null,
    revenueMetrics: null,
    summary: null,
    loaded: false,
    ...initial,
  };
  const listeners = new Set();

  return {
    get: () => ({ ...state }),
    getState: () => state,
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
    setState(patch) {
      this.set(patch);
    },
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
  };
}
