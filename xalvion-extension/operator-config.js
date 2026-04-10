/**
 * Extension operator API origin — single release-time switch for production vs local dev.
 *
 * Chrome MV3 cannot read process env at runtime. For production, set DEFAULT_OPERATOR_API_ORIGIN
 * to your hosted API (e.g. https://api.yourdomain.com or https://your-service.up.railway.app).
 *
 * Optional override (e.g. for experiments): before sidepanel scripts run, set
 *   globalThis.__XALVION_EXTENSION_OPERATOR_ORIGIN__ = "https://...";
 * (uncommon; DEFAULT is the supported path.)
 */
const DEFAULT_OPERATOR_API_ORIGIN = "http://127.0.0.1:8000";

function normalizeOrigin(value) {
  const s = String(value || "").trim().replace(/\/+$/, "");
  return s || DEFAULT_OPERATOR_API_ORIGIN;
}

const fromGlobal =
  typeof globalThis !== "undefined" && globalThis.__XALVION_EXTENSION_OPERATOR_ORIGIN__ != null
    ? String(globalThis.__XALVION_EXTENSION_OPERATOR_ORIGIN__)
    : "";

export const OPERATOR_API_ORIGIN = normalizeOrigin(fromGlobal || DEFAULT_OPERATOR_API_ORIGIN);
