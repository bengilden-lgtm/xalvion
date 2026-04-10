/**
 * Pure decision / payload shaping and string formatting for the sidepanel.
 * No DOM, no Chrome APIs — safe to reuse from tests or other bundles.
 */

export function getDecisionData(data) {
  if (!data || typeof data !== "object") return {};
  return data.sovereign_decision && typeof data.sovereign_decision === "object"
    ? data.sovereign_decision
    : data.decision && typeof data.decision === "object"
      ? data.decision
      : {};
}

export function getTriageData(data) {
  if (!data || typeof data !== "object") return {};
  return data.triage_metadata && typeof data.triage_metadata === "object"
    ? data.triage_metadata
    : data.triage && typeof data.triage === "object"
      ? data.triage
      : {};
}

export function getImpactData(data) {
  if (!data || typeof data !== "object") return {};
  return data.impact_projections && typeof data.impact_projections === "object"
    ? data.impact_projections
    : data.impact && typeof data.impact === "object"
      ? data.impact
      : {};
}

export function getHistoryData(data) {
  if (!data || typeof data !== "object") return {};
  return data.memory_delta && typeof data.memory_delta === "object"
    ? data.memory_delta
    : data.history && typeof data.history === "object"
      ? data.history
      : {};
}

export function getThinkingTrace(data) {
  return Array.isArray(data?.thinking_trace) ? data.thinking_trace : [];
}

export function normalize(value) {
  return typeof value === "string" ? value.trim() : "";
}

/** True when `/analyze` JSON is safe to pass into the sidepanel renderer (object payload). */
export function isRenderableAnalyzePayload(data) {
  return data != null && typeof data === "object" && !Array.isArray(data);
}

export function safe(value, fallback = "-") {
  const v = normalize(String(value ?? ""));
  return v || fallback;
}

/**
 * Aligned with `format.deriveConsequencePresentation` in workspace_modules.js
 * and the previous inline implementation in sidepanel.js.
 */
export function deriveConsequencePresentation(data) {
  if (!data || typeof data !== "object") data = {};
  const dec = getDecisionData(data);
  const triage = getTriageData(data);
  const risk = String(dec.risk_level || triage.risk_level || data.risk_level || "").toLowerCase();
  if (risk === "high") {
    return {
      cls: "signal-high-risk",
      text: "⚠ High risk",
      title: "Elevated risk — review before customer send",
    };
  }
  const tier = String(data.execution_tier || "").toLowerCase();
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
      title: "Awaiting operator approval",
    };
  }
  const action = String(dec.action || data.action || "none").toLowerCase();
  const actionRisk = String(dec.risk_level || triage.risk_level || "medium").toLowerCase();
  const req = Boolean(data.requires_approval || dec.requires_approval || data.decision_state === "pending_decision");
  const money = action === "refund" || action === "charge" || action === "credit";
  if (req && money) return { cls: "signal-approval", text: "⚡ Approval required", title: "" };
  if (action === "review" || actionRisk === "high" || actionRisk === "medium") {
    return { cls: "signal-review", text: "⚠ Review recommended", title: "" };
  }
  return { cls: "signal-safe", text: "✓ Safe to send", title: "" };
}

export function approvalGateActive(data) {
  const dec = getDecisionData(data);
  const pres = deriveConsequencePresentation(data);
  return (
    Boolean(dec.requires_approval || data.requires_approval) ||
    pres.cls === "signal-approval" ||
    pres.cls === "signal-high-risk" ||
    pres.cls === "signal-review"
  );
}

export function getApprovalCompactCopyText(data) {
  const dec = getDecisionData(data);
  const pres = deriveConsequencePresentation(data);
  if (pres.cls === "signal-high-risk") {
    return "High risk — hold or edit until you are satisfied.";
  }
  if (dec.requires_approval || data.requires_approval || pres.cls === "signal-approval") {
    return "Approval-class motion — confirm the customer-ready text before copy or insert.";
  }
  return "Review posture — skim brief and reply before sending.";
}

export function inferDisplayAction(data, reply, issueType) {
  const decision = getDecisionData(data);
  const raw = normalize(decision.action || data.action);
  if (raw) return raw;
  if (issueType === "shipping_issue" && reply) return "Inform";
  if (reply) return "Reply";
  return "";
}

export function inferExecutionPayload(data, reply, issueType) {
  if (data?.execution && typeof data.execution === "object") {
    return data.execution;
  }

  const decision = getDecisionData(data);
  const impact = getImpactData(data);
  const displayAction = inferDisplayAction(data, reply, issueType);
  const toolStatus = normalize(decision.tool_status || data.tool_status);

  let label = "-";
  if (toolStatus === "success" && displayAction && displayAction !== "Reply" && displayAction !== "Inform") {
    label = `${displayAction.charAt(0).toUpperCase()}${displayAction.slice(1)} executed`;
  } else if (issueType === "shipping_issue" && reply) {
    label = "Tracking response prepared";
  } else if (reply) {
    label = "Reply prepared";
  }

  const detailParts = [];
  if (toolStatus) detailParts.push(`Tool: ${toolStatus}`);
  if (impact?.agent_minutes_saved) detailParts.push(`Saved ${impact.agent_minutes_saved} min`);

  return {
    label,
    detail: detailParts.join(" • "),
    mode: normalize(data.mode),
    auto_resolved: Boolean(impact?.auto_resolved),
    requires_approval: Boolean(decision?.requires_approval),
  };
}

export function formatStatus(status) {
  const s = normalize(status).toLowerCase();

  if (!s) return "";
  if (s === "resolved") return "Resolved";
  if (s === "pending") return "Pending";
  if (s === "escalated") return "Escalated";
  if (s === "ignored") return "Ignored";
  if (s === "waiting") return "Waiting";

  return s
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function formatMode(mode) {
  const m = normalize(mode).toLowerCase();

  if (!m) return "-";
  if (m === "auto" || m === "policy_auto") return "Auto Execution";
  if (m === "manual_review") return "Review Required";
  if (m === "escalation") return "Escalated";
  if (m === "skip") return "Skipped";
  if (m === "assist") return "Assist";
  if (m === "ai_policy") return "AI + Policy";
  if (m === "fallback") return "Fallback";

  return m
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function formatImpact(impact) {
  if (!impact || typeof impact !== "object") return "";

  const lines = [];

  if (impact.resolution_speed) {
    const speed =
      String(impact.resolution_speed).charAt(0).toUpperCase() +
      String(impact.resolution_speed).slice(1);
    lines.push(`• Resolution: ${speed}`);
  }

  if (impact.agent_minutes_saved !== undefined && impact.agent_minutes_saved !== null) {
    lines.push(`• Agent time saved: ${impact.agent_minutes_saved} min`);
  }

  if (impact.cost_avoided !== undefined && impact.cost_avoided !== null) {
    lines.push(`• Cost avoided: $${Number(impact.cost_avoided).toFixed(2)}`);
  }

  if (impact.money_saved !== undefined && impact.money_saved !== null && Number(impact.money_saved) > 0) {
    lines.push(`• Value captured: $${Number(impact.money_saved).toFixed(2)}`);
  }

  return lines.join("\n");
}

export function formatSignals(impact) {
  if (!impact || typeof impact !== "object" || !Array.isArray(impact.signals)) return "";
  return impact.signals.map((s) => `• ${s}`).join("\n");
}

export function formatDecisionTrace(decisionTrace) {
  if (!Array.isArray(decisionTrace) || decisionTrace.length === 0) return "";
  return decisionTrace.map((s) => `• ${s}`).join("\n");
}

export function formatMemorySummary(memorySummary) {
  if (!memorySummary) return "";
  if (typeof memorySummary === "string") return memorySummary;

  const lines = [];
  if (memorySummary.summary) lines.push(`• ${memorySummary.summary}`);
  if (memorySummary.pattern) lines.push(`• Pattern: ${memorySummary.pattern}`);
  if (memorySummary.samples !== undefined) lines.push(`• Samples: ${memorySummary.samples}`);
  if (memorySummary.avg_confidence !== undefined) lines.push(`• Avg confidence: ${memorySummary.avg_confidence}`);
  if (memorySummary.same_action_rate !== undefined) lines.push(`• Same action rate: ${memorySummary.same_action_rate}`);
  if (memorySummary.issue_count !== undefined) lines.push(`• Similar issues: ${memorySummary.issue_count}`);
  if (memorySummary.same_action_count !== undefined) lines.push(`• Same action path: ${memorySummary.same_action_count}`);
  return lines.join("\n");
}

export function formatSessionImpact(sessionImpact) {
  if (!sessionImpact || typeof sessionImpact !== "object") return "";

  const lines = [];
  if (sessionImpact.tickets_seen !== undefined) lines.push(`• Tickets seen: ${sessionImpact.tickets_seen}`);
  if (sessionImpact.tickets_resolved !== undefined) lines.push(`• Tickets resolved: ${sessionImpact.tickets_resolved}`);
  if (sessionImpact.agent_minutes_saved !== undefined) lines.push(`• Agent minutes saved: ${sessionImpact.agent_minutes_saved}`);
  if (sessionImpact.value_generated !== undefined) lines.push(`• Value generated: $${Number(sessionImpact.value_generated).toFixed(2)}`);
  if (sessionImpact.avg_confidence !== undefined) lines.push(`• Avg confidence: ${sessionImpact.avg_confidence}`);
  return lines.join("\n");
}

/** Width percent (0–100) for the confidence meter from a raw confidence scalar. */
export function confidenceMeterPercent(conf) {
  let val = Number(conf);
  if (!Number.isFinite(val)) val = 0;
  return Math.max(0, Math.min(100, Math.round(val * 100)));
}

/**
 * Operator brief lines as structured data; sidepanel appends DOM rows.
 */
export function buildOperatorBriefLines(data) {
  const decision = getDecisionData(data);
  const triage = getTriageData(data);
  const impact = getImpactData(data);
  const issueType = normalize(data.issue_type || data.type);
  const reply = normalize(data.reply || data.response || data.final);
  const action = inferDisplayAction(data, reply, issueType);
  const status = formatStatus(normalize(decision.status || data.status)) || "—";
  const queue = normalize(String(decision.queue ?? data.queue ?? "")) || "—";
  const risk = normalize(String(decision.risk_level ?? triage.risk_level ?? data.risk_level ?? "")) || "—";
  const confRaw = decision.confidence ?? data.confidence;
  let conf = "—";
  if (confRaw !== "" && confRaw !== undefined && confRaw !== null) {
    const n = Number(confRaw);
    conf = Number.isFinite(n) ? n.toFixed(2) : String(confRaw);
  }
  const execTier = normalize(String(data.execution_tier || data.execution?.tier || ""));
  const requiresApproval = Boolean(decision.requires_approval || data.requires_approval || data.execution?.requires_approval);
  const governorReason = normalize(String(data.governor_reason || decision.governor_reason || ""));
  const timeSaved = impact?.agent_minutes_saved ? `${impact.agent_minutes_saved} min` : "";

  const posture =
    requiresApproval
      ? "Approval gate active — operator release required"
      : execTier
        ? `Execution tier: ${execTier.replace(/_/g, " ")}`
        : "No approval gate — standard operator verification";

  const operatorCheck = requiresApproval
    ? "Confirm customer-safe wording + money/policy facts, then approve or reject."
    : "Skim for factual correctness, then copy/insert.";

  return [
    { label: "Mission", value: `${safe(action)} · ${safe(issueType)}${timeSaved ? ` · est. ${timeSaved} saved` : ""}` },
    { label: "Posture", value: posture },
    { label: "Status · queue", value: `${status} · ${queue}` },
    { label: "Risk · confidence", value: `${risk} · ${conf}` },
    ...(governorReason ? [{ label: "Governor", value: governorReason }] : []),
    { label: "Operator check", value: operatorCheck },
  ];
}
