(function (global) {
  "use strict";

  /**
   * Shared fetch/format helpers for the workspace. Phase 2 operator chrome (rails, decision hierarchy,
   * monetization surfaces) lives in app.js + styles.css; extend this module only when a shared primitive
   * is required across bundles.
   */
  function createPhase2Core(config) {
    const fetchImpl =
      config && typeof config.fetchImpl === "function"
        ? config.fetchImpl
        : typeof global.fetch === "function"
          ? global.fetch.bind(global)
          : null;

    const format = {
      detailFromApiBody(data) {
        const detail = data && data.detail;
        if (typeof detail === "string") return detail;
        if (Array.isArray(detail) && detail.length && typeof detail[0]?.msg === "string") {
          return detail[0].msg;
        }
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
      relativeTime(date) {
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
      formatConsequenceSignal(tier, requiresApproval, riskLevel) {
        const t = String(tier || "").toLowerCase();
        const risk = String(riskLevel || "").toLowerCase();
        if (risk === "high") {
          return { label: "⚠ High risk", variant: "high_risk", cls: "signal-high-risk" };
        }
        if (t === "safe_autopilot_ready" && !requiresApproval) {
          return { label: "✓ Safe to automate", variant: "safe", cls: "signal-safe" };
        }
        if (t === "approval_required" || requiresApproval) {
          return { label: "⚡ Approval required", variant: "approval", cls: "signal-approval" };
        }
        if (t === "assist_only") {
          return { label: "○ Manual review", variant: "review", cls: "signal-review" };
        }
        return { label: "○ Manual review", variant: "review", cls: "signal-review" };
      },
      /**
       * Mirrors main workspace `deriveConsequenceSignal` (app.js) for API-shaped payloads.
       * Pure helper — safe for extension or other bundles that cannot import app.js.
       */
      deriveConsequencePresentation(data) {
        const d = data && typeof data === "object" ? data : {};
        const dec = d.sovereign_decision && typeof d.sovereign_decision === "object" ? d.sovereign_decision : d.decision || {};
        const triage =
          d.triage_metadata && typeof d.triage_metadata === "object"
            ? d.triage_metadata
            : d.triage || {};
        // File: workspace_modules.js
        // Governor fields (when present) become source-of-truth for trust signaling.
        const govRisk = String(d.governor_risk_level || dec.governor_risk_level || "").toLowerCase();
        const risk = String(govRisk || dec.risk_level || triage.risk_level || d.risk_level || "").toLowerCase();
        const execMode = String(d.execution_mode || dec.execution_mode || "").toLowerCase();
        if (execMode === "blocked") {
          return {
            cls: "signal-high-risk",
            text: "⛔ Blocked",
            title: String(d.governor_reason || dec.governor_reason || "Blocked by governor policy"),
          };
        }
        if (risk === "high") {
          return {
            cls: "signal-high-risk",
            text: "⚠ High risk",
            title: "Elevated risk — review before customer send",
          };
        }
        const tier = String(d.execution_tier || "").toLowerCase();
        if (tier === "safe_autopilot_ready") {
          return {
            cls: "signal-safe",
            text: "✓ Safe to automate",
            title: "Meets all automation safety criteria",
          };
        }
        if (tier === "assist_only") {
          return {
            cls: "signal-review",
            text: "○ Manual review",
            title: "Risk signals require human decision",
          };
        }
        if (tier === "approval_required") {
          return {
            cls: "signal-approval",
            text: "⚡ Approval required",
            title: String(d.governor_reason || dec.governor_reason || "Awaiting operator approval"),
          };
        }
        const action = String(d.action || dec.action || "none").toLowerCase();
        const actionRisk = String(dec.risk_level || triage.risk_level || "medium").toLowerCase();
        const req = Boolean(d.requires_approval || dec.requires_approval || d.decision_state === "pending_decision");
        const money = action === "refund" || action === "charge" || action === "credit";
        if (req && money) {
          return { cls: "signal-approval", text: "⚡ Approval required", title: "" };
        }
        if (action === "review" || actionRisk === "high" || actionRisk === "medium") {
          return { cls: "signal-review", text: "⚠ Review recommended", title: "" };
        }
        return { cls: "signal-safe", text: "✓ Safe to send", title: "" };
      },
      normalizeGovernorFactors(value) {
        if (!value) return [];
        if (Array.isArray(value)) {
          return value
            .map((x) => (x === null || typeof x === "undefined" ? "" : String(x)).trim())
            .filter(Boolean);
        }
        if (typeof value === "string") {
          const t = value.trim();
          if (!t) return [];
          const parts = t.includes("\n") ? t.split("\n") : t.split(/[;•]/g);
          return parts.map((x) => String(x || "").trim()).filter(Boolean);
        }
        if (typeof value === "object") {
          const v = value;
          const candidates = [];
          if (Array.isArray(v.factors)) candidates.push(...v.factors);
          if (Array.isArray(v.items)) candidates.push(...v.items);
          if (Array.isArray(v.signals)) candidates.push(...v.signals);
          if (candidates.length) {
            return candidates
              .map((x) => (x === null || typeof x === "undefined" ? "" : String(x)).trim())
              .filter(Boolean);
          }
          try {
            return [JSON.stringify(v)].map((x) => String(x || "").trim()).filter(Boolean);
          } catch {
            return [String(v)].map((x) => String(x || "").trim()).filter(Boolean);
          }
        }
        return [String(value)].map((x) => String(x || "").trim()).filter(Boolean);
      },
      normalizeViolations(value) {
        if (!value) return [];
        if (Array.isArray(value)) {
          return value
            .map((x) => (x === null || typeof x === "undefined" ? "" : String(x)).trim())
            .filter(Boolean);
        }
        if (typeof value === "string") {
          const t = value.trim();
          if (!t) return [];
          const parts = t.includes("\n") ? t.split("\n") : t.split(/[;•]/g);
          return parts.map((x) => String(x || "").trim()).filter(Boolean);
        }
        if (typeof value === "object") {
          const v = value;
          const candidates = [];
          if (Array.isArray(v.violations)) candidates.push(...v.violations);
          if (Array.isArray(v.items)) candidates.push(...v.items);
          if (Array.isArray(v.errors)) candidates.push(...v.errors);
          if (candidates.length) {
            return candidates
              .map((x) => (x === null || typeof x === "undefined" ? "" : String(x)).trim())
              .filter(Boolean);
          }
          try {
            return [JSON.stringify(v)].map((x) => String(x || "").trim()).filter(Boolean);
          } catch {
            return [String(v)].map((x) => String(x || "").trim()).filter(Boolean);
          }
        }
        return [String(value)].map((x) => String(x || "").trim()).filter(Boolean);
      },
      formatGovernorRisk(governor_risk_level, governor_risk_score) {
        const level = String(governor_risk_level || "").toLowerCase();
        const levelLabel =
          level === "low" ? "Low risk" : level === "medium" ? "Medium risk" : level === "high" ? "High risk" : "";
        if (!levelLabel) return "";
        const score = Number(governor_risk_score);
        if (Number.isFinite(score)) {
          const s = Math.max(0, Math.min(5, Math.round(score)));
          return `${levelLabel} · ${s}/5`;
        }
        return levelLabel;
      },
      deriveGovernorPresentation(data) {
        const d = data && typeof data === "object" ? data : {};
        const dec = d.sovereign_decision && typeof d.sovereign_decision === "object" ? d.sovereign_decision : d.decision || {};
        const triage =
          d.triage_metadata && typeof d.triage_metadata === "object"
            ? d.triage_metadata
            : d.triage || {};

        const execModeRaw = d.execution_mode ?? dec.execution_mode;
        const execMode = String(execModeRaw || "").toLowerCase();
        const hasGov =
          execMode === "auto" ||
          execMode === "review" ||
          execMode === "blocked" ||
          d.governor_reason != null ||
          dec.governor_reason != null ||
          d.governor_risk_level != null ||
          dec.governor_risk_level != null ||
          d.governor_risk_score != null ||
          dec.governor_risk_score != null ||
          d.governor_factors != null ||
          dec.governor_factors != null ||
          d.violations != null ||
          dec.violations != null ||
          d.approved != null ||
          dec.approved != null;

        const govReason = String(d.governor_reason || dec.governor_reason || "").trim();
        const govRiskLevel = String(d.governor_risk_level || dec.governor_risk_level || "").toLowerCase();
        const govRiskScore = d.governor_risk_score ?? dec.governor_risk_score;
        const factors = format.normalizeGovernorFactors(d.governor_factors ?? dec.governor_factors).slice(0, 12);
        const violations = format.normalizeViolations(d.violations ?? dec.violations).slice(0, 12);
        const riskChip = format.formatGovernorRisk(govRiskLevel, govRiskScore);

        const nextStep =
          execMode === "blocked"
            ? "Edit or escalate before execution."
            : execMode === "review"
              ? "Review and approve before execution."
              : execMode === "auto"
                ? "Action can proceed without operator intervention."
                : "";

        // Determine mode + top label/cls. Governor is source of truth only when governor fields are present.
        let mode = hasGov ? (execMode || "unknown") : "unknown";

        // Never imply safe if violations exist or risk is high, even if execMode is "auto".
        if (hasGov && mode === "auto" && (violations.length > 0 || govRiskLevel === "high")) {
          mode = "review";
        }

        let label = "";
        let cls = "";
        let title = "";

        if (mode === "blocked") {
          label = "Blocked by policy";
          cls = "signal-high-risk signal-blocked";
          title = govReason || "Blocked by governor policy";
        } else if (mode === "review") {
          label = "Approval required";
          cls = "signal-approval";
          title = govReason || "Review required under governor policy";
        } else if (mode === "auto") {
          label = "Safe to automate";
          cls = "signal-safe";
          title = govReason || "Meets automation safety criteria";
        }

        // Backwards-compatible fallback when no governor fields exist at all.
        if (!hasGov) {
          const legacy = format.deriveConsequencePresentation(d);
          const legacyLabel = legacy?.text || "○ Manual review";
          const legacyCls = legacy?.cls || "signal-review";
          return {
            label: legacyLabel.replace(/^✓\s*/g, "").replace(/^⚡\s*/g, "").replace(/^⚠\s*/g, "").replace(/^○\s*/g, "").replace(/^⛔\s*/g, ""),
            cls: legacyCls,
            title: legacy?.title || "",
            summary: "",
            nextStep: "",
            riskLabel: "",
            riskScoreLabel: "",
            factors: [],
            violations: [],
            mode: "unknown",
          };
        }

        const summary = govReason
          ? govReason
          : mode === "blocked"
            ? "Blocked by policy."
            : mode === "review"
              ? "Approval required under policy."
              : mode === "auto"
                ? "Low-risk action with no policy violations."
                : "";

        return {
          label,
          cls,
          title,
          summary,
          nextStep,
          riskLabel: govRiskLevel ? (govRiskLevel === "low" ? "Low risk" : govRiskLevel === "medium" ? "Medium risk" : govRiskLevel === "high" ? "High risk" : "") : "",
          riskScoreLabel: riskChip,
          factors,
          violations,
          mode: mode === "auto" || mode === "review" || mode === "blocked" ? mode : "unknown",
        };
      },
      formatValueSummary(metrics) {
        const m = metrics && typeof metrics === "object" ? metrics : {};
        return {
          tickets: Number(m.tickets_handled ?? m.tickets ?? 0) || 0,
          money: Number(m.money_moved ?? m.money_saved ?? 0) || 0,
          actions: Number(m.actions_taken ?? 0) || 0,
          minutes: Number(m.time_saved_minutes ?? 0) || 0,
        };
      },
      /** Phase 3: short strings for capacity / upgrade framing (no DOM). */
      monetizationFraming: {
        guestPreviewBody(freeMonthlyLimit, guestLimit) {
          const g = Number(guestLimit) || 0;
          const f = Number(freeMonthlyLimit) || 0;
          return `You used all ${g} guest preview runs — the workflow is real. A free account unlocks ${f} runs/month with saved threads and approval gates.`;
        },
        workspaceValueLine(valueGenerated) {
          const v = valueGenerated && typeof valueGenerated === "object" ? valueGenerated : {};
          const money = Number(v.money_saved ?? 0) || 0;
          const actions = Number(v.actions_taken ?? 0) || 0;
          const mins = Number(v.time_saved_minutes ?? 0) || 0;
          if (money <= 0 && actions <= 0 && mins <= 0) return "";
          return `This workspace has already surfaced $${money.toFixed(0)} across ${actions} billing motions (~${mins} min of operator time).`;
        },
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
      tierBadge(tier) {
        const t = String(tier || "free").toLowerCase();
        const labels = { free: "Free", pro: "Pro", elite: "Elite", dev: "Dev" };
        const variants = {
          free: "tier-free",
          pro: "tier-pro",
          elite: "tier-elite",
          dev: "tier-dev",
        };
        return { label: labels[t] || format.formatTier(t), variant: variants[t] || "tier-free" };
      },
    };

    async function parseResponse(res) {
      return res.json().catch(() => ({}));
    }

    const api = {
      async post({ baseUrl = "", path, body, headers = {}, onUnauthorized, extractDetail: ed = format.detailFromApiBody }) {
        if (!fetchImpl) throw new Error("fetch unavailable");
        const res = await fetchImpl(`${baseUrl}${path}`, {
          method: "POST",
          headers,
          body: JSON.stringify(body || {}),
        });
        const data = await parseResponse(res);
        if (res.status === 401) {
          onUnauthorized?.();
          throw new Error(ed(data) || "Session expired.");
        }
        if (!res.ok) {
          throw new Error(ed(data) || "Request failed.");
        }
        return data;
      },
      async get({ baseUrl = "", path, headers = {}, onUnauthorized, extractDetail: ed = format.detailFromApiBody }) {
        if (!fetchImpl) throw new Error("fetch unavailable");
        const res = await fetchImpl(`${baseUrl}${path}`, { headers });
        const data = await parseResponse(res);
        if (res.status === 401) {
          onUnauthorized?.();
          throw new Error(ed(data) || "Session expired.");
        }
        if (!res.ok) {
          throw new Error(ed(data) || "Request failed.");
        }
        return data;
      },
    };

    return { format, store, api };
  }

  /**
   * Phase 4: DOM-safe pure helpers + format bundle for classic scripts and future bundles.
   * Does not replace app.js fallbacks when Phase 2 core is missing.
   */
  function createWorkspacePureHelpers(globalRef) {
    const g = globalRef || global;
    const core =
      typeof g.createPhase2Core === "function"
        ? g.createPhase2Core({
            fetchImpl: typeof g.fetch === "function" ? g.fetch.bind(g) : null,
          })
        : null;
    const format = core?.format;

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function setText(el, value) {
      if (el) el.textContent = String(value ?? "");
    }

    function detailFromApiBody(data) {
      if (format?.detailFromApiBody) return format.detailFromApiBody(data);
      const d = data && data.detail;
      if (typeof d === "string") return d;
      if (Array.isArray(d) && d.length && typeof d[0]?.msg === "string") return d[0].msg;
      return "";
    }

    return { format, escapeHtml, setText, detailFromApiBody, core };
  }

  global.createPhase2Core = createPhase2Core;
  global.createWorkspacePureHelpers = createWorkspacePureHelpers;
})(typeof globalThis !== "undefined" ? globalThis : window);
