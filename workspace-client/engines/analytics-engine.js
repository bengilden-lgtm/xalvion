/**
 * Right-rail analytics: syncs dashboard /metrics-style numbers into DOM when elements exist.
 */

function setText(el, text) {
  if (el) el.textContent = String(text ?? "");
}

function formatMoney(n) {
  const x = Number(n || 0);
  return `$${Number.isFinite(x) ? x.toFixed(2) : "0.00"}`;
}

export function createAnalyticsEngine({ sessionStore } = {}) {
  return {
    syncValueRail(els, dashboardSummary = {}) {
      const vg = dashboardSummary.value_generated || {};
      const money = Number(vg.money_saved ?? dashboardSummary.money_saved ?? 0);
      const mins = Number(vg.time_saved_minutes ?? 0);
      const actions = Number(vg.actions_taken ?? dashboardSummary.actions ?? 0);

      if (els.railValueMoney) setText(els.railValueMoney, formatMoney(money));
      if (els.railValueTime) setText(els.railValueTime, mins > 0 ? `~${mins} min` : "—");
      if (els.railValueActions) setText(els.railValueActions, String(actions));

      const sess = sessionStore?.get?.() || {};
      if (els.railSessionTier) {
        const t = String(sess.tier || dashboardSummary.your_tier || "free").toUpperCase();
        setText(els.railSessionTier, t);
      }
    },
  };
}
