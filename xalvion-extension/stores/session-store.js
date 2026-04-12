/**
 * Session / plan surface for the extension chrome (capacity pill, tier hints).
 * Framework-free; values are updated when analyze responses include meta.
 */

const initialState = {
  planTier: null,
  /** Server-backed operator metering (null = unknown until first /analyze). */
  operatorUsage: null,
  operatorLimit: null,
  operatorRemaining: null,
  operatorAtLimit: false,
  operatorApproaching: false,
  usagePeriodAnchor: null,
};

let state = { ...initialState };
const listeners = new Set();

function notify() {
  for (const fn of listeners) {
    try {
      fn(state);
    } catch (err) {
      console.error("[session-store] listener error", err);
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

export const sessionStore = { getState, setState, subscribe };
