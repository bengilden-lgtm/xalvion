/**
 * Operator (FastAPI) — authoritative origin and lightweight reachability checks.
 * Origin is defined in operator-config.js (edit for production releases).
 */
import { OPERATOR_API_ORIGIN } from "./operator-config.js";

export const OPERATOR_ANALYZE_URL = `${OPERATOR_API_ORIGIN}/analyze`;
export const OPERATOR_HEALTH_URL = `${OPERATOR_API_ORIGIN}/health`;

/** Human-readable host for error copy (e.g. api.example.com or 127.0.0.1:8000). */
export function getOperatorConnectionLabel() {
  try {
    const u = new URL(OPERATOR_API_ORIGIN);
    return u.host || OPERATOR_API_ORIGIN;
  } catch {
    return OPERATOR_API_ORIGIN.replace(/^https?:\/\//i, "");
  }
}

export const OPERATOR_CONNECTION_LABEL = getOperatorConnectionLabel();

/** @deprecated Use OPERATOR_API_ORIGIN — kept for any external imports. */
export const LOCAL_OPERATOR_ORIGIN = OPERATOR_API_ORIGIN;
/** @deprecated Use OPERATOR_ANALYZE_URL */
export const LOCAL_OPERATOR_ANALYZE_URL = OPERATOR_ANALYZE_URL;
/** @deprecated Use OPERATOR_HEALTH_URL */
export const LOCAL_OPERATOR_HEALTH_URL = OPERATOR_HEALTH_URL;
/** @deprecated Use OPERATOR_CONNECTION_LABEL */
export const OPERATOR_HOST_PORT_LABEL = OPERATOR_CONNECTION_LABEL;

const HEALTH_TIMEOUT_MS = 4000;

/**
 * Fast GET /health before heavier POST /analyze calls.
 * @returns {{ ok: true } | { ok: false, kind: 'network' | 'timeout' | 'http_error', status?: number }}
 */
export async function pingOperatorHealth(timeoutMs = HEALTH_TIMEOUT_MS) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(OPERATOR_HEALTH_URL, {
      method: "GET",
      signal: controller.signal,
    });
    if (!res.ok) {
      return { ok: false, kind: "http_error", status: res.status };
    }
    return { ok: true };
  } catch (err) {
    const isAbort =
      err && typeof err === "object" && (err.name === "AbortError" || /aborted/i.test(String(err.message || "")));
    return { ok: false, kind: isAbort ? "timeout" : "network" };
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * User-facing copy when GET /health fails before a heavier POST.
 * @param {{ ok: false, kind: string, status?: number }} health
 */
export function describeOperatorHealthFailure(health) {
  const k = health.kind || "";
  if (k === "http_error") {
    const st = health.status;
    return {
      title: "Backend is running, but the health check failed",
      body: st
        ? `GET /health returned HTTP ${st}. The API may be mid-startup — try again, or check operator logs.`
        : "The health endpoint did not respond as expected. Try again in a moment.",
    };
  }
  if (k === "timeout") {
    return {
      title: `Operator app not responding (${OPERATOR_CONNECTION_LABEL})`,
      body: "The health check timed out. If the backend is starting up, wait a few seconds and tap Retry.",
    };
  }
  return {
    title: `Operator app not reachable (${OPERATOR_CONNECTION_LABEL})`,
    body: `Start the hosted or local API (see README / operator-config.js), then tap Retry.`,
  };
}

/**
 * Map POST /analyze fetch result to title + body (Analyze / shared with scan row failures).
 * @param {object} result - fetchJsonWithTimeout return shape
 * @param {{ actionLabel?: string }} [opts]
 */
export function describeOperatorAnalyzeFailure(result, opts = {}) {
  const action = opts.actionLabel || "Analyze";
  const k = result.kind || "";
  if (k === "timeout") {
    return {
      title: "Request timed out",
      body: `The operator at ${OPERATOR_CONNECTION_LABEL} took too long to answer. Check that the API is running, then tap Retry.`,
    };
  }
  if (k === "network") {
    return {
      title: `Operator app not reachable (${OPERATOR_CONNECTION_LABEL})`,
      body: `We could not connect to the operator API. Confirm the URL in operator-config.js matches your deployment, then try again.`,
    };
  }
  if (k === "plan_blocked") {
    const pb = result.planBlocked && typeof result.planBlocked === "object" ? result.planBlocked : {};
    const msg = String(pb.message || result.detail || "").trim();
    return {
      title: "Plan limit reached",
      body:
        msg ||
        "Included operator runs for this billing period are used up. Open your workspace billing console to upgrade or wait for the next usage window.",
    };
  }
  if (k === "http_error") {
    const st = result.status;
    const detail = String(result.detail || "").trim();
    const detailLine = detail && detail.length < 220 ? ` (${detail})` : "";
    return {
      title: "Backend is running, but the request failed",
      body: st
        ? `${action} got HTTP ${st}${detailLine}. Check the operator logs, then try again.`
        : `${action} failed after reaching the operator. Check the operator logs, then try again.`,
    };
  }
  if (k === "invalid_json") {
    return {
      title: "Unexpected response",
      body: "The operator returned data we could not read. Try again after a moment.",
    };
  }
  return {
    title: `${action} did not complete`,
    body: result.status
      ? `Something went wrong (HTTP ${result.status}). Try again in a moment.`
      : "Something went wrong. Try again in a moment.",
  };
}
