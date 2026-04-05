/**
 * UI-facing state: status, reply editing, explainability toggle, loading.
 * Framework-free; does not touch the DOM.
 */

const initialState = {
  statusMessage: "",
  statusIsError: false,
  loading: false,
  explainabilityOpen: false,
  replyEditing: false,
  lastReply: "",
  replySnapshotBeforeEdit: "",
};

let state = { ...initialState };
const listeners = new Set();

function notify() {
  for (const fn of listeners) {
    try {
      fn(state);
    } catch (err) {
      console.error("[ui-store] listener error", err);
    }
  }
}

function getState() {
  return state;
}

function setState(partialOrUpdater) {
  const next =
    typeof partialOrUpdater === "function"
      ? partialOrUpdater(state)
      : { ...state, ...partialOrUpdater };
  state = next;
  notify();
}

function subscribe(listener) {
  if (typeof listener !== "function") return () => {};
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export const uiStore = { getState, setState, subscribe };
