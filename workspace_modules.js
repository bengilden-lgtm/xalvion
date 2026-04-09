(function (global) {
  "use strict";

  /**
   * Shared fetch/format helpers for the workspace. Phase 2 operator chrome (rails, decision hierarchy,
   * monetization surfaces) lives in app.js + styles.css; extend this module only when a shared primitive
   * is required across bundles.
   */

  global.__XALVION_WORKSPACE_MODULES__ = global.__XALVION_WORKSPACE_MODULES__ || {};

  /**
   * Workspace Auth/Storage primitives
   * Owner: frontend/auth
   *
   * Purpose:
   * - Provide stable primitives for `app.js` without changing routes/IDs/UI structure.
   * - Keep `app.js` as an orchestrator by moving reusable auth/storage behaviors here.
   */
  function createWorkspaceAuthPrimitives(config) {
    const cfg = config || {};
    const debug =
      typeof location !== "undefined" &&
      (location.hostname === "localhost" || location.hostname === "127.0.0.1");

    function authDebugLog(label, detail) {
      if (!debug) return;
      try {
        const msg = detail && (detail.message || String(detail));
        if (msg) console.warn(`[xalvion:auth] ${label}`, msg);
        else console.warn(`[xalvion:auth] ${label}`);
      } catch {}
    }

    function storageGet(key, fallback = "") {
      try {
        const v = global.localStorage?.getItem?.(key);
        return v === null || typeof v === "undefined" ? fallback : v;
      } catch {
        return fallback;
      }
    }

    function storageSet(key, value) {
      try {
        global.localStorage?.setItem?.(key, String(value));
      } catch {}
    }

    function storageRemove(key) {
      try {
        global.localStorage?.removeItem?.(key);
      } catch {}
    }

    return {
      authDebugLog,
      storageGet,
      storageSet,
      storageRemove,
      keys: {
        TOKEN_KEY: String(cfg.TOKEN_KEY || "xalvion_token"),
        USER_KEY: String(cfg.USER_KEY || "xalvion_user"),
        TIER_KEY: String(cfg.TIER_KEY || "xalvion_tier"),
      },
    };
  }

  global.__XALVION_WORKSPACE_MODULES__.auth =
    global.__XALVION_WORKSPACE_MODULES__.auth || createWorkspaceAuthPrimitives();

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
      formatOutcomeTier(labelOrTier) {
        const map = {
          excellent: "Excellent outcome",
          good: "Good outcome",
          neutral: "Neutral outcome",
          bad: "Poor outcome",
          unknown: "Outcome unavailable",
        };
        const k = String(labelOrTier || "").toLowerCase();
        return map[k] || (k ? `${k.charAt(0).toUpperCase()}${k.slice(1)} outcome` : "Outcome unavailable");
      },
      formatOutcomeMetricLabel(key) {
        const map = {
          excellent: "Excellent",
          good: "Good",
          neutral: "Neutral",
          bad: "Poor",
          auto_success: "Auto success",
          assisted_success: "Assisted success",
          failed: "Failed",
          ticket_reopened: "Reopened",
          refund_reversed: "Reversed",
          dispute_filed: "Disputes",
          crm_closed: "CRM closed",
          money_refunded: "Refunded",
          money_credited: "Credited",
        };
        const k = String(key || "").toLowerCase();
        if (map[k]) return map[k];
        return k ? k.replaceAll("_", " ").replace(/\b\w/g, (m) => m.toUpperCase()) : "";
      },
      formatPatternKey(patternKey) {
        const raw = String(patternKey || "").trim();
        if (!raw) return "";
        // Expected format from learning.py: issue:action:risk:tier
        const parts = raw.split(":");
        if (parts.length === 4) {
          const [issue, action, risk, tier] = parts;
          const issueLabel = String(issue || "").replaceAll("_", " ");
          return `${issueLabel}:${action}:${risk}:${tier}`;
        }
        return raw;
      },
      normalizeOutcomeIntelligence(data) {
        const d = data && typeof data === "object" ? data : {};
        const latest = d.latest && typeof d.latest === "object" ? d.latest : null;
        const summary = d.summary && typeof d.summary === "object" ? d.summary : {};
        const insights = Array.isArray(d.insights) ? d.insights.filter((x) => typeof x === "string" && x.trim()) : [];
        const bestPattern = d.best_pattern && typeof d.best_pattern === "object" ? d.best_pattern : null;
        const safeLatest =
          latest && typeof latest === "object"
            ? {
                headline: String(latest.headline || "").trim(),
                tier: String(latest.tier || "unknown").toLowerCase(),
                score: latest.score === null || typeof latest.score === "undefined" ? null : Number(latest.score),
                badges: Array.isArray(latest.badges) ? latest.badges.map((b) => String(b || "").trim()).filter(Boolean).slice(0, 6) : [],
                money: {
                  refund: Number(latest.money?.refund || 0) || 0,
                  credit: Number(latest.money?.credit || 0) || 0,
                },
                flags: latest.flags && typeof latest.flags === "object" ? latest.flags : {},
              }
            : null;

        const coerceNum = (v) => {
          const n = Number(v);
          return Number.isFinite(n) ? n : 0;
        };

        const safeSummary = {
          excellent: Math.max(0, Math.floor(coerceNum(summary.excellent))),
          good: Math.max(0, Math.floor(coerceNum(summary.good))),
          neutral: Math.max(0, Math.floor(coerceNum(summary.neutral))),
          bad: Math.max(0, Math.floor(coerceNum(summary.bad))),
          auto_success: Math.max(0, Math.floor(coerceNum(summary.auto_success))),
          assisted_success: Math.max(0, Math.floor(coerceNum(summary.assisted_success))),
          failed: Math.max(0, Math.floor(coerceNum(summary.failed))),
          ticket_reopened: Math.max(0, Math.floor(coerceNum(summary.ticket_reopened))),
          refund_reversed: Math.max(0, Math.floor(coerceNum(summary.refund_reversed))),
          dispute_filed: Math.max(0, Math.floor(coerceNum(summary.dispute_filed))),
          crm_closed: Math.max(0, Math.floor(coerceNum(summary.crm_closed))),
          money_refunded: Math.max(0, coerceNum(summary.money_refunded)),
          money_credited: Math.max(0, coerceNum(summary.money_credited)),
        };

        const safeBest =
          bestPattern
            ? {
                pattern_key: String(bestPattern.pattern_key || "").trim(),
                expectation: String(bestPattern.expectation || "medium").toLowerCase(),
                ema_score: bestPattern.ema_score === null || typeof bestPattern.ema_score === "undefined" ? null : Number(bestPattern.ema_score),
                sample_count: Math.max(0, Math.floor(coerceNum(bestPattern.sample_count))),
              }
            : null;

        return {
          latest: safeLatest,
          summary: safeSummary,
          insights: insights.slice(0, 3),
          bestPattern: safeBest,
        };
      },
      formatOutcomeSummaryLine(snapshot) {
        const d = snapshot && typeof snapshot === "object" ? snapshot : {};
        const s = d.summary && typeof d.summary === "object" ? d.summary : {};
        const ex = Number(s.excellent || 0) || 0;
        const g = Number(s.good || 0) || 0;
        const n = Number(s.neutral || 0) || 0;
        const b = Number(s.bad || 0) || 0;
        const total = ex + g + n + b;
        if (total <= 0) return "";
        const bits = [];
        if (ex) bits.push(`${ex} excellent`);
        if (g) bits.push(`${g} good`);
        if (b) bits.push(`${b} poor`);
        if (!bits.length) bits.push(`${n} neutral`);
        return `Recent outcomes: ${bits.join(" · ")}`;
      },
      /**
       * Compact trust copy for a single operator decision. Uses only normalized outcome ledger
       * fields and live governor / gate context — no invented benchmarks.
       */
      buildDecisionTrustPresentation(resultData, outcomeRaw) {
        function safetyVerdictFallback(dataObj, gate) {
          const c = Number(dataObj.confidence || 0);
          if (gate) {
            return "Financial or policy gate is active — only an explicit approval releases execution.";
          }
          if (c > 0 && c < 0.62) {
            return "Model confidence is modest — scan triage signals before you send.";
          }
          return "No approval gate on this run — still apply your normal operator standard.";
        }

        const d = resultData && typeof resultData === "object" ? resultData : {};
        const dec = d.sovereign_decision && typeof d.sovereign_decision === "object" ? d.sovereign_decision : d.decision || {};
        const ticket = d.ticket || {};
        const actionLog = d.action_log || ticket.action_log || {};
        const requiresApproval = Boolean(
          d.requires_approval ||
            dec.requires_approval ||
            d.execution?.requires_approval ||
            ticket.requires_approval ||
            actionLog.requires_approval
        );
        const approved = Boolean(ticket.approved || actionLog.approved);
        const pendingGate = requiresApproval && !approved;

        const rawOi =
          outcomeRaw !== undefined && outcomeRaw !== null
            ? outcomeRaw
            : d.outcome_intelligence && typeof d.outcome_intelligence === "object"
              ? d.outcome_intelligence
              : null;
        const norm =
          rawOi && format.normalizeOutcomeIntelligence ? format.normalizeOutcomeIntelligence(rawOi) : null;
        const summary = norm && norm.summary && typeof norm.summary === "object" ? norm.summary : {};
        const best = norm && norm.bestPattern && typeof norm.bestPattern === "object" ? norm.bestPattern : null;

        const gov = format.deriveGovernorPresentation(d);
        const consec = format.deriveConsequencePresentation(d);

        const autoOk = Math.max(0, Math.floor(Number(summary.auto_success || 0) || 0));
        const assistedOk = Math.max(0, Math.floor(Number(summary.assisted_success || 0) || 0));
        const failed = Math.max(0, Math.floor(Number(summary.failed || 0) || 0));
        const reopened = Math.max(0, Math.floor(Number(summary.ticket_reopened || 0) || 0));
        const successDenom = autoOk + assistedOk + failed;
        const reopenDenom = autoOk + assistedOk + reopened;

        const microLines = [];
        const sampleN = best && Number(best.sample_count) > 0 ? Math.floor(Number(best.sample_count)) : 0;
        if (sampleN > 0) {
          microLines.push({
            key: "similar",
            label: "Comparable cases",
            value: `${sampleN} in your pattern library`,
          });
        }
        if (successDenom >= 5) {
          const pct = Math.round((100 * (autoOk + assistedOk)) / successDenom);
          microLines.push({
            key: "success",
            label: "Recorded success",
            value: `${pct}% (${autoOk + assistedOk}/${successDenom} outcomes)`,
          });
        }
        if (reopened > 0 && reopenDenom >= 3) {
          const rpct = Math.round((100 * reopened) / reopenDenom);
          microLines.push({
            key: "reopen",
            label: "Reopen rate (ledger)",
            value: `${rpct}% (${reopened}/${reopenDenom})`,
          });
        } else if (reopened > 0) {
          microLines.push({
            key: "reopen",
            label: "Reopens logged",
            value: `${reopened} in workspace ledger`,
          });
        }

        const hasLedger =
          norm &&
          (sampleN > 0 ||
            successDenom > 0 ||
            reopened > 0 ||
            autoOk > 0 ||
            assistedOk > 0 ||
            failed > 0);
        const ledgerSparse = !hasLedger;

        let verdict = "";
        let posture = "";
        if (gov.mode === "blocked") {
          verdict = "Review required before any customer-facing send.";
          posture = gov.summary || gov.title || "Governor blocked this path under policy.";
        } else if (pendingGate) {
          verdict = "Controlled release — explicit approval is warranted for this motion.";
          posture =
            gov.summary ||
            gov.title ||
            "A financial or policy-sensitive action is staged; the operator gate stays closed until you approve.";
        } else if (gov.mode === "review") {
          verdict = "Governor marked this path for operator review before execution.";
          posture =
            gov.summary ||
            gov.title ||
            "Policy or risk posture requires human sign-off even when no billing gate is open.";
        } else if (gov.mode === "auto") {
          verdict = "Governor clearance — forward motion matches automation-safe criteria.";
          posture = gov.summary || gov.title || "No blocking policy signals on this path.";
        } else if (String(consec.cls || "").includes("signal-safe")) {
          verdict = "Low execution risk on this path — routine verification is sufficient.";
          posture = safetyVerdictFallback(d, pendingGate);
        } else if (String(consec.cls || "").includes("signal-approval")) {
          verdict = "Approval discipline applies — treat execution as consequential.";
          posture = safetyVerdictFallback(d, pendingGate);
        } else if (String(consec.cls || "").includes("signal-high-risk") || String(consec.cls || "").includes("blocked")) {
          verdict = "Elevated risk — hold the line until you reconcile the signals.";
          posture = safetyVerdictFallback(d, pendingGate);
        } else {
          verdict = "Standard operator verification — read once, then proceed.";
          posture = safetyVerdictFallback(d, pendingGate);
        }

        let ledgerHint = "";
        if (ledgerSparse) {
          ledgerHint = "Outcome ledger is thin here — calibration is from live policy, governor, and this case.";
        } else if (!ledgerSparse && successDenom < 5) {
          ledgerHint = "Historical success rate appears once at least five outcomes are recorded in the ledger.";
        }

        return {
          microLines: microLines.slice(0, 4),
          verdict,
          posture,
          ledgerHint,
          ledgerSparse,
        };
      },
      /**
       * Trust Dominance Layer — compact horizontal strip under a decision title.
       * Uses only real outcome_store aggregates (when sample threshold met) and deterministic
       * expectation/memory factors (no fake stats).
       */
      buildTrustDominanceStrip(resultData) {
        const d = resultData && typeof resultData === "object" ? resultData : {};
        const dec =
          d.sovereign_decision && typeof d.sovereign_decision === "object"
            ? d.sovereign_decision
            : d.decision && typeof d.decision === "object"
              ? d.decision
              : {};

        const td = d.trust_dominance && typeof d.trust_dominance === "object" ? d.trust_dominance : null;

        const similar = (() => {
          const v = td?.similar_case_count ?? dec.similar_case_count;
          const n = Math.floor(Number(v || 0));
          return Number.isFinite(n) && n > 0 ? n : 0;
        })();

        const sr = (() => {
          const v = td?.historical_success_rate ?? dec.historical_success_rate;
          const n = Number(v);
          return Number.isFinite(n) && n >= 0 && n <= 1 ? n : null;
        })();

        const rr = (() => {
          const v = dec.historical_reopen_rate;
          const n = Number(v);
          return Number.isFinite(n) && n >= 0 && n <= 1 ? n : null;
        })();

        const reopenRisk = String(td?.reopen_risk || "").toLowerCase() || "unknown";
        const band = String(td?.outcome_confidence_band || "").toLowerCase() || "uncertain";
        const sparse = Boolean(td?.sparse_history || (similar < 5 || sr === null));
        const conservativeNote = sparse ? String(td?.conservative_note || "limited history — conservative decision") : "";

        const severity = (() => {
          const s = String(td?.severity || "").toLowerCase();
          if (s === "safe" || s === "review" || s === "risk") return s;
          // Fallback: infer from reopenRisk + band.
          if (reopenRisk === "high" || band === "uncertain") return "risk";
          if (sr !== null && sr >= 0.88 && (reopenRisk === "low" || reopenRisk === "unknown") && band !== "uncertain" && !sparse) return "safe";
          return "review";
        })();

        const tokens = [];
        if (sr !== null && similar >= 5) {
          tokens.push({ key: "success", label: `${Math.round(sr * 100)}% success`, tone: severity });
        } else {
          tokens.push({ key: "success", label: "Limited history", tone: "review" });
        }
        tokens.push({ key: "cases", label: `based on ${similar || 0} cases`, tone: "review" });
        tokens.push({
          key: "reopen",
          label: `reopen risk: ${reopenRisk === "unknown" ? "—" : reopenRisk}`,
          tone: reopenRisk === "high" ? "risk" : reopenRisk === "low" ? "safe" : "review",
        });
        tokens.push({
          key: "band",
          label: `outcome band: ${band === "tight" ? "tight" : band === "moderate" ? "moderate" : "uncertain"}`,
          tone: band === "tight" ? "safe" : band === "moderate" ? "review" : "risk",
        });

        const why = Array.isArray(td?.why_factors) ? td.why_factors.map((x) => String(x || "").trim()).filter(Boolean) : [];

        return {
          severity,
          tokens: tokens.slice(0, 4),
          conservativeNote,
          why: why.slice(0, 3),
          raw: td,
          rr,
        };
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
          return `You used all ${g} guest preview tickets — the workflow is real. A free account unlocks ${f} tickets/month with saved threads and approval gates.`;
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

    /**
     * Conversion layer helpers (pure, DOM-free).
     * Safe to call from app.js and extension bundles. Keep outputs concise + premium.
     */
    const conversion = (() => {
      const normTier = (t) => {
        const v = String(t || "free").toLowerCase();
        if (v === "guest" || v === "anon" || v === "unauthenticated") return "guest";
        if (v === "free" || v === "pro" || v === "elite" || v === "dev") return v;
        return "free";
      };

      const clampInt = (v) => {
        const n = Math.floor(Number(v || 0));
        return Number.isFinite(n) && n > 0 ? n : 0;
      };

      const clampNum = (v) => {
        const n = Number(v || 0);
        return Number.isFinite(n) && n > 0 ? n : 0;
      };

      const outcomeTone = (latestOutcomeTier) => {
        const t = String(latestOutcomeTier || "").toLowerCase();
        if (t === "excellent") return "premium";
        if (t === "good") return "value";
        if (t === "neutral") return "neutral";
        if (t === "bad") return "urgency";
        return "neutral";
      };

      function buildPlanComparisonHint(tier) {
        const t = normTier(tier);
        if (t === "guest") return "Create a free account to save threads, keep continuity, and expand capacity.";
        if (t === "free") return "Pro unlocks live Stripe execution, higher capacity, and stronger governance surfaces.";
        if (t === "pro") return "Elite adds higher-volume operating capacity, deeper outcome visibility, and team-level controls.";
        return "";
      }

      function buildLockedFeatureNarrative(feature, ctx = {}) {
        const t = normTier(ctx.tier);
        const next = t === "pro" ? "elite" : "pro";
        const nextLabel = next === "elite" ? "View Elite" : "View Pro";
        const stripeConnected = Boolean(ctx.stripeConnected);

        const base = {
          primary: "",
          secondary: "",
          cta: nextLabel,
          tone: "premium",
        };

        switch (String(feature || "").toLowerCase()) {
          case "refund_execution":
            return {
              ...base,
              primary: "Live refund execution is gated on Pro.",
              secondary: stripeConnected
                ? "Pro turns prepared refund decisions into audited Stripe execution — without leaving the operator workspace."
                : "Connect Stripe, then Pro turns prepared refund decisions into audited execution.",
              cta: "Unlock live execution",
              tone: "premium",
            };
          case "advanced_analytics":
            return {
              ...base,
              primary: "Advanced analytics are a higher-tier surface.",
              secondary: "Upgrade to see outcome mix, risk holds, and billing value surfaced — tied back to operator decisions.",
              cta: t === "free" ? "Unlock Pro analytics" : "Unlock Elite analytics",
              tone: "value",
            };
          case "high_capacity":
            return {
              ...base,
              primary: "Higher-volume operating capacity is locked.",
              secondary: "Upgrade for more monthly tickets and fewer mid-shift ceilings — keep approvals and routing continuous.",
              cta: "Add headroom",
              tone: "urgency",
            };
          case "team_ops":
            return {
              ...base,
              primary: "Team-level operating controls are locked.",
              secondary: "Upgrade to scale governed support execution across seats with clearer accountability surfaces.",
              cta: "View team tiers",
              tone: "premium",
            };
          case "outcome_intelligence":
            return {
              ...base,
              primary: "Outcome intelligence deepens on higher tiers.",
              secondary: "Upgrade for stronger outcome visibility and tighter feedback loops — so the operator layer gets measurably better over time.",
              cta: "Unlock outcome intelligence",
              tone: "value",
            };
          default:
            return {
              ...base,
              primary: "This surface is available on a higher tier.",
              secondary: buildPlanComparisonHint(t),
              cta: t === "pro" ? "View Elite" : "View Pro",
              tone: "premium",
            };
        }
      }

      function buildUsagePressureNarrative(ctx = {}) {
        const t = normTier(ctx.tier);
        const atLimit = Boolean(ctx.atLimit);
        const approaching = Boolean(ctx.approachingLimit) && !atLimit;
        const guest = t === "guest";
        const tickets = clampInt(ctx.tickets);
        const money = clampNum(ctx.money);
        const minutes = clampInt(ctx.minutes);

        if (!approaching && !atLimit) return null;

        if (guest && atLimit) {
          return {
            primary: "Guest preview is at capacity.",
            secondary: "Create a free account to keep continuity, save threads, and expand operating runs.",
            cta: "Create free account",
            tone: "urgency",
          };
        }

        if (atLimit) {
          return {
            primary: "This plan is at capacity for the current window.",
            secondary:
              tickets || money || minutes
                ? `You’ve already generated value here — ${tickets ? `${tickets} tickets` : "tickets"}${money ? ` · ${format.formatMoney(money)} surfaced` : ""}${minutes ? ` · ~${minutes} min saved` : ""}. Add headroom to keep execution continuous.`
                : "Add headroom so approvals, routing, and execution don’t stall mid-shift.",
            cta: t === "pro" ? "Add Elite headroom" : "Unlock Pro capacity",
            tone: "urgency",
          };
        }

        return {
          primary: "Approaching this plan’s operating ceiling.",
          secondary:
            tickets || money || minutes
              ? `You’re using real capacity — ${tickets ? `${tickets} tickets` : "tickets"}${money ? ` · ${format.formatMoney(money)} in billing motions` : ""}${minutes ? ` · ~${minutes} min back` : ""}.`
              : "Upgrade before the ceiling so workflows stay uninterrupted.",
          cta: t === "pro" ? "Plan ahead with Elite" : "Upgrade for continuity",
          tone: "neutral",
        };
      }

      function buildPostValueUpgradeNudge(ctx = {}) {
        const t = normTier(ctx.tier);
        if (t !== "free" && t !== "pro") return null;
        const tickets = clampInt(ctx.tickets);
        const money = clampNum(ctx.money);
        const minutes = clampInt(ctx.minutes);
        const actions = clampInt(ctx.actions);
        const outcomeTier = String(ctx.latestOutcomeTier || "").toLowerCase();

        const hasEvidence = tickets >= 4 || actions >= 3 || minutes >= 20 || money >= 75 || outcomeTier === "good" || outcomeTier === "excellent";
        if (!hasEvidence) return null;

        if (t === "free") {
          return {
            primary: "You’re already using Xalvion like an operations layer.",
            secondary: "Pro turns prepared decisions into live execution and gives you uninterrupted capacity.",
            cta: "Unlock Pro",
            tone: "premium",
          };
        }

        return {
          primary: "This workspace is generating measurable value.",
          secondary: "Elite adds higher-volume operating capacity and deeper outcome visibility for serious support teams.",
          cta: "View Elite",
          tone: "premium",
        };
      }

      function buildTierValueNarrative(ctx = {}) {
        const t = normTier(ctx.tier);
        const tickets = clampInt(ctx.tickets);
        const actions = clampInt(ctx.actions);
        const minutes = clampInt(ctx.minutes);
        const money = clampNum(ctx.money);
        const stripeConnected = Boolean(ctx.stripeConnected);
        const refundCenterAllowed = Boolean(ctx.refundCenterAllowed);
        const latestOutcomeTier = String(ctx.latestOutcomeTier || "").toLowerCase();

        const proofBits = [];
        if (tickets) proofBits.push(`${tickets} tickets`);
        if (money) proofBits.push(`${format.formatMoney(money)} surfaced`);
        if (actions) proofBits.push(`${actions} billing motions`);
        if (minutes) proofBits.push(`~${minutes} min saved`);

        const proof = proofBits.length ? proofBits.join(" · ") : "";
        const outcomeLine = latestOutcomeTier && latestOutcomeTier !== "unknown"
          ? `Most recent outcome: ${format.formatOutcomeTier ? format.formatOutcomeTier(latestOutcomeTier) : latestOutcomeTier}.`
          : "";

        if (t === "guest") {
          return {
            primary: proof ? `Workspace value so far: ${proof}.` : "Preview the operator workflow with real controls.",
            secondary: proof
              ? "Create a free account to save threads, keep operator continuity, and expand runs."
              : "Create a free account to save threads and keep operator continuity across runs.",
            cta: "Create free account",
            tone: proof ? "value" : "neutral",
          };
        }

        if (t === "free") {
          const secondary =
            refundCenterAllowed
              ? "Pro unlocks higher capacity and uninterrupted execution."
              : stripeConnected
                ? "Pro turns prepared billing decisions into live Stripe execution — with governance and auditability."
                : "Connect Stripe, then Pro unlocks live execution with governance and auditability.";
          return {
            primary: proof ? `Workspace value so far: ${proof}.` : "Run governed support decisioning with visible risk and approvals.",
            secondary: [outcomeLine, secondary].filter(Boolean).join(" "),
            cta: "Unlock Pro",
            tone: proof ? "value" : outcomeTone(latestOutcomeTier),
          };
        }

        if (t === "pro") {
          return {
            primary: proof ? `Workspace value so far: ${proof}.` : "Live operating tier: governed decisions with execution-ready workflow.",
            secondary: [outcomeLine, "Elite adds higher-volume operating capacity and deeper outcome visibility for serious support orgs."].filter(Boolean).join(" "),
            cta: "View Elite",
            tone: proof ? "premium" : outcomeTone(latestOutcomeTier),
          };
        }

        return {
          primary: proof ? `Workspace value so far: ${proof}.` : "Maximum capacity and premium control surfaces.",
          secondary: outcomeLine,
          cta: "",
          tone: "premium",
        };
      }

      return {
        buildTierValueNarrative,
        buildUsagePressureNarrative,
        buildLockedFeatureNarrative,
        buildPostValueUpgradeNudge,
        buildPlanComparisonHint,
      };
    })();

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

    return { format, store, api, conversion };
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
