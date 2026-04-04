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
