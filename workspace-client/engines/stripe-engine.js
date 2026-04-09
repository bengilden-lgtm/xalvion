/**
 * Stripe + refund center DOM — app.js remains authoritative for fetch / state; engine is render-only.
 */

function setText(el, value) {
  if (el) el.textContent = String(value ?? "");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function createStripeEngine({ refundStore, apiClient } = {}) {
  return {
    syncFromWorkspace(patch) {
      refundStore?.set?.(patch);
    },

    updateStripePanel(els, stripeState = {}) {
      const connected = Boolean(stripeState.stripeConnected);
      const state = {
        stripeConnected: connected,
        stripeAccountId: String(stripeState.stripeAccountId || ""),
        stripeMode: String(stripeState.stripeMode || ""),
      };

      if (els.stripeStatus) {
        els.stripeStatus.textContent = connected ? "Connected" : "Not connected";
        els.stripeStatus.classList.toggle("is-connected", connected);
      }

      if (els.stripeConnectBtn) {
        const label = els.stripeConnectBtn.querySelector(".stripe-connect-label");
        if (label) {
          label.textContent = connected ? "Reconnect Stripe" : "Connect Stripe";
        } else {
          els.stripeConnectBtn.textContent = connected ? "Reconnect Stripe" : "Connect Stripe";
        }
        els.stripeConnectBtn.disabled = false;
      }

      if (els.stripeDisconnectBtn) {
        els.stripeDisconnectBtn.hidden = !connected;
        els.stripeDisconnectBtn.disabled = !connected;
      }

      if (els.stripeAccountPill) {
        els.stripeAccountPill.textContent = connected && state.stripeAccountId ? state.stripeAccountId : "No account linked";
      }

      if (els.stripeModePill) {
        els.stripeModePill.textContent = connected ? state.stripeMode || "Connected" : "Awaiting connection";
      }

      if (els.stripeIntegrationCopy) {
        els.stripeIntegrationCopy.textContent = connected
          ? "Stripe is connected. Live refund execution is available for this workspace."
          : "Connect Stripe to execute refunds from the workspace (instead of preparing drafts only).";
      }

      this.syncFromWorkspace({
        stripeConnected: state.stripeConnected,
        stripeAccountId: state.stripeAccountId,
        stripeMode: state.stripeMode,
      });
    },

    updateRefundCenterPanel(els, ctx = {}, helpers = {}) {
      const { tier = "free", dashboardStats = null } = ctx;
      const { canUseRefundCenter, formatMoney, setText: st } = helpers;
      const setT = st || setText;
      const allowed = typeof canUseRefundCenter === "function" ? canUseRefundCenter() : false;

      if (els.refundTierAccess) {
        setT(els.refundTierAccess, allowed ? "Ready" : "");
      }

      if (els.refundCenterCard) {
        els.refundCenterCard.classList.toggle("refund-disabled", !allowed);
      }

      if (els.openRefundModalBtn) {
        els.openRefundModalBtn.disabled = !allowed;
        els.openRefundModalBtn.textContent = allowed ? "Open refunds" : "Upgrade to unlock";
      }

      if (els.executeRefundBtn) {
        els.executeRefundBtn.disabled = !allowed;
      }

      if (els.refundModalNote) {
        els.refundModalNote.textContent = allowed
          ? "Live refund execution is available on this plan. Use a PaymentIntent or Charge ID from Stripe."
          : "Live refund execution is locked on this plan. Upgrade to enable billing actions from the workspace.";
      }

      if (els.refundCenterCopy) {
        els.refundCenterCopy.textContent = allowed
          ? "Open the refund UI, paste a PaymentIntent or Charge ID, and run a refund from the workspace."
          : "Free shows decisions and approvals. Pro unlocks live Stripe refund execution without leaving the operator surface.";
      }

      if (els.refundUpgradeTease) {
        const d = dashboardStats || {};
        const vg = d.value_generated && typeof d.value_generated === "object" ? d.value_generated : null;
        const money = Number((vg && vg.money_saved) ?? d.money_saved ?? 0);
        const actions = Number((vg && vg.actions_taken) ?? d.actions ?? 0);
        const fm = formatMoney || ((n) => `$${Number.isFinite(Number(n)) ? Number(n).toFixed(0) : "0"}`);
        els.refundUpgradeTease.textContent = allowed
          ? "Execute refunds from the workspace · Available on Pro and Elite"
          : money > 0 || actions > 0
            ? `Your workspace already logged ${fm(money)} across ${actions} billing motions — Pro turns that into live Stripe execution here.`
            : "Close the loop on Free → Pro: execute refunds from the workspace with Stripe connected — no context switch.";
      }

    },

    refundStatusTone(status) {
      const value = String(status || "").toLowerCase();
      if (value.includes("refund") || value === "executed" || value === "succeeded" || value === "success") return "success";
      if (value.includes("fail") || value.includes("error") || value.includes("blocked")) return "error";
      return "pending";
    },

    formatRefundTimestamp(value) {
      if (!value) return "Just now";
      const parsed = new Date(value);
      if (Number.isNaN(parsed.getTime())) return String(value);
      return parsed.toLocaleString([], {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    },

    renderRefundHistory(els, logs = [], helpers = {}) {
      const { formatMoney, escapeHtml: esc, formatRefundTimestamp: fmtTs, refundStatusTone: toneFn, setText: st } = helpers;
      const setT = st || setText;
      const escHtml = esc || escapeHtml;
      const fm = formatMoney || ((n) => `$${Number.isFinite(Number(n)) ? Number(n).toFixed(0) : "0"}`);
      const fmt = fmtTs || ((v) => this.formatRefundTimestamp(v));
      const toneFor = toneFn || ((s) => this.refundStatusTone(s));

      const list = Array.isArray(logs) ? logs.slice() : [];

      if (els.refundHistoryCount) {
        setT(els.refundHistoryCount, String(list.length));
      }

      if (!els.refundHistoryList) {
        this.syncFromWorkspace({ history: list });
        return;
      }

      if (!list.length) {
        els.refundHistoryList.innerHTML =
          '<div class="refund-empty">No refund activity yet. Refunds will appear here with status and timestamp.</div>';
        this.syncFromWorkspace({ history: list });
        return;
      }

      els.refundHistoryList.innerHTML = list
        .map((log) => {
          const status = String(log.status || "pending");
          const tone = toneFor(status);
          const amount = Number(log.amount || 0);
          const title = amount > 0 ? `Refunded ${fm(amount)}` : "Refund activity";
          const reason = log.reason ? escHtml(log.reason) : "No reason provided";
          const timestamp = escHtml(fmt(log.timestamp));
          const username = log.username ? escHtml(log.username) : "workspace";
          return `
        <div class="refund-item">
          <div class="refund-item-head">
            <div class="refund-item-title">${escHtml(title)}</div>
            <div class="refund-pill ${tone}">${escHtml(status)}</div>
          </div>
          <div class="refund-item-meta">
            <span>${timestamp}</span>
            <span>·</span>
            <span>${username}</span>
          </div>
          <div class="refund-item-meta">
            <span>${reason}</span>
          </div>
        </div>
      `;
        })
        .join("");

      this.syncFromWorkspace({ history: list });
    },

    hydrateStripeCallbackState(win, { setNotice } = {}) {
      if (!win?.location?.href || typeof setNotice !== "function") return;
      try {
        const url = new URL(win.location.href);
        const stripe = url.searchParams.get("stripe");
        const detail = url.searchParams.get("detail");

        if (!stripe) return;

        if (stripe === "success" || stripe === "connected") {
          setNotice("success", "Stripe connected", detail || "Refund execution is now live for this workspace.");
        } else if (stripe === "cancel") {
          setNotice("warning", "Stripe connection canceled", detail || "Stripe was not connected.");
        } else if (stripe === "error" || stripe === "connect_error") {
          setNotice("error", "Stripe connection failed", detail || "Could not complete Stripe connection.");
        } else if (stripe === "disconnected") {
          setNotice("success", "Stripe disconnected", detail || "Stripe has been disconnected from this workspace.");
        }

        url.searchParams.delete("stripe");
        url.searchParams.delete("detail");
        win.history.replaceState(
          {},
          win.document?.title || "",
          url.pathname + (url.searchParams.toString() ? `?${url.searchParams.toString()}` : "") + url.hash
        );
      } catch {
        /* no-op */
      }
    },

    async executeRefund(_payload) {
      if (!apiClient?.post) throw new Error("API client unavailable");
    },
  };
}
