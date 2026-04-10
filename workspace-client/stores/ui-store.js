export function createUiStore() {
  let state = {
    notices: [],
    modalOpen: null,
    stickToBottom: true,
    operatorBriefExpanded: false,
    editMode: false,
    currentView: "workspace",
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
