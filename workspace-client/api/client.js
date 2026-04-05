/**
 * Xalvion API client — fetch wrapper with auth, retries, SSE stream helper.
 * Degrades when imported alone; workspace boot registers globally for app.js.
 */

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function extractDetail(data) {
  if (!data || typeof data !== "object") return "";
  const d = data.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d.length && typeof d[0]?.msg === "string") return d[0].msg;
  return "";
}

export function createApiClient(options = {}) {
  const {
    getToken = () => "",
    baseUrl = "",
    fetchImpl = typeof fetch !== "undefined" ? fetch.bind(globalThis) : null,
    maxRetries = 2,
    onUnauthorized = null,
  } = options;

  if (typeof fetchImpl !== "function") {
    return {
      post: async () => {
        throw new Error("fetch unavailable");
      },
      get: async () => {
        throw new Error("fetch unavailable");
      },
      stream: async () => {
        throw new Error("fetch unavailable");
      },
      extractDetail,
    };
  }

  function authHeaders(json = true) {
    const h = {};
    if (json) h["Content-Type"] = "application/json";
    const t = getToken();
    if (t) h.Authorization = `Bearer ${t}`;
    return h;
  }

  async function post(path, body, { headers = {} } = {}) {
    let attempt = 0;
    let lastErr;
    while (attempt <= maxRetries) {
      const res = await fetchImpl(`${baseUrl}${path}`, {
        method: "POST",
        headers: { ...authHeaders(true), ...headers },
        body: JSON.stringify(body ?? {}),
      });
      const data = await res.json().catch(() => ({}));
      if (res.status === 401) {
        onUnauthorized?.();
        throw new Error(extractDetail(data) || "Session expired.");
      }
      if (res.status >= 500 && attempt < maxRetries) {
        attempt += 1;
        await sleep(200 * 2 ** attempt);
        lastErr = new Error(extractDetail(data) || "Server error.");
        continue;
      }
      if (!res.ok) {
        throw new Error(extractDetail(data) || `Request failed (${res.status}).`);
      }
      return data;
    }
    throw lastErr || new Error("Request failed.");
  }

  async function get(path, { headers = {} } = {}) {
    let attempt = 0;
    let lastErr;
    while (attempt <= maxRetries) {
      const res = await fetchImpl(`${baseUrl}${path}`, {
        method: "GET",
        headers: { ...authHeaders(false), ...headers },
      });
      const data = await res.json().catch(() => ({}));
      if (res.status === 401) {
        onUnauthorized?.();
        throw new Error(extractDetail(data) || "Session expired.");
      }
      if (res.status >= 500 && attempt < maxRetries) {
        attempt += 1;
        await sleep(200 * 2 ** attempt);
        lastErr = new Error(extractDetail(data) || "Server error.");
        continue;
      }
      if (!res.ok) {
        throw new Error(extractDetail(data) || `Request failed (${res.status}).`);
      }
      return data;
    }
    throw lastErr || new Error("Request failed.");
  }

  async function stream(path, body, { onEvent, signal } = {}) {
    const res = await fetchImpl(`${baseUrl}${path}`, {
      method: "POST",
      headers: authHeaders(true),
      body: JSON.stringify(body ?? {}),
      signal,
    });

    if (res.status === 401) {
      const data = await res.json().catch(() => ({}));
      onUnauthorized?.();
      throw new Error(extractDetail(data) || "Session expired.");
    }

    if (!res.ok || !res.body) {
      const data = await res.json().catch(() => ({}));
      throw new Error(extractDetail(data) || `Stream failed (${res.status}).`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    const parseBlock = (block) => {
      if (!block.trim()) return;
      let eventName = "message";
      let dataStr = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) eventName = line.slice(6).trim();
        if (line.startsWith("data:")) dataStr += line.slice(5).trim();
      }
      if (!dataStr) return;
      try {
        const data = JSON.parse(dataStr);
        onEvent?.({ event: eventName, data });
      } catch {
        /* ignore malformed chunk */
      }
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";
      for (const p of parts) parseBlock(p);
    }
    if (buffer.trim()) parseBlock(buffer);
  }

  return { post, get, stream, extractDetail };
}

export { extractDetail };
