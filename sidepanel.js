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


function mapCanonicalToLegacy(data) {
  if (!data || typeof data !== "object" || !data.sovereign_decision) return data;

  const decision = data.sovereign_decision || {};
  const triage = data.triage_metadata || {};
  const impact = data.impact_projections || {};
  const memory = data.memory_delta || {};
  const trace = Array.isArray(data.thinking_trace) ? data.thinking_trace : [];

  return {
    ...data,
    type: (data.issue_type || "general_support").replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()),
    status: decision.status || "new",
    action: decision.action ? decision.action.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()) : "None",
    action_raw: decision.action || "none",
    confidence: decision.confidence ?? "",
    quality: data.quality ?? "",
    reason: decision.reason || "",
    queue: decision.queue || "new",
    priority: decision.priority || "medium",
    risk_level: decision.risk_level || triage.risk_level || "medium",
    requires_approval: !!decision.requires_approval,
    urgency: triage.urgency || 0,
    reply: data.reply || data.final || data.response || "",
    final: data.final || data.reply || data.response || "",
    response: data.response || data.reply || data.final || "",
    policy_rule: decision.reason || "",
    ai_summary: trace.length ? trace.map(step => step.step).join(" -> ") : "Sovereign pipeline completed.",
    execution: {
      label: decision.tool_status || decision.status || "completed",
      detail: decision.requires_approval ? "Human review is required before execution." : "Decision executed through the sovereign pipeline.",
      mode: data.mode || "sovereign",
    },
    impact: {
      ...impact,
      signals: Array.isArray(impact.signals) ? impact.signals : [],
    },
    decision_trace: trace.map(step => `${step.step}: ${step.status}${step.detail ? ` (${step.detail})` : ""}`),
    memory_summary: {
      summary: `Plan ${memory.plan_tier || "free"} • refunds ${memory.refund_count || 0} • complaints ${memory.complaint_count || 0}`,
      pattern: memory.repeat_customer ? "Repeat customer pattern detected" : "No repeat customer pattern detected",
      samples: memory.refund_count || 0,
      avg_confidence: decision.confidence || 0,
      same_action_rate: memory.review_count || 0,
      issue_count: memory.complaint_count || 0,
      same_action_count: memory.refund_count || 0,
    },
    session_impact: {
      tickets_seen: 1,
      tickets_resolved: decision.status === "resolved" ? 1 : 0,
      agent_minutes_saved: impact.agent_minutes_saved || 0,
      value_generated: Number(impact.money_saved || 0),
      avg_confidence: decision.confidence || 0,
    },
    note: decision.requires_approval ? "Approval required" : "Sovereign decision",
  };
}

async function extractPageContext(tab) {
  const url = tab?.url || "";
  const title = tab?.title || "";
  let page = {};
  try {
    const [result] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => ({
        page_title: document.title || "",
        subject: document.querySelector("h2,h3,[role='heading']")?.innerText?.trim() || "",
        sender: document.querySelector("[email], [data-hovercard-id], .go, .gD")?.innerText?.trim() || "",
        dom_excerpt: document.body?.innerText?.trim()?.slice(0, 1000) || "",
        selected_text: window.getSelection?.()?.toString?.().trim?.() || "",
      })
    });
    page = result?.result || {};
  } catch (_) {}

  let host = "";
  try { host = new URL(url).host || ""; } catch (_) {}
  const appName = host.includes("mail.google") ? "gmail" : host.includes("zendesk") ? "zendesk" : host.includes("gorgias") ? "gorgias" : "web";

  return {
    page_url: url,
    host,
    page_title: page.page_title || title,
    app_name: appName,
    thread_id: url,
    subject: page.subject || title,
    sender: page.sender || "",
    dom_excerpt: page.dom_excerpt || "",
    selected_text: page.selected_text || "",
  };
}


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
  const status = normalize(data.status).toLowerCase();
  const action = normalize(data.action);
  const confidence = Number(data.confidence);
  const policy = normalize(data.policy_rule);
  const memorySummary = data.memory_summary || {};
  const samples =
    Number(memorySummary.samples) ||
    Number(memorySummary.same_action_count) ||
    Number(memorySummary.issue_count) ||
    0;

  if (status === "resolved" && action && samples > 0 && Number.isFinite(confidence) && confidence > 0) {
    return `Resolved instantly based on ${samples} similar past tickets at ${confidence.toFixed(2)} confidence.`;
  }

  if (status === "resolved" && action) {
    return `High-confidence automation selected: ${action}.`;
  }

  if ((status === "waiting" || status === "pending") && action) {
    return `Decision prepared: ${action}. Human review is still required.`;
  }

  if (status === "escalated") {
    return `Escalated for review because this case falls outside the low-risk auto-resolution path.`;
  }

  if (policy && action) {
    return `Policy '${policy}' selected '${action}' for this ticket.`;
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

function render(data) {
  ensureEnterpriseCards();

  const status = normalize(data.status);
  const statusLower = status.toLowerCase();
  const reply = normalize(data.reply);
  const note = normalize(data.note);
  const policyRule = normalize(data.policy_rule);
  const aiSummary = normalize(data.ai_summary);
  const reason = normalize(data.reason);
  const priority = normalize(String(data.priority ?? ""));
  const queue = normalize(String(data.queue ?? ""));
  const risk = normalize(String(data.risk_level ?? ""));
  const confidence = data.confidence ?? "";

  if (typeValue) typeValue.textContent = safe(data.type || data.issue_type);
  if (actionValue) actionValue.textContent = safe(data.action);
  if (confidenceValue) confidenceValue.textContent = confidence === "" ? "-" : String(confidence);
  if (priorityValue) priorityValue.textContent = priority || "-";
  if (queueValue) queueValue.textContent = queue || "-";
  if (riskValue) riskValue.textContent = risk || "-";
  if (reasonValue) reasonValue.textContent = reason || "-";
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

  setVisible(statusCard, !!status);
  setVisible(confidenceCard, confidence !== "" && confidence !== null && confidence !== undefined);
  setVisible(priorityCard, !!priority);
  setVisible(queueCard, !!queue && statusLower !== "resolved" && statusLower !== "ignored" && queue !== "none");
  setVisible(riskCard, !!risk);
  setVisible(reasonCard, !!reason);
  setVisible(policyCard, !!policyRule);
  setVisible(aiSummaryCard, !!aiSummary);
  setVisible(replyCard, !!reply);

  renderExecution(data.execution);
  renderImpact(data.impact);
  renderMetaCards(data);
  renderExplainability(data);

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
  showHeaderInsight(buildHeaderInsight(data));
  hideThinkingPanel();
  showPanel();
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
    const status = normalize(r.status).toLowerCase();
    const riskLevel = normalize(r.risk_level).toLowerCase();

    if (status === "resolved") auto += 1;
    else review += 1;

    if (riskLevel === "high") risk += 1;
  });

  return {
    total: results.length,
    auto,
    review,
    risk
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

    const context = await extractPageContext(tab);
    const res = await fetch("http://127.0.0.1:8000/analyze", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ text, ...context })
    });

    await thinkingPromise;

    if (!res.ok) {
      hideThinkingPanel();
      showStatus(`Analyze failed (${res.status})`, true);
      if (emptyState) emptyState.style.display = "grid";
      return;
    }

    showStatus("Generating decision...");
    const data = mapCanonicalToLegacy(await res.json());
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
        const context = await extractPageContext(tab);
        const res = await fetch("http://127.0.0.1:8000/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: threads[i], ...context })
        });

        if (res.ok) {
          results.push(mapCanonicalToLegacy(await res.json()));
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
      `• ${summary.auto} safe to auto-resolve\n` +
      `• ${summary.review} need review\n` +
      `• ${summary.risk} high risk`;

    showInboxSummary(summaryText);
    showHeaderInsight(`Inbox scan complete — ${summary.auto}/${summary.total} visible tickets look safe to automate.`);
    showStatus("Inbox analysis complete.");
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