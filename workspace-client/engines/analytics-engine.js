/**
 * Right-rail analytics and upgrade value copy — DOM side effects with no app state ownership.
 */

function setText(el, text) {
  if (el) el.textContent = String(text ?? "");
}

function formatMoneyDefault(n) {
  const x = Number(n || 0);
  return `$${Number.isFinite(x) ? x.toFixed(0) : "0"}`;
}

function formatMoneyRail(n) {
  const x = Number(n || 0);
  return `$${Number.isFinite(x) ? x.toFixed(2) : "0.00"}`;
}

export function createAnalyticsEngine({ sessionStore } = {}) {
  function estimateMinutes(d = {}, actionsCount = 0) {
    const actions = Number(d.actions ?? actionsCount ?? 0);
    const auto = Number(d.auto_resolved ?? 0);
    return Math.round(actions * 6 + auto * 2);
  }

  return {
    syncValueRail(els, dashboardSummary = {}) {
      const vg = dashboardSummary.value_generated || {};
      const money = Number(vg.money_saved ?? dashboardSummary.money_saved ?? 0);
      const mins = Number(vg.time_saved_minutes ?? 0);
      const actions = Number(vg.actions_taken ?? dashboardSummary.actions ?? 0);

      if (els.railValueMoney) setText(els.railValueMoney, formatMoneyRail(money));
      if (els.railValueTime) setText(els.railValueTime, mins > 0 ? `~${mins} min` : "—");
      if (els.railValueActions) setText(els.railValueActions, String(actions));

      const sess = sessionStore?.get?.() || {};
      if (els.railSessionTier) {
        const t = String(sess.tier || dashboardSummary.your_tier || "free").toUpperCase();
        setText(els.railSessionTier, t);
      }
    },

    estimateAgentMinutesSavedFromDashboard: estimateMinutes,

    /**
     * Mirrors app.js refreshUpgradeValueSummary when formatters match the workspace runtime.
     */
    refreshUpgradeValueSummary(el, dashboardStats, runtime = {}, formatters = {}) {
      if (!el) return;
      const formatMoney = formatters.formatMoney || formatMoneyDefault;
      const d = dashboardStats || {};
      const vg = d.value_generated && typeof d.value_generated === "object" ? d.value_generated : null;
      const tickets = Number(d.total_tickets ?? d.total_interactions ?? runtime.totalInteractions ?? 0);
      const money = Number((vg && vg.money_saved) ?? d.money_saved ?? 0);
      const actions = Number((vg && vg.actions_taken) ?? d.actions ?? runtime.actionsCount ?? 0);
      const est = estimateMinutes(d, runtime.actionsCount ?? 0);
      const mins = Number((vg && vg.time_saved_minutes) ?? est);
      const tier = String(runtime.tier || "free").toLowerCase();
      const upgradeHint =
        tier === "free"
          ? " Pro: 500 tickets/month + live Stripe execution when connected."
          : tier === "pro"
            ? " Elite: 5k tickets/month + team-scale headroom."
            : "";
      const hasValue = tickets > 0 || money > 0 || actions > 0 || mins > 0;
      el.textContent = hasValue
        ? `Session impact: ${tickets} tickets · ${formatMoney(money)} in billing · ${actions} actions · ~${mins} min back.${upgradeHint}`
        : "";
      el.style.display = hasValue ? "block" : "none";
    },
  };
}
