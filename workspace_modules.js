export function createPhase2Core({ fetchImpl }) {
  const safeFetch = typeof fetchImpl === "function" ? fetchImpl : fetch.bind(globalThis);

  const format = {
    detailFromApiBody(data) {
      const detail = data && data.detail;
      if (typeof detail === "string") return detail;
      if (Array.isArray(detail) && detail.length && typeof detail[0]?.msg === "string") return detail[0].msg;
      return "";
    },
    formatTier(value) {
      const tier = String(value || "free").toLowerCase();
      return tier.charAt(0).toUpperCase() + tier.slice(1);
    },
    formatMetric(value, digits = 0) {
      const num = Number(value || 0);
      return Number.isFinite(num) ? num.toFixed(digits) : digits ? (0).toFixed(digits) : "0";
    },
    formatMoney(value) {
      const num = Number(value || 0);
      return `$${Number.isFinite(num) ? num.toFixed(0) : "0"}`;
    },
    relativeTime(date = new Date()) {
      const d = date instanceof Date ? date : new Date(date);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    },
    formatExecutionTier(tier) {
      const map = {
        safe_autopilot_ready: "Safe to automate",
        approval_required: "Approval required",
        assist_only: "Manual review",
      };
      const k = String(tier || "").toLowerCase();
      return map[k] || "Unknown";
    },
    formatOutcomeQuality(score) {
      const n = Number(score);
      if (!Number.isFinite(n)) return "Unknown";
      if (n < 2.0) return "Low";
      if (n < 3.5) return "Moderate";
      if (n < 4.5) return "Strong";
      return "Excellent";
    },
    formatImpactScore(score) {
      if (score === null || score === undefined) return "—";
      const n = Number(score);
      if (!Number.isFinite(n)) return "—";
      if (n >= 0.8) return "Excellent";
      if (n >= 0.58) return "Good";
      if (n >= 0.38) return "Neutral";
      return "Poor";
    },
    formatImpactLabel(label) {
      const map = {
        excellent: "Excellent outcome",
        good: "Good outcome",
        neutral: "Neutral outcome",
        bad: "Poor outcome",
      };
      const k = String(label || "").toLowerCase();
      return map[k] || label || "—";
    },
    buildExplanationSummary(explanation) {
      if (!explanation || typeof explanation !== "object") return "";
      const s = explanation.summary;
      return typeof s === "string" ? s : "";
    },
  };

  const store = {
    planCopy(tier) {
      switch (String(tier || "free").toLowerCase()) {
        case "pro":
          return "Priority handling, larger usage limits, and a more serious operating surface for real support volume.";
        case "elite":
          return "Maximum capacity, premium control, and the strongest Xalvion operator environment.";
        default:
          return "Entry access with clear capacity limits and a visible upgrade path when usage pressure builds.";
      }
    },
  };

  async function parseResponse(res) {
    return res.json().catch(() => ({}));
  }

  const api = {
    async post({ baseUrl = "", path, body, headers = {}, onUnauthorized, extractDetail = format.detailFromApiBody }) {
      const res = await safeFetch(`${baseUrl}${path}`, {
        method: "POST",
        headers,
        body: JSON.stringify(body || {}),
      });
      const data = await parseResponse(res);
      if (res.status === 401) {
        onUnauthorized?.();
        throw new Error(extractDetail(data) || "Session expired.");
      }
      if (!res.ok) {
        throw new Error(extractDetail(data) || "Request failed.");
      }
      return data;
    },
    async get({ baseUrl = "", path, headers = {}, onUnauthorized, extractDetail = format.detailFromApiBody }) {
      const res = await safeFetch(`${baseUrl}${path}`, { headers });
      const data = await parseResponse(res);
      if (res.status === 401) {
        onUnauthorized?.();
        throw new Error(extractDetail(data) || "Session expired.");
      }
      if (!res.ok) {
        throw new Error(extractDetail(data) || "Request failed.");
      }
      return data;
    },
  };

  return { format, store, api };
}
