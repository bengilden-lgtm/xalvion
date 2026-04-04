/**
 * Optional DOM bridge for agent-store; workspace keeps primary rendering in app.js fallback.
 */

export function createAgentVisualizer({ agentStore } = {}) {
  let unsub = null;

  return {
    attach() {
      if (!agentStore?.subscribe) return () => {};
      unsub = agentStore.subscribe(() => {
        /* Reserved: incremental canvas updates without replacing app.js flow */
      });
      return () => {
        unsub?.();
        unsub = null;
      };
    },
  };
}
