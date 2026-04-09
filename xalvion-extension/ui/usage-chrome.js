/**
 * Xalvion Extension — Usage chrome
 * Owner: xalvion-extension/ui
 *
 * Purpose:
 * - Keep quota/plan tier UI and upgrade panel behavior consistent across the extension.
 * - Contextual conversion surfaces (capacity, post–high-value run, gated power features) — no modal spam.
 * - Designed for dependency injection: DOM nodes + usage-plan functions passed in by orchestrator.
 */

import { NEAR_HARD_BUFFER } from "../usage-plan.js";

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

  /** @type {number} */
  let postRunHighlightUntil = 0;
  /** @type {'analyze' | 'scan' | null} */
  let lastGateAttempt = null;
  let gateAttemptUntil = 0;

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

  function formatRunSplit(snap) {
    return `Guest runs ${snap.guestUsageCount} · Enrolled runs ${snap.freeTierUsageCount}`;
  }

  /**
   * Call after a successful analyze when the run looks high-impact (confidence, $ surfaced, etc.).
   * Shows a positive, earned-value upgrade moment for a short window.
   */
  function notifyOperatorRunComplete(data) {
    if (!data || typeof data !== "object") return;
    const decision = data.decision && typeof data.decision === "object" ? data.decision : {};
    const conf = Number(decision.confidence ?? data.confidence ?? 0);
    const status = String(decision.status || data.status || "").toLowerCase();
    const money = Number(data.amount ?? decision.amount ?? 0);
    const highConfidence = Number.isFinite(conf) && conf >= 0.86;
    const moneySignal = Number.isFinite(money) && money >= 35;
    const resolved = status === "resolved";
    if (resolved && (highConfidence || moneySignal)) {
      postRunHighlightUntil = Date.now() + 4 * 60 * 1000;
    }
  }

  /**
   * When the user hits a hard gate (analyze/scan) or tries a power action at the limit.
   */
  function notifyGateAttempt(kind) {
    lastGateAttempt = kind;
    gateAttemptUntil = Date.now() + 90 * 1000;
  }

  function clearPostRunMoment() {
    postRunHighlightUntil = 0;
    refreshUsageChrome();
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
    const softLabel =
      snap.nearHardLimit && !snap.hardLimited
        ? `Extension · ${snap.totalOperatorRuns}/${snap.hardThreshold} runs (near cap)`
        : `Extension · ${snap.totalOperatorRuns}/${snap.hardThreshold} operator runs`;
    els.capPill.textContent = softLabel;
  }

  function refreshUsageChrome() {
    const snap = getUsageSnapshot(currentPlanTier());
    if (els.capPill) {
      if (snap.hasProAccess) {
        const t = currentPlanTier();
        els.capPill.textContent = t ? `Extension · ${String(t).toUpperCase()}` : "Extension · PRO";
      } else {
        els.capPill.textContent =
          snap.nearHardLimit && !snap.hardLimited
            ? `Extension · ${snap.totalOperatorRuns}/${snap.hardThreshold} runs (near cap)`
            : `Extension · ${snap.totalOperatorRuns}/${snap.hardThreshold} operator runs`;
      }
    }

    if (!els.upgradeContextPanel) return;

    els.upgradeContextPanel.classList.remove(
      "is-visible",
      "mode-soft",
      "mode-hard",
      "mode-post-value",
      "mode-locked-power",
      "mode-approaching"
    );

    if (snap.hasProAccess) {
      els.upgradeEnrollFreeBtn?.classList.add("is-hidden");
      els.upgradeDismissSoftBtn?.classList.add("is-hidden");
      if (els.upgradeContextSplit) els.upgradeContextSplit.textContent = "";
      return;
    }

    const now = Date.now();
    const gateFresh = lastGateAttempt && now < gateAttemptUntil;
    const postFresh = now < postRunHighlightUntil;

    const runsLeft = Math.max(0, snap.hardThreshold - snap.totalOperatorRuns);
    const approachingCopy =
      snap.showSoftNudge ||
      snap.nearHardLimit ||
      (runsLeft > 0 && runsLeft <= NEAR_HARD_BUFFER);

    // 1) Hard capacity — operator runs exhausted (still copy/insert/review).
    if (snap.hardLimited) {
      els.upgradeContextPanel.classList.add("is-visible", "mode-hard");
      if (gateFresh) els.upgradeContextPanel.classList.add("mode-locked-power");
      if (els.upgradeContextEyebrow) {
        els.upgradeContextEyebrow.textContent = gateFresh ? "Operator capacity" : "Included runs — window";
      }
      if (els.upgradeContextPrimary) {
        els.upgradeContextPrimary.textContent = gateFresh
          ? "This action needs another operator run — your included runs for this window are already allocated."
          : `${snap.totalOperatorRuns} operator runs logged this window (${snap.hardThreshold} included).`;
      }
      if (els.upgradeContextSecondary) {
        els.upgradeContextSecondary.textContent =
          "Pro keeps throughput predictable: higher included runs, same approval-first console, and uninterrupted ticket analysis when volume spikes.";
      }
      if (els.upgradeContextSplit) els.upgradeContextSplit.textContent = formatRunSplit(snap);
      els.upgradeDismissSoftBtn?.classList.add("is-hidden");
      els.upgradeEnrollFreeBtn?.classList.toggle("is-hidden", snap.freeTierEnrolled);
      if (els.upgradeProLink) {
        els.upgradeProLink.textContent = "Unlock Pro capacity →";
        els.upgradeProLink.dataset.moment = "hard_gate";
      }
      return;
    }

    // 2) After a high-value successful run — earned-value upgrade (time / billing / outcomes).
    if (postFresh) {
      els.upgradeContextPanel.classList.add("is-visible", "mode-post-value");
      if (els.upgradeContextEyebrow) els.upgradeContextEyebrow.textContent = "Earned momentum";
      if (els.upgradeContextPrimary) {
        els.upgradeContextPrimary.textContent =
          "That run cleared real work — strong confidence and billing signal on the line. Keep the streak without hitting a ceiling.";
      }
      if (els.upgradeContextSecondary) {
        els.upgradeContextSecondary.textContent =
          "Pro is for operators who want headroom: more included runs, Gmail insert and inbox scans without friction, and room for spikes.";
      }
      if (els.upgradeContextSplit) {
        els.upgradeContextSplit.textContent = `${formatRunSplit(snap)} · ${runsLeft} included run${runsLeft === 1 ? "" : "s"} left this window`;
      }
      els.upgradeDismissSoftBtn?.classList.remove("is-hidden");
      if (els.upgradeDismissSoftBtn) els.upgradeDismissSoftBtn.textContent = "Hide";
      els.upgradeEnrollFreeBtn?.classList.toggle("is-hidden", snap.freeTierEnrolled);
      if (els.upgradeProLink) {
        els.upgradeProLink.textContent = "Move to Pro →";
        els.upgradeProLink.dataset.moment = "post_value";
      }
      return;
    }

    // 3) Approaching included runs — contextual pressure with remaining buffer.
    if (approachingCopy && !snap.hardLimited) {
      els.upgradeContextPanel.classList.add("is-visible", "mode-soft", "mode-approaching");
      if (els.upgradeContextEyebrow) els.upgradeContextEyebrow.textContent = "Headroom";
      if (els.upgradeContextPrimary) {
        els.upgradeContextPrimary.textContent =
          runsLeft <= NEAR_HARD_BUFFER && runsLeft > 0
            ? `Only ${runsLeft} included operator run${runsLeft === 1 ? "" : "s"} left before this window’s cap.`
            : `You’ve used ${snap.totalOperatorRuns} operator runs toward the ${snap.hardThreshold}-run window.`;
      }
      if (els.upgradeContextSecondary) {
        els.upgradeContextSecondary.textContent =
          "Upgrade before the cap lands mid-shift — Pro adds capacity so ticket prep, copy/insert, and inbox scans stay available when volume spikes.";
      }
      if (els.upgradeContextSplit) {
        els.upgradeContextSplit.textContent = `${formatRunSplit(snap)} · ${runsLeft} left`;
      }
      els.upgradeDismissSoftBtn?.classList.remove("is-hidden");
      if (els.upgradeDismissSoftBtn) els.upgradeDismissSoftBtn.textContent = "Not now";
      els.upgradeEnrollFreeBtn?.classList.toggle("is-hidden", snap.freeTierEnrolled);
      if (els.upgradeProLink) {
        els.upgradeProLink.textContent = "See Pro capacity →";
        els.upgradeProLink.dataset.moment = "approaching";
      }
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
    const hint =
      "Included operator runs for this window are used. Copy, insert, and review stay available for your current reply.";
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
        showStatus("Free access enabled — run counts are tracked on this device and reset on a rolling window.");
      });
    }
    if (els.upgradeDismissSoftBtn && !els.upgradeDismissSoftBtn.dataset.bound) {
      els.upgradeDismissSoftBtn.dataset.bound = "1";
      els.upgradeDismissSoftBtn.addEventListener("click", async () => {
        const snap = getUsageSnapshot(currentPlanTier());
        if (Date.now() < postRunHighlightUntil) {
          clearPostRunMoment();
          showStatus("Got it — we’ll stay quiet until there’s a new capacity signal.");
          return;
        }
        await dismissSoftNudgeForPeriod();
        refreshUsageChrome();
      });
    }
    if (els.upgradeProLink && !els.upgradeProLink.dataset.bound) {
      els.upgradeProLink.dataset.bound = "1";
      els.upgradeProLink.addEventListener("click", (e) => {
        e.preventDefault();
        showStatus("Manage Pro from your workspace billing console.");
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
    notifyOperatorRunComplete,
    notifyGateAttempt,
  };
}
