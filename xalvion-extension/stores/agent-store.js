/**
 * Agent / decision run state for the side panel (framework-free).
 * Owns latest API payload and thinking-sequence cancellation id.
 */

const initialState = {
  latestPayload: null,
  thinkingRunId: 0,
};

let state = { ...initialState };
const listeners = new Set();

function notify() {
  for (const fn of listeners) {
    try {
      fn(state);
    } catch (err) {
      console.error("[agent-store] listener error", err);
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

export const agentStore = { getState, setState, subscribe };
