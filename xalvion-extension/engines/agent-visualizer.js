/**
 * Explainability shaping, header insight copy, and thinking-step UI helpers (DOM updates only where passed in).
 */

import {
  formatImpact,
  formatMemorySummary,
  formatMode,
  formatSessionImpact,
  formatSignals,
  getDecisionData,
  getHistoryData,
  inferDisplayAction,
  normalize,
} from "../utils/decision-formatters.js";

export function toBullets(value) {
  if (!value) return "";
  if (typeof value === "string") return value.trim();
  if (Array.isArray(value)) {
    return value.map((item) => `• ${String(item ?? "").trim()}`).filter(Boolean).join("\n");
  }
  if (typeof value === "object") {
    return Object.entries(value)
      .filter(([, v]) => v !== null && v !== undefined && String(v).trim() !== "")
      .map(([k, v]) => `• ${k.replace(/_/g, " ")}: ${v}`)
      .join("\n");
  }
  return String(value);
}

export function buildExplainabilityFallback(data) {
  const sections = {};

  if (data.reason || data.policy_rule || data.ai_summary) {
    sections.decision = [
      data.reason ? `Reason: ${data.reason}` : "",
      data.policy_rule ? `Policy rule: ${data.policy_rule}` : "",
      data.ai_summary ? `AI summary: ${data.ai_summary}` : "",
    ]
      .filter(Boolean)
      .join("\n");
  }

  if (data.confidence !== undefined || data.risk_level || data.priority) {
    sections.confidence = [
      data.confidence !== undefined && data.confidence !== null && data.confidence !== ""
        ? `Model confidence: ${data.confidence}`
        : "",
      data.priority ? `Priority: ${data.priority}` : "",
      data.risk_level ? `Risk level: ${data.risk_level}` : "",
    ]
      .filter(Boolean)
      .join("\n");
  }

  if (data.memory_summary) {
    sections.learning = formatMemorySummary(data.memory_summary);
  }

  if (data.execution) {
    sections.execution = [
      data.execution.label ? data.execution.label : "",
      data.execution.detail ? data.execution.detail : "",
      data.execution.mode ? `Mode: ${formatMode(data.execution.mode)}` : "",
    ]
      .filter(Boolean)
      .join("\n");
  }

  if (data.impact || data.signals) {
    sections.impact = [formatImpact(data.impact), formatSignals(data.impact)].filter(Boolean).join("\n");
  }

  if (data.session_impact) {
    sections.session = formatSessionImpact(data.session_impact);
  }

  return sections;
}

export function normalizeExplainability(data) {
  const explainability =
    data && typeof data.explainability === "object" && data.explainability ? data.explainability : {};
  const fallback = buildExplainabilityFallback(data);

  const sections = {
    decision: explainability.decision || explainability.policy || fallback.decision || "",
    confidence: explainability.confidence || explainability.confidence_context || fallback.confidence || "",
    learning: explainability.learning || explainability.memory || fallback.learning || "",
    execution: explainability.execution || explainability.execution_rationale || fallback.execution || "",
    impact: explainability.impact || explainability.impact_narrative || fallback.impact || "",
    session: explainability.session || explainability.session_context || fallback.session || "",
  };

  const summary =
    normalize(data.explainability_summary) ||
    normalize(explainability.summary) ||
    normalize(data.reason) ||
    "Decision confidence, policy fit, learned behavior, and execution rationale.";

  return { summary, sections };
}

/**
 * Fold API shapes `decision_explainability` and `decision_explanation` into
 * `data.explainability` so a single panel (`renderExplainabilitySections`) renders them.
 */
export function applyStructuredExplainabilityToData(data) {
  if (!data || typeof data !== "object") return data;
  const out = { ...data };
  const lines = [];

  const op = out.decision_explainability;
  if (op && typeof op === "object") {
    if (op.classification?.signal) lines.push(String(op.classification.signal));
    if (op.risk_reasoning?.signal) lines.push(String(op.risk_reasoning.signal));
    if (op.policy_trigger?.signal) lines.push(String(op.policy_trigger.signal));
    if (op.memory_influence?.signal) lines.push(String(op.memory_influence.signal));
    if (op.outcome_expectation?.signal) lines.push(String(op.outcome_expectation.signal));
    if (op.why_not_other_actions) lines.push(String(op.why_not_other_actions));
    if (op.summary) lines.push(String(op.summary));
  }

  const leg = out.decision_explanation;
  if (leg && typeof leg === "object") {
    if (leg.issue_classification?.signal) lines.push(String(leg.issue_classification.signal));
    if (leg.risk_assessment?.signal) lines.push(String(leg.risk_assessment.signal));
    if (leg.policy_influence?.signal) lines.push(String(leg.policy_influence.signal));
    if (leg.memory_influence?.signal) lines.push(String(leg.memory_influence.signal));
    if (leg.approval_rationale?.reason) lines.push(String(leg.approval_rationale.reason));
    if (leg.summary) lines.push(String(leg.summary));
  }

  const block = lines.join("\n");
  if (!block) return out;

  const ex = out.explainability && typeof out.explainability === "object" ? { ...out.explainability } : {};
  const baseDecision = ex.decision || ex.policy || "";
  ex.decision = [baseDecision, block].filter(Boolean).join("\n\n");
  out.explainability = ex;
  return out;
}

export function buildHeaderInsight(data) {
  const decision = getDecisionData(data);
  const history = getHistoryData(data);
  const issueType = normalize(data.issue_type || data.type).toLowerCase();
  const status = normalize(decision.status || data.status).toLowerCase();
  const action = inferDisplayAction(data, normalize(data.reply), issueType);
  const confidence = Number(decision.confidence ?? data.confidence);
  const samples =
    Number(history.samples) ||
    Number(history.same_action_count) ||
    Number(history.issue_count) ||
    0;

  if (issueType === "shipping_issue" && normalize(data.reply)) {
    return "Shipping context verified and a customer-safe tracking reply is ready.";
  }

  if (status === "resolved" && action && samples > 0 && Number.isFinite(confidence) && confidence > 0) {
    return `Resolved using ${samples} similar past tickets at ${confidence.toFixed(2)} confidence.`;
  }

  if (status === "resolved" && action) {
    return `High-confidence path selected: ${action}.`;
  }

  if ((status === "waiting" || status === "pending") && action) {
    return `Decision prepared: ${action}. Human review is still required.`;
  }

  if (status === "escalated") {
    return "Escalated for review because this case falls outside the low-risk automation path.";
  }

  return "Decision prepared using ticket context, policy fit, and learned behavior.";
}

export function resetThinkingSteps(thinkingSteps, thinkingSubtitle) {
  if (!thinkingSteps?.length) return;
  thinkingSteps.forEach((step) => {
    step.classList.remove("active", "done");
    const status = step.querySelector(".thinking-step-status");
    if (status) status.textContent = "Queued";
  });
  if (thinkingSubtitle) {
    thinkingSubtitle.textContent = "Xalvion is reading the ticket, checking policy, and preparing the next step.";
  }
}

export function setThinkingStep(thinkingSteps, index, state, subtitle, thinkingSubtitle) {
  const step = thinkingSteps[index];
  if (!step) return;

  step.classList.remove("active", "done");
  if (state === "active") {
    step.classList.add("active");
  }
  if (state === "done") {
    step.classList.add("done");
  }

  const status = step.querySelector(".thinking-step-status");
  if (status) {
    if (state === "active") status.textContent = "Running";
    else if (state === "done") status.textContent = "Done";
    else status.textContent = "Queued";
  }

  if (subtitle && thinkingSubtitle) {
    thinkingSubtitle.textContent = subtitle;
  }
}

export function buildThinkingSequence(mode = "single") {
  return mode === "inbox"
    ? [
        { index: 0, status: "Reading inbox...", subtitle: "Capturing visible threads from the page." },
        { index: 1, status: "Classifying visible tickets...", subtitle: "Understanding likely intent across multiple conversations." },
        { index: 2, status: "Matching policy...", subtitle: "Checking best-fit policy paths across the inbox." },
        { index: 3, status: "Checking memory patterns...", subtitle: "Comparing multiple decisions against prior learned outcomes." },
        { index: 4, status: "Building inbox summary...", subtitle: "Preparing workload totals, risk flags, and automation opportunities." },
      ]
    : [
        { index: 0, status: "Reading ticket...", subtitle: "Capturing the current message and context from the page." },
        { index: 1, status: "Classifying intent...", subtitle: "Understanding what the customer needs and how urgent it is." },
        { index: 2, status: "Matching policy...", subtitle: "Checking the best-fit policy path for this request." },
        { index: 3, status: "Checking memory patterns...", subtitle: "Comparing against prior decisions and learned outcomes." },
        { index: 4, status: "Finalizing decision...", subtitle: "Preparing the reply, action, and confidence summary." },
      ];
}
