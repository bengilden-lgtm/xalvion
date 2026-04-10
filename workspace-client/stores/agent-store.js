export function createAgentStore() {
  let state = {
    currentState: "idle",
    currentResult: null,
    thinkingTrace: [],
    currentDecision: null,
    lastError: null,
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
