/**
 * Stripe/refund orchestration hooks — app.js remains source of truth for live wiring.
 */

export function createStripeEngine({ refundStore, apiClient } = {}) {
  return {
    syncFromWorkspace(patch) {
      refundStore?.set?.(patch);
    },
    async executeRefund(_payload) {
      if (!apiClient?.post) throw new Error("API client unavailable");
      /* Caller supplies path/body from app.js */
    },
  };
}
