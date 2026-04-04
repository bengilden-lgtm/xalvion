export function createRefundStore() {
  let state = {
    modalOpen: false,
    history: [],
    stripeConnected: false,
    stripeAccountId: "",
    stripeMode: "",
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
