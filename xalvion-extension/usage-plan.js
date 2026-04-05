/**
 * Local usage + plan gate for operator runs (chrome.storage).
 * Server plan_tier from analyze responses takes precedence (Pro never downgraded by local caps).
 */

const STORAGE_KEY = "xalvion_usage_v1";
const PERIOD_MS = 7 * 24 * 60 * 60 * 1000;

/** Total successful runs before contextual soft nudge (non-blocking). */
export const SOFT_THRESHOLD_TOTAL = 4;

/** Total successful runs before Analyze is gated (Copy / Insert / approval flows stay). */
export const HARD_THRESHOLD_TOTAL = 12;

const initialPersisted = {
  guestUsageCount: 0,
  freeTierUsageCount: 0,
  /** After true, new successful runs increment free tier only (guest frozen). */
  freeTierEnrolled: false,
  softNudgeDismissedPeriodId: null,
  periodStartedAt: null,
  /** Optional local unlock for QA / future billing hook. */
  proUnlockLocal: false,
};

let cache = { ...initialPersisted };
let loaded = false;

function periodId(now) {
  return Math.floor(now / PERIOD_MS);
}

function normalizeTier(tier) {
  if (tier == null) return "";
  return String(tier).trim().toLowerCase();
}

export function isProFromPlanTier(planTier, localUnlock = false) {
  if (localUnlock) return true;
  const t = normalizeTier(planTier);
  return t === "pro" || t === "enterprise" || t === "paid" || t === "team";
}

export async function loadUsagePlan() {
  try {
    const bag = await chrome.storage.local.get(STORAGE_KEY);
    const raw = bag[STORAGE_KEY];
    if (raw && typeof raw === "object") {
      cache = { ...initialPersisted, ...raw };
    } else {
      cache = { ...initialPersisted };
    }
    const now = Date.now();
    if (!cache.periodStartedAt) {
      cache.periodStartedAt = now;
      await persist();
    } else if (now - cache.periodStartedAt >= PERIOD_MS) {
      cache.guestUsageCount = 0;
      cache.freeTierUsageCount = 0;
      cache.softNudgeDismissedPeriodId = null;
      cache.periodStartedAt = now;
      await persist();
    }
    loaded = true;
  } catch (err) {
    console.error("[usage-plan] load failed", err);
    loaded = true;
  }
  return getUsageSnapshot(null);
}

async function persist() {
  try {
    await chrome.storage.local.set({ [STORAGE_KEY]: { ...cache } });
  } catch (err) {
    console.error("[usage-plan] persist failed", err);
  }
}

/**
 * Call after a successful single-ticket analyze (response rendered).
 * Does not increment when Pro / unlimited from server or local unlock.
 */
export async function recordSuccessfulOperatorRun(planTier) {
  if (!loaded) await loadUsagePlan();
  if (isProFromPlanTier(planTier, cache.proUnlockLocal)) {
    return getUsageSnapshot(planTier);
  }
  if (cache.freeTierEnrolled) {
    cache.freeTierUsageCount += 1;
  } else {
    cache.guestUsageCount += 1;
  }
  await persist();
  return getUsageSnapshot(planTier);
}

/** Each inbox thread analyzed counts as one operator run (same as backend calls). */
export async function recordSuccessfulOperatorRuns(planTier, count) {
  if (!loaded) await loadUsagePlan();
  const n = Math.max(0, Math.floor(Number(count) || 0));
  if (n === 0 || isProFromPlanTier(planTier, cache.proUnlockLocal)) {
    return getUsageSnapshot(planTier);
  }
  if (cache.freeTierEnrolled) {
    cache.freeTierUsageCount += n;
  } else {
    cache.guestUsageCount += n;
  }
  await persist();
  return getUsageSnapshot(planTier);
}

export function getUsageSnapshot(planTier) {
  const guest = cache.guestUsageCount;
  const free = cache.freeTierUsageCount;
  const total = guest + free;
  const hasAccess = isProFromPlanTier(planTier, cache.proUnlockLocal);
  const atOrPastSoft = !hasAccess && total >= SOFT_THRESHOLD_TOTAL;
  const atHard = !hasAccess && total >= HARD_THRESHOLD_TOTAL;
  const now = Date.now();
  const pid = periodId(now);
  const softDismissedForPeriod = cache.softNudgeDismissedPeriodId === pid;
  return {
    guestUsageCount: guest,
    freeTierUsageCount: free,
    totalOperatorRuns: total,
    freeTierEnrolled: cache.freeTierEnrolled,
    softThreshold: SOFT_THRESHOLD_TOTAL,
    hardThreshold: HARD_THRESHOLD_TOTAL,
    hasProAccess: hasAccess,
    showSoftNudge: atOrPastSoft && !atHard && !softDismissedForPeriod,
    hardLimited: atHard,
    periodResetsInMs: Math.max(0, cache.periodStartedAt + PERIOD_MS - now),
  };
}

export async function enrollFreeTier() {
  if (!loaded) await loadUsagePlan();
  cache.freeTierEnrolled = true;
  await persist();
  return getUsageSnapshot(null);
}

export async function dismissSoftNudgeForPeriod() {
  if (!loaded) await loadUsagePlan();
  cache.softNudgeDismissedPeriodId = periodId(Date.now());
  await persist();
  return getUsageSnapshot(null);
}

export async function setLocalProUnlock(on) {
  if (!loaded) await loadUsagePlan();
  cache.proUnlockLocal = Boolean(on);
  await persist();
  return getUsageSnapshot(null);
}
