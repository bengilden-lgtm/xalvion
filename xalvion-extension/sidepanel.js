const analyzeBtn = document.getElementById("analyze");
const copyBtn = document.getElementById("copyBtn");
const insertBtn = document.getElementById("insertBtn");

const statusBox = document.getElementById("status");
const resultPanel = document.getElementById("resultPanel");
const notePill = document.getElementById("notePill");
const statusBadge = document.getElementById("statusBadge");

const thinkingPanel = document.getElementById("thinkingPanel");
const thinkingSubtitle = document.getElementById("thinkingSubtitle");
const thinkingSteps = Array.from(document.querySelectorAll(".thinking-step"));

const headerInsight = document.getElementById("headerInsight");
const headerInsightValue = document.getElementById("headerInsightValue");
const emptyState = document.getElementById("emptyState");

const statusValue = document.getElementById("statusValue");
const typeValue = document.getElementById("typeValue");
const actionValue = document.getElementById("actionValue");
const confidenceValue = document.getElementById("confidenceValue");
const priorityValue = document.getElementById("priorityValue");
const queueValue = document.getElementById("queueValue");
const riskValue = document.getElementById("riskValue");
const reasonValue = document.getElementById("reasonValue");
const policyValue = document.getElementById("policyValue");
const aiSummaryValue = document.getElementById("aiSummaryValue");
const replyValue = document.getElementById("replyValue");
const confidenceMeter = document.getElementById("confidenceMeter");

const statusCard = document.getElementById("statusCard");
const confidenceCard = document.getElementById("confidenceCard");
const priorityCard = document.getElementById("priorityCard");
const queueCard = document.getElementById("queueCard");
const riskCard = document.getElementById("riskCard");
const reasonCard = document.getElementById("reasonCard");
const policyCard = document.getElementById("policyCard");
const aiSummaryCard = document.getElementById("aiSummaryCard");
const replyCard = document.getElementById("replyCard");

let executionCard = document.getElementById("executionCard");
let executionValue = document.getElementById("executionValue");
let executionDetailValue = document.getElementById("executionDetailValue");

let modeCard = document.getElementById("modeCard");
let modeValue = document.getElementById("modeValue");

let impactCard = document.getElementById("impactCard");
let impactValue = document.getElementById("impactValue");

let signalsCard = document.getElementById("signalsCard");
let signalsValue = document.getElementById("signalsValue");

let decisionTraceCard = document.getElementById("decisionTraceCard");
let decisionTraceValue = document.getElementById("decisionTraceValue");

let memorySummaryCard = document.getElementById("memorySummaryCard");
let memorySummaryValue = document.getElementById("memorySummaryValue");

let sessionImpactCard = document.getElementById("sessionImpactCard");
let sessionImpactValue = document.getElementById("sessionImpactValue");

const explainabilityWrap = document.getElementById("explainabilityWrap");
const explainabilityToggle = document.getElementById("explainabilityToggle");
const explainabilitySummary = document.getElementById("explainabilitySummary");
const explainDecisionCard = document.getElementById("explainDecisionCard");
const explainDecisionValue = document.getElementById("explainDecisionValue");
const explainConfidenceCard = document.getElementById("explainConfidenceCard");
const explainConfidenceValue = document.getElementById("explainConfidenceValue");
const explainLearningCard = document.getElementById("explainLearningCard");
const explainLearningValue = document.getElementById("explainLearningValue");
const explainExecutionCard = document.getElementById("explainExecutionCard");
const explainExecutionValue = document.getElementById("explainExecutionValue");
const explainImpactCard = document.getElementById("explainImpactCard");
const explainImpactValue = document.getElementById("explainImpactValue");
const explainSessionCard = document.getElementById("explainSessionCard");
const explainSessionValue = document.getElementById("explainSessionValue");

let lastReply = "";
let explainabilityOpen = false;
let thinkingRunId = 0;

// ===== MULTI-TICKET UI INJECTION =====
function ensureScanInboxButton() {
  let scanBtn = document.getElementById("scanInbox");
  if (scanBtn) return scanBtn;

  const actions = document.querySelector(".actions");
  if (!actions) return null;

  scanBtn = document.createElement("button");
  scanBtn.id = "scanInbox";
  scanBtn.textContent = "Scan Inbox ⚡";
  scanBtn.style.background = "linear-gradient(135deg, #22c1ff, #0a84ff)";
  scanBtn.style.boxShadow = "0 10px 24px rgba(10,132,255,0.25)";

  const actionsRow = actions.querySelector(".actions-row");
  if (actionsRow) {
    actions.insertBefore(scanBtn, actionsRow);
  } else {
    actions.appendChild(scanBtn);
  }

  return scanBtn;
}

function ensureInboxSummaryPanel() {
  let panel = document.getElementById("inboxSummary");
  let value = document.getElementById("inboxSummaryValue");

  if (panel && value) return { panel, value };

  const content = document.querySelector(".content");
  if (!content) return { panel: null, value: null };

  panel = document.createElement("div");
  panel.id = "inboxSummary";
  panel.className = "insight";
  panel.style.display = "none";

  const label = document.createElement("div");
  label.className = "insight-label";
  label.textContent = "Inbox Summary";

  value = document.createElement("div");
  value.id = "inboxSummaryValue";
  value.className = "insight-value";
  value.textContent = "No inbox scan yet.";

  panel.appendChild(label);
  panel.appendChild(value);

  if (headerInsight && headerInsight.parentNode === content) {
    if (headerInsight.nextSibling) {
      content.insertBefore(panel, headerInsight.nextSibling);
    } else {
      content.appendChild(panel);
    }
  } else {
    content.appendChild(panel);
  }

  return { panel, value };
}

const scanInboxBtn = ensureScanInboxButton();
const inboxSummaryRefs = ensureInboxSummaryPanel();
const inboxSummary = inboxSummaryRefs.panel;
const inboxSummaryValue = inboxSummaryRefs.value;

function showStatus(message, isError = false) {
  if (!statusBox) return;

  if (!message) {
    statusBox.textContent = "";
    statusBox.className = "status";
    return;
  }

  statusBox.textContent = message;
  statusBox.className = isError ? "status show error" : "status show";
}

function showPanel() {
  if (resultPanel) resultPanel.classList.add("show");
}

function hidePanel() {
  if (resultPanel) resultPanel.classList.remove("show");
}


function getDecisionData(data) {
  if (!data || typeof data !== "object") return {};
  return (data.sovereign_decision && typeof data.sovereign_decision === "object")
    ? data.sovereign_decision
    : ((data.decision && typeof data.decision === "object") ? data.decision : {});
}

function getTriageData(data) {
  if (!data || typeof data !== "object") return {};
  return (data.triage_metadata && typeof data.triage_metadata === "object")
    ? data.triage_metadata
    : ((data.triage && typeof data.triage === "object") ? data.triage : {});
}

function getImpactData(data) {
  if (!data || typeof data !== "object") return {};
  return (data.impact_projections && typeof data.impact_projections === "object")
    ? data.impact_projections
    : ((data.impact && typeof data.impact === "object") ? data.impact : {});
}

function getHistoryData(data) {
  if (!data || typeof data !== "object") return {};
  return (data.memory_delta && typeof data.memory_delta === "object")
    ? data.memory_delta
    : ((data.history && typeof data.history === "object") ? data.history : {});
}

function getThinkingTrace(data) {
  return Array.isArray(data?.thinking_trace) ? data.thinking_trace : [];
}

function inferDisplayAction(data, reply, issueType) {
  const decision = getDecisionData(data);
  const raw = normalize(decision.action || data.action);
  if (raw) return raw;
  if (issueType === "shipping_issue" && reply) return "Inform";
  if (reply) return "Reply";
  return "";
}

function inferExecutionPayload(data, reply, issueType) {
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
    requires_approval: Boolean(decision?.requires_approval)
  };
}

function normalize(value) {
  return typeof value === "string" ? value.trim() : "";
}

function safe(value, fallback = "-") {
  const v = normalize(String(value ?? ""));
  return v || fallback;
}

function setVisible(el, visible) {
  if (!el) return;
  el.style.display = visible ? "" : "none";
}

function formatStatus(status) {
  const s = normalize(status).toLowerCase();

  if (!s) return "";
  if (s === "resolved") return "Resolved";
  if (s === "pending") return "Pending";
  if (s === "escalated") return "Escalated";
  if (s === "ignored") return "Ignored";
  if (s === "waiting") return "Waiting";

  return s
    .split("_")
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatMode(mode) {
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
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function updateStatusBadge(status) {
  const s = normalize(status).toLowerCase();

  if (!statusBadge) return;

  if (!s) {
    statusBadge.className = "status-badge hidden";
    return;
  }

  statusBadge.className = `status-badge ${s}`;

  if (s === "resolved") statusBadge.textContent = "Resolved ✓";
  else if (s === "pending") statusBadge.textContent = "Pending";
  else if (s === "escalated") statusBadge.textContent = "Escalated";
  else if (s === "ignored") statusBadge.textContent = "Ignored";
  else statusBadge.textContent = formatStatus(s);
}

function setConfidence(conf) {
  if (!confidenceMeter) return;

  let val = Number(conf);
  if (!Number.isFinite(val)) val = 0;

  const pct = Math.max(0, Math.min(100, Math.round(val * 100)));
  confidenceMeter.style.width = pct + "%";
}

function getGrid() {
  return resultPanel?.querySelector(".grid");
}

function createCard(id, labelText, valueId, options = {}) {
  const grid = getGrid();
  if (!grid) return null;

  const card = document.createElement("div");
  card.className = `card${options.full ? " full" : ""}`;
  card.id = id;

  const label = document.createElement("span");
  label.className = "label";
  label.textContent = labelText;

  const value = document.createElement("div");
  value.className = `value${options.muted ? " muted" : ""}`;
  value.id = valueId;
  value.textContent = "-";

  card.appendChild(label);
  card.appendChild(value);

  if (options.detailId) {
    const detail = document.createElement("div");
    detail.className = "value muted";
    detail.id = options.detailId;
    detail.style.marginTop = "8px";
    detail.textContent = "-";
    card.appendChild(detail);
  }

  grid.appendChild(card);
  return card;
}

function ensureEnterpriseCards() {
  if (!executionCard) {
    executionCard = createCard("executionCard", "Execution", "executionValue", {
      full: true,
      detailId: "executionDetailValue"
    });
    executionValue = document.getElementById("executionValue");
    executionDetailValue = document.getElementById("executionDetailValue");
  }

  if (!modeCard) {
    modeCard = createCard("modeCard", "Mode", "modeValue");
    modeValue = document.getElementById("modeValue");
  }

  if (!impactCard) {
    impactCard = createCard("impactCard", "Impact", "impactValue", {
      full: true
    });
    impactValue = document.getElementById("impactValue");
    if (impactValue) impactValue.classList.add("reply-box");
  }

  if (!signalsCard) {
    signalsCard = createCard("signalsCard", "Signals", "signalsValue", {
      full: true,
      muted: true
    });
    signalsValue = document.getElementById("signalsValue");
    if (signalsValue) signalsValue.classList.add("reply-box");
  }

  if (!decisionTraceCard) {
    decisionTraceCard = createCard("decisionTraceCard", "Decision Trace", "decisionTraceValue", {
      full: true,
      muted: true
    });
    decisionTraceValue = document.getElementById("decisionTraceValue");
    if (decisionTraceValue) decisionTraceValue.classList.add("reply-box");
  }

  if (!memorySummaryCard) {
    memorySummaryCard = createCard("memorySummaryCard", "Memory Summary", "memorySummaryValue", {
      full: true,
      muted: true
    });
    memorySummaryValue = document.getElementById("memorySummaryValue");
    if (memorySummaryValue) memorySummaryValue.classList.add("reply-box");
  }

  if (!sessionImpactCard) {
    sessionImpactCard = createCard("sessionImpactCard", "Session Impact", "sessionImpactValue", {
      full: true,
      muted: true
    });
    sessionImpactValue = document.getElementById("sessionImpactValue");
    if (sessionImpactValue) sessionImpactValue.classList.add("reply-box");
  }
}

function toBullets(value) {
  if (!value) return "";
  if (typeof value === "string") return value.trim();
  if (Array.isArray(value)) {
    return value.map(item => `• ${String(item ?? "").trim()}`).filter(Boolean).join("\n");
  }
  if (typeof value === "object") {
    return Object.entries(value)
      .filter(([, v]) => v !== null && v !== undefined && String(v).trim() !== "")
      .map(([k, v]) => `• ${k.replace(/_/g, " ")}: ${v}`)
      .join("\n");
  }
  return String(value);
}

function formatImpact(impact) {
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

function formatSignals(impact) {
  if (!impact || typeof impact !== "object" || !Array.isArray(impact.signals)) return "";
  return impact.signals.map(s => `• ${s}`).join("\n");
}

function formatDecisionTrace(decisionTrace) {
  if (!Array.isArray(decisionTrace) || decisionTrace.length === 0) return "";
  return decisionTrace.map(s => `• ${s}`).join("\n");
}

function formatMemorySummary(memorySummary) {
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

function formatSessionImpact(sessionImpact) {
  if (!sessionImpact || typeof sessionImpact !== "object") return "";

  const lines = [];
  if (sessionImpact.tickets_seen !== undefined) lines.push(`• Tickets seen: ${sessionImpact.tickets_seen}`);
  if (sessionImpact.tickets_resolved !== undefined) lines.push(`• Tickets resolved: ${sessionImpact.tickets_resolved}`);
  if (sessionImpact.agent_minutes_saved !== undefined) lines.push(`• Agent minutes saved: ${sessionImpact.agent_minutes_saved}`);
  if (sessionImpact.value_generated !== undefined) lines.push(`• Value generated: $${Number(sessionImpact.value_generated).toFixed(2)}`);
  if (sessionImpact.avg_confidence !== undefined) lines.push(`• Avg confidence: ${sessionImpact.avg_confidence}`);
  return lines.join("\n");
}

function renderExecution(execution) {
  if (!execution || typeof execution !== "object") {
    setVisible(executionCard, false);
    setVisible(modeCard, false);
    return;
  }

  const label = safe(execution.label);
  const detail = normalize(execution.detail);
  const mode = formatMode(execution.mode);

  if (executionValue) executionValue.textContent = label;
  if (executionDetailValue) executionDetailValue.textContent = detail || "-";
  if (modeValue) modeValue.textContent = mode;

  setVisible(executionCard, true);
  setVisible(modeCard, true);
}

function renderImpact(impact) {
  const impactText = formatImpact(impact);
  const signalsText = formatSignals(impact);

  if (impactValue) impactValue.textContent = impactText || "-";
  if (signalsValue) signalsValue.textContent = signalsText || "-";

  setVisible(impactCard, !!impactText);
  setVisible(signalsCard, !!signalsText);
}

function renderMetaCards(data) {
  const decisionTraceText = formatDecisionTrace(data.decision_trace);
  const memorySummaryText = formatMemorySummary(data.memory_summary);
  const sessionImpactText = formatSessionImpact(data.session_impact);

  if (decisionTraceValue) decisionTraceValue.textContent = decisionTraceText || "-";
  if (memorySummaryValue) memorySummaryValue.textContent = memorySummaryText || "-";
  if (sessionImpactValue) sessionImpactValue.textContent = sessionImpactText || "-";

  setVisible(decisionTraceCard, !!decisionTraceText);
  setVisible(memorySummaryCard, !!memorySummaryText);
  setVisible(sessionImpactCard, !!sessionImpactText);
}

function buildExplainabilityFallback(data) {
  const sections = {};

  if (data.reason || data.policy_rule || data.ai_summary) {
    sections.decision = [
      data.reason ? `Reason: ${data.reason}` : "",
      data.policy_rule ? `Policy rule: ${data.policy_rule}` : "",
      data.ai_summary ? `AI summary: ${data.ai_summary}` : ""
    ].filter(Boolean).join("\n");
  }

  if (data.confidence !== undefined || data.risk_level || data.priority) {
    sections.confidence = [
      data.confidence !== undefined && data.confidence !== null && data.confidence !== "" ? `Model confidence: ${data.confidence}` : "",
      data.priority ? `Priority: ${data.priority}` : "",
      data.risk_level ? `Risk level: ${data.risk_level}` : ""
    ].filter(Boolean).join("\n");
  }

  if (data.memory_summary) {
    sections.learning = formatMemorySummary(data.memory_summary);
  }

  if (data.execution) {
    sections.execution = [
      data.execution.label ? data.execution.label : "",
      data.execution.detail ? data.execution.detail : "",
      data.execution.mode ? `Mode: ${formatMode(data.execution.mode)}` : ""
    ].filter(Boolean).join("\n");
  }

  if (data.impact || data.signals) {
    sections.impact = [
      formatImpact(data.impact),
      formatSignals(data.impact)
    ].filter(Boolean).join("\n");
  }

  if (data.session_impact) {
    sections.session = formatSessionImpact(data.session_impact);
  }

  return sections;
}

function normalizeExplainability(data) {
  const explainability = data && typeof data.explainability === "object" && data.explainability ? data.explainability : {};
  const fallback = buildExplainabilityFallback(data);

  const sections = {
    decision: explainability.decision || explainability.policy || fallback.decision || "",
    confidence: explainability.confidence || explainability.confidence_context || fallback.confidence || "",
    learning: explainability.learning || explainability.memory || fallback.learning || "",
    execution: explainability.execution || explainability.execution_rationale || fallback.execution || "",
    impact: explainability.impact || explainability.impact_narrative || fallback.impact || "",
    session: explainability.session || explainability.session_context || fallback.session || ""
  };

  const summary =
    normalize(data.explainability_summary) ||
    normalize(explainability.summary) ||
    normalize(data.reason) ||
    "Decision confidence, policy fit, learned behavior, and execution rationale.";

  return { summary, sections };
}

function renderExplainability(data) {
  if (!explainabilityWrap) return;

  const explainability = normalizeExplainability(data);
  const sections = explainability.sections;

  if (explainabilitySummary) {
    explainabilitySummary.textContent = explainability.summary || "Decision confidence, policy fit, learned behavior, and execution rationale.";
  }

  const decisionText = toBullets(sections.decision);
  const confidenceText = toBullets(sections.confidence);
  const learningText = toBullets(sections.learning);
  const executionText = toBullets(sections.execution);
  const impactText = toBullets(sections.impact);
  const sessionText = toBullets(sections.session);

  if (explainDecisionValue) explainDecisionValue.textContent = decisionText || "-";
  if (explainConfidenceValue) explainConfidenceValue.textContent = confidenceText || "-";
  if (explainLearningValue) explainLearningValue.textContent = learningText || "-";
  if (explainExecutionValue) explainExecutionValue.textContent = executionText || "-";
  if (explainImpactValue) explainImpactValue.textContent = impactText || "-";
  if (explainSessionValue) explainSessionValue.textContent = sessionText || "-";

  setVisible(explainDecisionCard, !!decisionText);
  setVisible(explainConfidenceCard, !!confidenceText);
  setVisible(explainLearningCard, !!learningText);
  setVisible(explainExecutionCard, !!executionText);
  setVisible(explainImpactCard, !!impactText);
  setVisible(explainSessionCard, !!sessionText);

  const hasAny = !!(decisionText || confidenceText || learningText || executionText || impactText || sessionText);
  explainabilityWrap.classList.toggle("hidden", !hasAny);
  if (!hasAny) {
    explainabilityWrap.classList.remove("open");
    explainabilityOpen = false;
  }
}

function toggleExplainability(forceOpen = null) {
  if (!explainabilityWrap || explainabilityWrap.classList.contains("hidden")) return;
  explainabilityOpen = typeof forceOpen === "boolean" ? forceOpen : !explainabilityOpen;
  explainabilityWrap.classList.toggle("open", explainabilityOpen);
}

function hideThinkingPanel() {
  if (thinkingPanel) thinkingPanel.classList.remove("show");
}

function resetThinkingSteps() {
  if (!thinkingSteps.length) return;
  thinkingSteps.forEach((step) => {
    step.classList.remove("active", "done");
    const status = step.querySelector(".thinking-step-status");
    if (status) status.textContent = "Queued";
  });
  if (thinkingSubtitle) {
    thinkingSubtitle.textContent = "Xalvion is reading the ticket, checking policy, and preparing the next step.";
  }
}

function startThinkingPanel() {
  resetThinkingSteps();
  if (thinkingPanel) thinkingPanel.classList.add("show");
}

function setThinkingStep(index, state, subtitle = "") {
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

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function playThinkingSequence(runId, mode = "single") {
  const sequence = mode === "inbox"
    ? [
        { index: 0, status: "Reading inbox...", subtitle: "Capturing visible threads from the page." },
        { index: 1, status: "Classifying visible tickets...", subtitle: "Understanding likely intent across multiple conversations." },
        { index: 2, status: "Matching policy...", subtitle: "Checking best-fit policy paths across the inbox." },
        { index: 3, status: "Checking memory patterns...", subtitle: "Comparing multiple decisions against prior learned outcomes." },
        { index: 4, status: "Building inbox summary...", subtitle: "Preparing workload totals, risk flags, and automation opportunities." }
      ]
    : [
        { index: 0, status: "Reading ticket...", subtitle: "Capturing the current message and context from the page." },
        { index: 1, status: "Classifying intent...", subtitle: "Understanding what the customer needs and how urgent it is." },
        { index: 2, status: "Matching policy...", subtitle: "Checking the best-fit policy path for this request." },
        { index: 3, status: "Checking memory patterns...", subtitle: "Comparing against prior decisions and learned outcomes." },
        { index: 4, status: "Finalizing decision...", subtitle: "Preparing the reply, action, and confidence summary." }
      ];

  for (const item of sequence) {
    if (runId !== thinkingRunId) return;
    showStatus(item.status);
    setThinkingStep(item.index, "active", item.subtitle);
    await delay(180);
    if (runId !== thinkingRunId) return;
    setThinkingStep(item.index, "done", item.subtitle);
  }
}

function buildHeaderInsight(data) {
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

function showHeaderInsight(text) {
  if (!headerInsight || !headerInsightValue) return;
  headerInsightValue.textContent = text || "Decision prepared using ticket context, policy fit, and learned behavior.";
  headerInsight.classList.add("show");
}

function hideHeaderInsight() {
  if (!headerInsight || !headerInsightValue) return;
  headerInsight.classList.remove("show");
  headerInsightValue.textContent = "No decision yet.";
}

function showInboxSummary(text) {
  if (!inboxSummary || !inboxSummaryValue) return;
  inboxSummaryValue.textContent = text || "";
  inboxSummary.style.display = "grid";
  inboxSummary.classList.add("show");
}

function hideInboxSummary() {
  if (!inboxSummary || !inboxSummaryValue) return;
  inboxSummaryValue.textContent = "No inbox scan yet.";
  inboxSummary.classList.remove("show");
  inboxSummary.style.display = "none";
}

function ensureDecisionExplanationHost() {
  const panel = document.getElementById("resultPanel");
  const explain = document.getElementById("explainabilityWrap");
  if (!panel) return null;
  let host = document.getElementById("decisionExplanationHost");
  if (host) return host;
  host = document.createElement("div");
  host.id = "decisionExplanationHost";
  const det = document.createElement("details");
  det.className = "explainability-wrap";
  const sum = document.createElement("summary");
  sum.className = "explainability-toggle";
  sum.type = "button";
  const titleCol = document.createElement("div");
  titleCol.className = "explainability-toggle-title";
  const title = document.createElement("div");
  title.className = "explainability-title";
  title.textContent = "Why?";
  titleCol.appendChild(title);
  const preview = document.createElement("div");
  preview.id = "decisionExplanationPreview";
  preview.className = "explainability-summary";
  titleCol.appendChild(preview);
  const chev = document.createElement("div");
  chev.className = "chevron";
  chev.textContent = "⌄";
  sum.appendChild(titleCol);
  sum.appendChild(chev);
  const inner = document.createElement("div");
  inner.className = "explainability-panel";
  inner.id = "decisionExplanationBody";
  det.appendChild(sum);
  det.appendChild(inner);
  host.appendChild(det);
  det.addEventListener("toggle", () => {
    det.classList.toggle("open", det.open);
  });
  if (explain && explain.parentNode === panel) {
    panel.insertBefore(host, explain);
  } else {
    const grid = panel.querySelector(".grid");
    if (grid) panel.insertBefore(host, grid);
    else panel.appendChild(host);
  }
  return host;
}

function renderDecisionExplanation(explanation) {
  const host = ensureDecisionExplanationHost();
  const preview = document.getElementById("decisionExplanationPreview");
  const body = document.getElementById("decisionExplanationBody");
  const det = host?.querySelector("details");
  if (!host || !preview || !body || !det) return;

  if (!explanation || typeof explanation !== "object") {
    host.style.display = "none";
    det.open = false;
    preview.textContent = "";
    body.replaceChildren();
    return;
  }

  const lines = [];
  const ic = explanation.issue_classification;
  if (ic && ic.signal) lines.push(String(ic.signal));
  const ra = explanation.risk_assessment;
  if (ra && ra.signal) lines.push(String(ra.signal));
  const pi = explanation.policy_influence;
  if (pi && pi.signal) lines.push(String(pi.signal));
  const mi = explanation.memory_influence;
  if (mi && mi.signal) lines.push(String(mi.signal));
  const appr = explanation.approval_rationale;
  if (appr && appr.reason) lines.push(String(appr.reason));
  if (explanation.summary) lines.push(String(explanation.summary));

  if (!lines.length) {
    host.style.display = "none";
    det.open = false;
    preview.textContent = "";
    body.replaceChildren();
    return;
  }

  host.style.display = "";
  const sumText = explanation.summary ? String(explanation.summary) : lines[0];
  preview.textContent = sumText.length > 140 ? `${sumText.slice(0, 140)}…` : sumText;

  body.replaceChildren();
  lines.forEach((text) => {
    const row = document.createElement("div");
    row.className = "value muted reply-box";
    row.style.marginBottom = "8px";
    row.textContent = text;
    body.appendChild(row);
  });
  det.open = false;
  det.classList.remove("open");
}

function ensureOperatorExplainabilityHost() {
  const panel = document.getElementById("resultPanel");
  const explain = document.getElementById("explainabilityWrap");
  if (!panel) return null;
  let host = document.getElementById("operatorExplainabilityHost");
  if (host) return host;
  host = document.createElement("div");
  host.id = "operatorExplainabilityHost";
  host.style.marginBottom = "10px";
  const wrap = document.createElement("div");
  wrap.className = "explainability-wrap";
  const btn = document.createElement("button");
  btn.type = "button";
  btn.id = "explainToggleBtn";
  btn.className = "explainability-toggle";
  btn.style.width = "100%";
  btn.textContent = "Why this decision ↓";
  const panelBody = document.createElement("div");
  panelBody.id = "operatorExplainabilityBody";
  panelBody.className = "explainability-panel";
  panelBody.style.display = "none";
  wrap.appendChild(btn);
  wrap.appendChild(panelBody);
  host.appendChild(wrap);
  if (explain && explain.parentNode === panel) {
    panel.insertBefore(host, explain);
  } else {
    const grid = panel.querySelector(".grid");
    if (grid) panel.insertBefore(host, grid);
    else panel.appendChild(host);
  }
  return host;
}

function renderExplainability(explainability) {
  const host = ensureOperatorExplainabilityHost();
  const body = document.getElementById("operatorExplainabilityBody");
  const btn = document.getElementById("explainToggleBtn");
  if (!host || !body || !btn) return;

  if (!explainability || typeof explainability !== "object") {
    host.style.display = "none";
    body.replaceChildren();
    body.style.display = "none";
    btn.textContent = "Why this decision ↓";
    return;
  }

  const lines = [];
  const cl = explainability.classification;
  if (cl && cl.signal) lines.push(String(cl.signal));
  const rr = explainability.risk_reasoning;
  if (rr && rr.signal) lines.push(String(rr.signal));
  const pt = explainability.policy_trigger;
  if (pt && pt.signal) lines.push(String(pt.signal));
  const mi = explainability.memory_influence;
  if (mi && mi.signal) lines.push(String(mi.signal));
  const oe = explainability.outcome_expectation;
  if (oe && oe.signal) lines.push(String(oe.signal));

  host.style.display = "";
  body.replaceChildren();
  lines.forEach((text) => {
    const row = document.createElement("div");
    row.className = "value muted reply-box";
    row.style.marginBottom = "8px";
    row.textContent = text;
    body.appendChild(row);
  });
  if (explainability.why_not_other_actions) {
    const wrow = document.createElement("div");
    wrow.className = "value muted reply-box";
    wrow.style.marginBottom = "8px";
    wrow.style.opacity = "0.85";
    wrow.style.fontSize = "12px";
    wrow.textContent = String(explainability.why_not_other_actions);
    body.appendChild(wrow);
  }
  if (explainability.summary) {
    const sep = document.createElement("div");
    sep.style.borderTop = "1px solid var(--line)";
    sep.style.margin = "12px 0 10px";
    body.appendChild(sep);
    const sum = document.createElement("div");
    sum.className = "value reply-box";
    sum.style.fontSize = "13px";
    sum.style.lineHeight = "1.5";
    sum.textContent = String(explainability.summary);
    body.appendChild(sum);
  }

  const wrapEl = host.querySelector(".explainability-wrap");
  let open = false;
  btn.onclick = () => {
    open = !open;
    body.style.display = open ? "grid" : "none";
    btn.textContent = open ? "Close ↑" : "Why this decision ↓";
    if (wrapEl) wrapEl.classList.toggle("open", open);
  };
  body.style.display = "none";
  btn.textContent = "Why this decision ↓";
  if (wrapEl) wrapEl.classList.remove("open");
}

function ensureExecutionTierPill() {
  const top = document.querySelector("#resultPanel .panel-top");
  if (!top) return null;
  let el = document.getElementById("executionTierPill");
  if (el) return el;
  el = document.createElement("span");
  el.id = "executionTierPill";
  el.className = "status-badge hidden";
  const badge = document.getElementById("statusBadge");
  if (badge && badge.parentNode === top) {
    top.insertBefore(el, badge);
  } else {
    top.appendChild(el);
  }
  return el;
}

function deriveExecutionTierPresentation(data) {
  const raw = String(data.execution_tier || "").toLowerCase();
  if (raw === "safe_autopilot_ready") {
    return {
      text: "✓ Safe to automate",
      cls: "resolved",
      title: "Meets all automation safety criteria"
    };
  }
  if (raw === "assist_only") {
    return {
      text: "○ Manual review",
      cls: "pending",
      title: "Risk signals require human decision"
    };
  }
  if (raw === "approval_required") {
    return {
      text: "⚡ Approval required",
      cls: "waiting",
      title: "Awaiting operator approval"
    };
  }

  const dec = getDecisionData(data);
  const triage = getTriageData(data);
  const req = Boolean(dec.requires_approval || data.requires_approval);
  const action = String(dec.action || data.action || "none").toLowerCase();
  const amt = Number(dec.amount ?? data.amount ?? 0);
  const risk = String(dec.risk_level || triage.risk_level || data.risk_level || "medium").toLowerCase();
  const money = action === "refund" || action === "charge" || action === "credit";

  if (req && money) {
    return { text: "⚡ Approval required", cls: "waiting", title: "" };
  }
  if (action === "review" || risk === "high" || risk === "medium") {
    return { text: "⚠ Review recommended", cls: "pending", title: "" };
  }
  return { text: "✓ Safe to send", cls: "resolved", title: "" };
}

function renderExecutionTierSignal(data) {
  const el = ensureExecutionTierPill();
  if (!el) return;
  const pres = deriveExecutionTierPresentation(data);
  if (!pres.text) {
    el.classList.add("hidden");
    return;
  }
  el.textContent = pres.text;
  el.className = `status-badge ${pres.cls}`.trim();
  if (pres.title) el.setAttribute("title", pres.title);
  else el.removeAttribute("title");
  el.classList.remove("hidden");
}

function render(data) {
  ensureEnterpriseCards();

  const decision = getDecisionData(data);
  const triage = getTriageData(data);
  const impact = getImpactData(data);
  const history = getHistoryData(data);
  const issueType = normalize(data.issue_type || data.type);
  const reply = normalize(data.reply || data.response || data.final);
  const note = normalize(data.note);
  const policyRule = normalize(data.policy_rule);
  const aiSummary = normalize(data.ai_summary);
  const action = inferDisplayAction(data, reply, issueType);
  const reason = normalize(decision.reason || data.reason);
  const priority = normalize(String(decision.priority ?? data.priority ?? ""));
  const queue = normalize(String(decision.queue ?? data.queue ?? ""));
  const risk = normalize(String(decision.risk_level ?? triage.risk_level ?? data.risk_level ?? ""));
  const confidence = decision.confidence ?? data.confidence ?? "";
  const status = normalize(decision.status || data.status || (reply ? "resolved" : ""));
  const statusLower = status.toLowerCase();
  const execution = inferExecutionPayload(data, reply, issueType);

  if (typeValue) typeValue.textContent = safe(issueType);
  if (actionValue) actionValue.textContent = safe(action, issueType === "shipping_issue" && reply ? "Inform" : "-");
  if (confidenceValue) confidenceValue.textContent = confidence === "" ? "-" : String(confidence);
  if (priorityValue) priorityValue.textContent = priority || "-";
  if (queueValue) queueValue.textContent = queue || "-";
  if (riskValue) riskValue.textContent = risk || "-";
  if (reasonValue) reasonValue.textContent = reason || (issueType === "shipping_issue" ? "Tracking and ETA surfaced from current order context." : "-");
  if (policyValue) policyValue.textContent = policyRule || "-";
  if (aiSummaryValue) aiSummaryValue.textContent = aiSummary || "-";
  if (replyValue) replyValue.textContent = reply || "-";
  if (statusValue) statusValue.textContent = formatStatus(status) || "-";

  updateStatusBadge(status);
  setConfidence(confidence);

  if (notePill) {
    if (note) {
      notePill.textContent = note;
      notePill.classList.remove("hidden");
    } else {
      notePill.textContent = "";
      notePill.classList.add("hidden");
    }
  }

  renderExecutionTierSignal(data);
  if (data.decision_explainability && typeof data.decision_explainability === "object") {
    renderExplainability(data.decision_explainability);
    renderDecisionExplanation(null);
  } else {
    renderExplainability(null);
    renderDecisionExplanation(data.decision_explanation);
  }

  setVisible(statusCard, !!status);
  setVisible(confidenceCard, confidence !== "" && confidence !== null && confidence !== undefined);
  setVisible(priorityCard, !!priority);
  setVisible(queueCard, !!queue && statusLower !== "resolved" && statusLower !== "ignored" && queue !== "none");
  setVisible(riskCard, !!risk);
  setVisible(reasonCard, !!(reason || issueType === "shipping_issue"));
  setVisible(policyCard, !!policyRule);
  setVisible(aiSummaryCard, !!aiSummary);
  setVisible(replyCard, !!reply);

  renderExecution(execution);
  renderImpact(impact);
  renderMetaCards({
    ...data,
    impact,
    history,
    decision_trace: getThinkingTrace(data).map(step => `${step.step}: ${step.status}${step.detail ? ` (${step.detail})` : ""}`),
    memory_summary: history,
    session_impact: data.session_impact || (impact.agent_minutes_saved ? {
      tickets_seen: 1,
      tickets_resolved: statusLower === "resolved" ? 1 : 0,
      agent_minutes_saved: impact.agent_minutes_saved,
      value_generated: impact.money_saved || 0
    } : {})
  });
  renderExplainability({
    ...data,
    impact,
    reason,
    confidence,
    priority,
    risk_level: risk,
    execution
  });

  if (resultPanel) {
    const cards = Array.from(resultPanel.querySelectorAll(".card"));
    cards.forEach((card, index) => {
      card.style.animationDelay = `${Math.min(index * 0.02, 0.22)}s`;
    });
  }

  lastReply = reply;

  if (copyBtn) {
    copyBtn.style.display = reply ? "block" : "none";
    copyBtn.disabled = !reply;
  }

  if (insertBtn) {
    insertBtn.style.display = reply ? "block" : "none";
    insertBtn.disabled = !reply;
  }

  if (emptyState) {
    emptyState.style.display = "none";
  }

  hideInboxSummary();
  showHeaderInsight(buildHeaderInsight({ ...data, status, action, confidence, issue_type: issueType }));
  hideThinkingPanel();
  showPanel();

  if (impact?.agent_minutes_saved > 0) {
    showStatus(`⚡ Saved ${impact.agent_minutes_saved} agent minutes`);
  } else {
    showStatus("Ready.");
  }
}

async function extractText(tabId) {
  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => {
      const gmailMessage =
        document.querySelector(".a3s")?.innerText ||
        document.querySelector("div.a3s.aiL")?.innerText;

      if (gmailMessage && gmailMessage.trim()) {
        return gmailMessage.trim();
      }

      const gmailMain = document.querySelector('[role="main"]')?.innerText;
      if (gmailMain && gmailMain.trim()) {
        return gmailMain.trim();
      }

      return document.body?.innerText?.trim() || "";
    }
  });

  return results?.[0]?.result || "";
}

async function extractThreads(tabId) {
  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => {
      const rows = Array.from(document.querySelectorAll("tr.zA, tr[role='row'], .zA"));
      const threads = [];

      rows.forEach((el) => {
        const text = (el.innerText || "").trim();
        if (text && text.length > 20) {
          threads.push(text.slice(0, 500));
        }
      });

      return threads.slice(0, 15);
    }
  });

  return results?.[0]?.result || [];
}

function buildInboxSummary(results) {
  let auto = 0;
  let review = 0;
  let risk = 0;

  results.forEach((r) => {
    const decision = getDecisionData(r);
    const status = normalize(decision.status || r.status).toLowerCase();
    const riskLevel = normalize(decision.risk_level || r.risk_level).toLowerCase();

    if (status === "resolved") auto += 1;
    else review += 1;

    if (riskLevel === "high") risk += 1;
  });

  const minutesSaved = auto * 6;

  return {
    total: results.length,
    auto,
    review,
    risk,
    minutesSaved
  };
}

async function insertIntoGmail(tabId, text) {
  const [res] = await chrome.scripting.executeScript({
    target: { tabId },
    args: [text],
    func: async (reply) => {
      const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));

      function getComposer() {
        return (
          document.querySelector('div[aria-label="Message Body"]') ||
          document.querySelector('div[aria-label^="Message Body"]') ||
          document.querySelector('div[role="textbox"][g_editable="true"]') ||
          document.querySelector('div[contenteditable="true"][role="textbox"]') ||
          document.querySelector('div[contenteditable="true"][aria-label*="Message Body"]') ||
          document.querySelector('div[contenteditable="true"]')
        );
      }

      function findReplyButton() {
        const selectors = [
          'div[role="button"][aria-label="Reply"]',
          'div[role="button"][aria-label^="Reply"]',
          'span[role="button"][aria-label="Reply"]',
          'span[role="button"][aria-label^="Reply"]',
          '[data-tooltip="Reply"]',
          '[aria-label*="Reply"]'
        ];

        for (const selector of selectors) {
          const found = document.querySelector(selector);
          if (found) return found;
        }

        const roleButtons = Array.from(document.querySelectorAll('[role="button"], [role="link"], button, span'));
        return roleButtons.find(el => {
          const aria = (el.getAttribute("aria-label") || "").trim().toLowerCase();
          const text = (el.textContent || "").trim().toLowerCase();
          const tooltip = (el.getAttribute("data-tooltip") || "").trim().toLowerCase();

          return (
            aria === "reply" ||
            aria.startsWith("reply") ||
            tooltip === "reply" ||
            text === "reply"
          );
        }) || null;
      }

      function findComposeButton() {
        return (
          document.querySelector('div[role="button"][gh="cm"]') ||
          document.querySelector('div[role="button"][aria-label="Compose"]') ||
          document.querySelector('div[role="button"][aria-label^="Compose"]') ||
          document.querySelector('[aria-label="Compose"]')
        );
      }

      function insertTextIntoComposer(composer, value) {
        composer.focus();

        try {
          composer.click();
        } catch (_) {}

        try {
          if (document.getSelection) {
            const selection = document.getSelection();
            const range = document.createRange();
            range.selectNodeContents(composer);
            range.collapse(true);
            selection.removeAllRanges();
            selection.addRange(range);
          }
        } catch (_) {}

        let inserted = false;

        try {
          inserted = document.execCommand("insertText", false, value);
        } catch (_) {}

        if (!inserted) {
          try {
            composer.innerHTML = "";
          } catch (_) {}

          try {
            composer.textContent = value;
          } catch (_) {}
        }

        composer.dispatchEvent(new InputEvent("input", {
          bubbles: true,
          cancelable: true,
          inputType: "insertText",
          data: value
        }));

        composer.dispatchEvent(new Event("change", { bubbles: true }));
      }

      let composer = getComposer();

      if (!composer) {
        const replyButton = findReplyButton();

        if (replyButton) {
          try {
            replyButton.click();
          } catch (_) {
            try {
              replyButton.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
            } catch (_) {}
          }

          for (let i = 0; i < 8; i += 1) {
            await wait(250);
            composer = getComposer();
            if (composer) break;
          }
        }
      }

      if (!composer) {
        const composeButton = findComposeButton();

        if (composeButton) {
          try {
            composeButton.click();
          } catch (_) {
            try {
              composeButton.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
            } catch (_) {}
          }

          for (let i = 0; i < 10; i += 1) {
            await wait(300);
            composer = getComposer();
            if (composer) break;
          }
        }
      }

      if (!composer) {
        return {
          ok: false,
          detail: "No Gmail reply composer found."
        };
      }

      insertTextIntoComposer(composer, reply);

      return { ok: true };
    }
  });

  return res?.result || { ok: false, detail: "Insert failed." };
}

async function analyze() {
  thinkingRunId += 1;
  const currentRunId = thinkingRunId;

  hidePanel();
  hideHeaderInsight();
  hideInboxSummary();
  if (emptyState) emptyState.style.display = "none";

  if (copyBtn) {
    copyBtn.disabled = true;
    copyBtn.style.display = "none";
  }

  if (insertBtn) {
    insertBtn.disabled = true;
    insertBtn.style.display = "none";
  }

  lastReply = "";
  toggleExplainability(false);
  startThinkingPanel();

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (!tab?.id) {
      hideThinkingPanel();
      showStatus("No active tab found.", true);
      if (emptyState) emptyState.style.display = "grid";
      return;
    }

    const thinkingPromise = playThinkingSequence(currentRunId, "single");
    const text = await extractText(tab.id);

    if (!text) {
      thinkingRunId += 1;
      hideThinkingPanel();
      showStatus("No readable content found on this page.", true);
      if (emptyState) emptyState.style.display = "grid";
      return;
    }

    const res = await fetch("http://127.0.0.1:8000/analyze", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ text })
    });

    await thinkingPromise;

    if (!res.ok) {
      hideThinkingPanel();
      showStatus(`Analyze failed (${res.status})`, true);
      if (emptyState) emptyState.style.display = "grid";
      return;
    }

    showStatus("Generating decision...");
    const data = await res.json();
    render(data);
    showStatus("Ready.");
  } catch (err) {
    console.error("Analyze failed:", err);
    hideThinkingPanel();
    showStatus("Backend not reachable. Make sure app.py is running on 127.0.0.1:8000.", true);
    if (emptyState) emptyState.style.display = "grid";
  }
}

async function scanInbox() {
  thinkingRunId += 1;
  const currentRunId = thinkingRunId;

  hidePanel();
  hideHeaderInsight();
  hideInboxSummary();
  if (emptyState) emptyState.style.display = "none";

  if (copyBtn) {
    copyBtn.disabled = true;
    copyBtn.style.display = "none";
  }

  if (insertBtn) {
    insertBtn.disabled = true;
    insertBtn.style.display = "none";
  }

  lastReply = "";
  toggleExplainability(false);
  startThinkingPanel();

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (!tab?.id) {
      hideThinkingPanel();
      showStatus("No active tab found.", true);
      if (emptyState) emptyState.style.display = "grid";
      return;
    }

    const thinkingPromise = playThinkingSequence(currentRunId, "inbox");
    const threads = await extractThreads(tab.id);

    if (!threads.length) {
      thinkingRunId += 1;
      hideThinkingPanel();
      showStatus("No inbox threads found on this page.", true);
      if (emptyState) emptyState.style.display = "grid";
      return;
    }

    const results = [];

    for (let i = 0; i < threads.length; i += 1) {
      showStatus(`Analyzing ${i + 1}/${threads.length} visible tickets...`);
      try {
        const res = await fetch("http://127.0.0.1:8000/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: threads[i] })
        });

        if (res.ok) {
          results.push(await res.json());
        }
      } catch (err) {
        console.error("Inbox ticket analyze failed:", err);
      }
    }

    await thinkingPromise;

    hideThinkingPanel();

    if (!results.length) {
      showStatus("Inbox scan completed, but no tickets were analyzed.", true);
      if (emptyState) emptyState.style.display = "grid";
      return;
    }

    const summary = buildInboxSummary(results);
    const summaryText =
      `${summary.total} tickets scanned\n` +
      `⚡ ${summary.auto} safe to auto-resolve\n` +
      `🧠 ${summary.review} need review\n` +
      `⚠️ ${summary.risk} high-risk cases\n` +
      `💰 Estimated time saved: ${summary.minutesSaved} min`;

    showInboxSummary(summaryText);
    showHeaderInsight(`Inbox scan complete — ${summary.auto}/${summary.total} visible tickets look safe to automate.`);
    showStatus(`Inbox analysis complete. Estimated time saved: ${summary.minutesSaved} min`);
  } catch (err) {
    console.error("Inbox scan failed:", err);
    hideThinkingPanel();
    showStatus("Inbox scan failed.", true);
    if (emptyState) emptyState.style.display = "grid";
  }
}

if (explainabilityToggle) {
  explainabilityToggle.addEventListener("click", () => {
    toggleExplainability();
  });
}

if (analyzeBtn) {
  analyzeBtn.addEventListener("click", analyze);
}

if (scanInboxBtn) {
  scanInboxBtn.addEventListener("click", scanInbox);
}

if (copyBtn) {
  copyBtn.addEventListener("click", async () => {
    if (!lastReply) return;

    try {
      await navigator.clipboard.writeText(lastReply);
      const original = copyBtn.textContent;
      copyBtn.textContent = "Copied ✓";

      setTimeout(() => {
        copyBtn.textContent = original;
      }, 1200);
    } catch (err) {
      console.error("Copy failed:", err);
      showStatus("Could not copy the reply.", true);
    }
  });
}

if (insertBtn) {
  insertBtn.addEventListener("click", async () => {
    if (!lastReply) return;

    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

      if (!tab?.id) {
        showStatus("No active tab found.", true);
        return;
      }

      const res = await insertIntoGmail(tab.id, lastReply);

      if (!res.ok) {
        showStatus(res.detail || "Insert failed", true);
        return;
      }

      const original = insertBtn.textContent;
      insertBtn.textContent = "Inserted ✓";
      showStatus("Reply inserted into Gmail.");

      setTimeout(() => {
        insertBtn.textContent = original;
      }, 1200);
    } catch (err) {
      console.error("Insert failed:", err);
      showStatus("Could not insert reply into Gmail.", true);
    }
  });
}