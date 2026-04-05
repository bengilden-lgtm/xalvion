export function createSessionStore(initial = {}) {
  let state = {
    token: "",
    username: "",
    tier: "free",
    usage: 0,
    limit: 12,
    remaining: 12,
    usagePct: 0,
    approachingLimit: false,
    atLimit: false,
    valueSignals: null,
    ...initial,
  };
  const listeners = new Set();

  return {
    get: () => ({ ...state }),
    set(patch) {
      const next = { ...state, ...patch };
      state = next;
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
