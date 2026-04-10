/**
 * Extension operator API origin — single release-time switch for production vs local dev.
 *
 * Chrome MV3 cannot read process env at runtime. Shipped builds use PRODUCTION_OPERATOR_API_ORIGIN.
 *
 * Local dev: set USE_LOCAL_OPERATOR_API to true in this file for unpacked development only.
 *
 * Optional override (e.g. staging): before sidepanel scripts run, set
 *   globalThis.__XALVION_EXTENSION_OPERATOR_ORIGIN__ = "https://...";
 */
/** Set true only for unpacked local development — never ship with this enabled. */
const USE_LOCAL_OPERATOR_API = false;

const PRODUCTION_OPERATOR_API_ORIGIN = "https://xalvion-production.up.railway.app";
// For custom domains (e.g. api.xalvion.tech),
// replace this value once DNS is configured.
const LOCAL_OPERATOR_API_ORIGIN = "http://127.0.0.1:8000";

const DEFAULT_OPERATOR_API_ORIGIN = USE_LOCAL_OPERATOR_API
  ? LOCAL_OPERATOR_API_ORIGIN
  : PRODUCTION_OPERATOR_API_ORIGIN;

function normalizeOrigin(value) {
  const s = String(value || "").trim().replace(/\/+$/, "");
  return s || DEFAULT_OPERATOR_API_ORIGIN;
}

const fromGlobal =
  typeof globalThis !== "undefined" && globalThis.__XALVION_EXTENSION_OPERATOR_ORIGIN__ != null
    ? String(globalThis.__XALVION_EXTENSION_OPERATOR_ORIGIN__)
    : "";

export const OPERATOR_API_ORIGIN = normalizeOrigin(fromGlobal || DEFAULT_OPERATOR_API_ORIGIN);

const XALVION_ANALYZE_SECRET = "2ee34f109fede5549ada2d72802e5c01bdccd4ce5e2aa2edc5b3bc655eb4cf61";
