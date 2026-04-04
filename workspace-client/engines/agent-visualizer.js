/**
 * Subscribes to agent-store for future incremental canvas updates; core rendering stays in app.js fallback.
 */

export function createAgentVisualizer({ agentStore } = {}) {
  let unsub = null;

  return {
    attach() {
      if (!agentStore?.subscribe) return () => {};
      unsub = agentStore.subscribe(() => {
        /* Reserved: Phase 4 keeps streaming DOM in app.js; store is synced from SSE. */
      });
      return () => {
        unsub?.();
        unsub = null;
      };
    },

    getState() {
      return agentStore?.get?.() || null;
    },
  };
}
