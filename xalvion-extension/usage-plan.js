/**
 * Operator capacity — driven by server `operator_entitlements` from POST /analyze.
 * Local chrome.storage is used only for soft-nudge dismiss state (UX), not enforcement.
 */

import { sessionStore } from "./stores/session-store.js";

const DISMISS_KEY = "xalvion_usage_soft_dismiss_v1";
const PERIOD_MS = 7 * 24 * 60 * 60 * 1000;

/** Fraction of included runs remaining before contextual “approaching” copy (non-blocking). */
export const NEAR_HARD_BUFFER = 3;

let softDismissLoaded = false;
let softDismissedPeriodId = null;

function periodId(now) {
  return Math.floor(now / PERIOD_MS);
}

function normalizeTier(tier) {
  if (tier == null) return "";
  return String(tier).trim().toLowerCase();
}

export function isProFromPlanTier(planTier) {
  const t = normalizeTier(planTier);
  return t === "pro" || t === "elite" || t === "enterprise" || t === "paid" || t === "team" || t === "dev";
}

async function loadSoftDismiss() {
  if (softDismissLoaded) return;
  try {
    const bag = await chrome.storage.local.get(DISMISS_KEY);
    softDismissedPeriodId = bag[DISMISS_KEY] ?? null;
  } catch (err) {
    console.error("[usage-plan] soft dismiss load failed", err);
  }
  softDismissLoaded = true;
}

export async function loadUsagePlan() {
  await loadSoftDismiss();
  return getUsageSnapshot(sessionStore.getState().planTier);
}

export function getUsageSnapshot(planTier) {
  const s = sessionStore.getState();
  const hasServer = s.operatorUsage != null && s.operatorLimit != null;
  const usage = hasServer ? Math.max(0, Number(s.operatorUsage) || 0) : 0;
  const limit = hasServer ? Math.max(1, Number(s.operatorLimit) || 1) : 12;
  const remaining = hasServer ? Math.max(0, Number(s.operatorRemaining ?? 0)) : 12;
  const hasAccess = isProFromPlanTier(planTier || s.planTier);
  const atHard = Boolean(!hasAccess && hasServer && s.operatorAtLimit);
  const approachingServer = Boolean(!hasAccess && hasServer && s.operatorApproaching);
  const runsLeft = Math.max(0, limit - usage);
  const nearHardLimit =
    !hasAccess &&
    hasServer &&
    !atHard &&
    (approachingServer || (runsLeft > 0 && runsLeft <= NEAR_HARD_BUFFER && limit < 1e9));
  const now = Date.now();
  const pid = periodId(now);
  const softDismissedForPeriod = softDismissedPeriodId === pid;
  const softThreshold = Math.max(3, Math.floor(limit * 0.35));
  const atOrPastSoft = !hasAccess && hasServer && usage >= softThreshold;
  return {
    guestUsageCount: 0,
    freeTierUsageCount: 0,
    totalOperatorRuns: usage,
    freeTierEnrolled: true,
    softThreshold,
    hardThreshold: limit,
    hasProAccess: hasAccess,
    showSoftNudge: atOrPastSoft && !atHard && !softDismissedForPeriod && hasServer,
    hardLimited: atHard,
    nearHardLimit,
    periodResetsInMs: Math.max(0, (s.usagePeriodAnchor || now) + PERIOD_MS - now),
    serverMetered: hasServer,
  };
}

/**
 * Apply authoritative usage from POST /analyze (or similar) JSON body.
 */
export function syncOperatorEntitlementsFromResponse(planTier, data) {
  const ent = data && typeof data === "object" ? data.operator_entitlements : null;
  if (!ent || typeof ent !== "object") {
    return getUsageSnapshot(planTier);
  }
  const lim = Math.max(1, Number(ent.limit) || 1);
  const use = Math.max(0, Number(ent.usage) || 0);
  const rem = Number.isFinite(Number(ent.remaining)) ? Math.max(0, Number(ent.remaining)) : Math.max(0, lim - use);
  const tier = ent.plan_tier != null ? String(ent.plan_tier) : planTier;
  sessionStore.setState({
    planTier: tier != null ? tier : sessionStore.getState().planTier,
    operatorUsage: use,
    operatorLimit: lim,
    operatorRemaining: rem,
    operatorAtLimit: Boolean(ent.at_limit),
    operatorApproaching: Boolean(ent.approaching_limit),
    usagePeriodAnchor: Date.now(),
  });
  return getUsageSnapshot(tier || planTier);
}

/** @deprecated No local quota increments — server meters runs. */
export async function recordSuccessfulOperatorRun(planTier) {
  return getUsageSnapshot(planTier);
}

/** @deprecated No local quota increments — server meters runs. */
export async function recordSuccessfulOperatorRuns(planTier, _count) {
  return getUsageSnapshot(planTier);
}

/** @deprecated Enrollment is account/workspace scoped in the product console. */
export async function enrollFreeTier() {
  return getUsageSnapshot(null);
}

export async function dismissSoftNudgeForPeriod() {
  await loadSoftDismiss();
  softDismissedPeriodId = periodId(Date.now());
  try {
    await chrome.storage.local.set({ [DISMISS_KEY]: softDismissedPeriodId });
  } catch (err) {
    console.error("[usage-plan] soft dismiss persist failed", err);
  }
  return getUsageSnapshot(sessionStore.getState().planTier);
}
