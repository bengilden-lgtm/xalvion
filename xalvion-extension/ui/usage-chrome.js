/**
 * Xalvion Extension — Usage chrome
 * Owner: xalvion-extension/ui
 *
 * Purpose:
 * - Keep quota/plan tier UI and upgrade panel behavior consistent across the extension.
 * - Designed for dependency injection: DOM nodes + usage-plan functions passed in by orchestrator.
 */

export function createUsageChrome(deps) {
  const {
    sessionStore,
    getUsageSnapshot,
    loadUsagePlan,
    enrollFreeTier,
    dismissSoftNudgeForPeriod,
    showStatus,
  } = deps;

  const els = deps.els || {};

  const usageReady = Promise.resolve()
    .then(() => loadUsagePlan())
    .then(() => {
      refreshUsageChrome();
      syncPrimaryRunButtons();
      bindUpgradePanel();
    });

  function currentPlanTier() {
    return sessionStore.getState().planTier;
  }

  function updateCapacityPillFromData(data) {
    if (!els.capPill) return;
    if (data?.meta && data.meta.plan_tier) {
      sessionStore.setState({ planTier: data.meta.plan_tier });
    }
    const snap = getUsageSnapshot(currentPlanTier());
    if (snap.hasProAccess) {
      const fromServer = data?.meta?.plan_tier;
      const label = fromServer ? String(fromServer).toUpperCase() : "PRO";
      els.capPill.textContent = `Extension · ${label}`;
      return;
    }
    els.capPill.textContent = `Extension · ${snap.totalOperatorRuns}/${snap.hardThreshold} operator runs`;
  }

  function refreshUsageChrome() {
    const snap = getUsageSnapshot(currentPlanTier());
    if (els.capPill) {
      if (snap.hasProAccess) {
        const t = currentPlanTier();
        els.capPill.textContent = t ? `Extension · ${String(t).toUpperCase()}` : "Extension · PRO";
      } else {
        els.capPill.textContent = `Extension · ${snap.totalOperatorRuns}/${snap.hardThreshold} operator runs`;
      }
    }

    if (!els.upgradeContextPanel) return;

    els.upgradeContextPanel.classList.remove("is-visible", "mode-soft", "mode-hard");

    if (snap.hasProAccess) {
      els.upgradeEnrollFreeBtn?.classList.add("is-hidden");
      els.upgradeDismissSoftBtn?.classList.add("is-hidden");
      if (els.upgradeContextSplit) els.upgradeContextSplit.textContent = "";
      return;
    }

    if (snap.hardLimited) {
      els.upgradeContextPanel.classList.add("is-visible", "mode-hard");
      if (els.upgradeContextEyebrow) els.upgradeContextEyebrow.textContent = "Quota — window limit";
      if (els.upgradeContextPrimary) {
        els.upgradeContextPrimary.textContent = `You've used ${snap.totalOperatorRuns} operator runs — this window is at capacity (${snap.hardThreshold}).`;
      }
      if (els.upgradeContextSecondary) {
        els.upgradeContextSecondary.textContent =
          "Upgrade for higher capacity and uninterrupted execution. Approval-safe automation continues on Pro. Your current reply stays available to copy or insert.";
      }
      if (els.upgradeContextSplit) {
        els.upgradeContextSplit.textContent = `Guest runs ${snap.guestUsageCount} · Free-tier runs ${snap.freeTierUsageCount}`;
      }
      els.upgradeDismissSoftBtn?.classList.add("is-hidden");
      els.upgradeEnrollFreeBtn?.classList.toggle("is-hidden", snap.freeTierEnrolled);
      return;
    }

    if (snap.showSoftNudge) {
      els.upgradeContextPanel.classList.add("is-visible", "mode-soft");
      if (els.upgradeContextEyebrow) els.upgradeContextEyebrow.textContent = "Capacity";
      if (els.upgradeContextPrimary) {
        els.upgradeContextPrimary.textContent = `You've used ${snap.totalOperatorRuns} operator runs.`;
      }
      if (els.upgradeContextSecondary) {
        els.upgradeContextSecondary.textContent =
          "Upgrade for higher capacity and uninterrupted execution. Approval-safe automation continues on Pro.";
      }
      if (els.upgradeContextSplit) {
        els.upgradeContextSplit.textContent = `Guest runs ${snap.guestUsageCount} · Free-tier runs ${snap.freeTierUsageCount}`;
      }
      els.upgradeDismissSoftBtn?.classList.remove("is-hidden");
      els.upgradeEnrollFreeBtn?.classList.toggle("is-hidden", snap.freeTierEnrolled);
      return;
    }

    if (els.upgradeContextSplit) els.upgradeContextSplit.textContent = "";
    els.upgradeEnrollFreeBtn?.classList.add("is-hidden");
    els.upgradeDismissSoftBtn?.classList.add("is-hidden");
  }

  function syncPrimaryRunButtons() {
    const loading = deps.uiStore.getState().loading;
    const snap = getUsageSnapshot(currentPlanTier());
    const block = snap.hardLimited && !snap.hasProAccess;
    const hint = "Operator quota exhausted for this period. Copy, insert, and review stay available.";
    if (els.analyzeBtn) {
      els.analyzeBtn.disabled = Boolean(loading || block);
      els.analyzeBtn.title = block ? hint : "";
    }
    if (els.scanInboxBtn) {
      els.scanInboxBtn.disabled = Boolean(loading || block);
      els.scanInboxBtn.title = block ? hint : "";
    }
  }

  function bindUpgradePanel() {
    if (els.upgradeEnrollFreeBtn && !els.upgradeEnrollFreeBtn.dataset.bound) {
      els.upgradeEnrollFreeBtn.dataset.bound = "1";
      els.upgradeEnrollFreeBtn.addEventListener("click", async () => {
        await enrollFreeTier();
        refreshUsageChrome();
        syncPrimaryRunButtons();
        showStatus("Free console enrolled — run counts continue on this device; quota resets on the rolling window.");
      });
    }
    if (els.upgradeDismissSoftBtn && !els.upgradeDismissSoftBtn.dataset.bound) {
      els.upgradeDismissSoftBtn.dataset.bound = "1";
      els.upgradeDismissSoftBtn.addEventListener("click", async () => {
        await dismissSoftNudgeForPeriod();
        refreshUsageChrome();
      });
    }
    if (els.upgradeProLink && !els.upgradeProLink.dataset.bound) {
      els.upgradeProLink.dataset.bound = "1";
      els.upgradeProLink.addEventListener("click", (e) => {
        e.preventDefault();
        showStatus("Pro routing can open your billing or workspace console when wired.");
      });
    }
  }

  async function ensureUsageReady() {
    await usageReady;
  }

  return {
    ensureUsageReady,
    refreshUsageChrome,
    syncPrimaryRunButtons,
    updateCapacityPillFromData,
  };
}

