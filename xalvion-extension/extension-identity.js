/**
 * Stable anonymous identity for operator API metering (guest client + workspace).
 * Persists in chrome.storage.local — required for server-side quota enforcement.
 */

const STORAGE_KEY = "xalvion_extension_identity_v1";

export async function getExtensionIdentity() {
  const bag = await chrome.storage.local.get(STORAGE_KEY);
  let rec = bag[STORAGE_KEY];
  if (!rec || typeof rec !== "object") {
    rec = {};
  }
  let changed = false;
  if (!rec.clientId || typeof rec.clientId !== "string") {
    rec.clientId = typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `xc_${Date.now()}_${Math.random().toString(36).slice(2, 12)}`;
    changed = true;
  }
  if (!rec.workspaceId || typeof rec.workspaceId !== "string") {
    rec.workspaceId = typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `xw_${Date.now()}_${Math.random().toString(36).slice(2, 12)}`;
    changed = true;
  }
  if (changed) {
    await chrome.storage.local.set({ [STORAGE_KEY]: rec });
  }
  return { clientId: String(rec.clientId), workspaceId: String(rec.workspaceId) };
}
