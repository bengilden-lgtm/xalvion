/**
 * Xalvion Extension — side panel orchestrator
 * Owner: xalvion-extension/sidepanel.js
 *
 * Wires DOM, analyze/inbox pipelines, and Gmail actions. Delegates quota/upgrade UI to
 * `./ui/usage-chrome.js` and governor/trust presentation to `./renderers/governor-trust.js`.
 */
import { createChromeContext } from "./chrome-context.js";
import { insertIntoGmail } from "./adapters/chrome-compose.js";
import {
  OPERATOR_ANALYZE_URL,
  OPERATOR_CONNECTION_LABEL,
  describeOperatorAnalyzeFailure,
  describeOperatorHealthFailure,
  pingOperatorHealth,
} from "./operator-api.js";
import { createUsageChrome } from "./ui/usage-chrome.js";
import {
  renderConsequenceBar as renderConsequenceBarGov,
  renderOperatorBrief as renderOperatorBriefGov,
  renderTrustDominanceStrip as renderTrustDominanceStripGov,
} from "./renderers/governor-trust.js";
import {
  applyStructuredExplainabilityToData,
  buildHeaderInsight,
  buildThinkingSequence,
  normalizeExplainability,
  resetThinkingSteps,
  setThinkingStep,
  toBullets,
} from "./engines/agent-visualizer.js";
import {
  approvalGateActive,
  buildOperatorBriefLines,
  confidenceMeterPercent,
  deriveConsequencePresentation,
  formatDecisionTrace,
  formatImpact,
  formatMemorySummary,
  formatMode,
  formatSessionImpact,
  formatSignals,
  formatStatus,
  getApprovalCompactCopyText,
  getDecisionData,
  getHistoryData,
  getImpactData,
  getThinkingTrace,
  getTriageData,
  inferDisplayAction,
  inferExecutionPayload,
  normalize,
  safe,
  isRenderableAnalyzePayload,
} from "./utils/decision-formatters.js";
import { agentStore } from "./stores/agent-store.js";
import { uiStore } from "./stores/ui-store.js";
import { sessionStore } from "./stores/session-store.js";
import {
  dismissSoftNudgeForPeriod,
  enrollFreeTier,
  getUsageSnapshot,
  loadUsagePlan,
  recordSuccessfulOperatorRun,
  recordSuccessfulOperatorRuns,
} from "./usage-plan.js";

const chromeCtx = createChromeContext(typeof chrome !== "undefined" ? chrome : null);
const chromeApi = typeof chrome !== "undefined" ? chrome : null;

const analyzeBtn = document.getElementById("analyze");
const copyBtn = document.getElementById("copyBtn");
const insertBtn = document.getElementById("insertBtn");

const statusBox = document.getElementById("status");
const statusTitle = document.getElementById("statusTitle");
const statusBody = document.getElementById("statusBody");
const statusActionBtn = document.getElementById("statusActionBtn");
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
const replyStack = document.getElementById("replyStack");
const replyTextarea = document.getElementById("replyTextarea");
const replyToggleEditBtn = document.getElementById("replyToggleEditBtn");
const replyEditBanner = document.getElementById("replyEditBanner");
const gateEditBtn = document.getElementById("gateEditBtn");
const gateDoneBtn = document.getElementById("gateDoneBtn");
const approvalCompact = document.getElementById("approvalCompact");
const approvalCompactCopy = document.getElementById("approvalCompactCopy");
const consequenceSignal = document.getElementById("consequenceSignal");
let trustStripEl = document.getElementById("trustStrip");
let decisionMicrocopyEl = document.getElementById("decisionMicrocopy");
const operatorBriefEl = document.getElementById("operatorBrief");
const operatorBriefBody = document.getElementById("operatorBriefBody");

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

const capPill = document.getElementById("extensionCapacityPill");
const upgradeContextPanel = document.getElementById("upgradeContextPanel");
const upgradeContextEyebrow = document.getElementById("upgradeContextEyebrow");
const upgradeContextPrimary = document.getElementById("upgradeContextPrimary");
const upgradeContextSecondary = document.getElementById("upgradeContextSecondary");
const upgradeContextSplit = document.getElementById("upgradeContextSplit");
const upgradeEnrollFreeBtn = document.getElementById("upgradeEnrollFreeBtn");
const upgradeDismissSoftBtn = document.getElementById("upgradeDismissSoftBtn");
const upgradeProLink = document.getElementById("upgradeProLink");

const scanInboxBtn = document.getElementById("scanInbox");
const inboxSummary = document.getElementById("inboxSummary");
const inboxSummaryValue = document.getElementById("inboxSummaryValue");

const usageChrome = createUsageChrome({
  els: {
    analyzeBtn,
    scanInboxBtn,
    capPill,
    upgradeContextPanel,
    upgradeContextEyebrow,
    upgradeContextPrimary,
    upgradeContextSecondary,
    upgradeContextSplit,
    upgradeEnrollFreeBtn,
    upgradeDismissSoftBtn,
    upgradeProLink,
  },
  uiStore,
  sessionStore,
  getUsageSnapshot,
  loadUsagePlan,
  enrollFreeTier,
  dismissSoftNudgeForPeriod,
  showStatus: (msg) => showStatus(msg, false),
});

/** Compat: legacy locals stay in sync with stores for existing closures and guards */
let lastReply = "";
let replySnapshotBeforeEdit = "";
let explainabilityOpen = false;
let thinkingRunId = 0;
let replyEditing = false;
let lastPrimaryIntent = "";
let activeRunKind = "";

function syncCompatFromStores() {
  const ui = uiStore.getState();
  lastReply = ui.lastReply;
  replySnapshotBeforeEdit = ui.replySnapshotBeforeEdit;
  explainabilityOpen = ui.explainabilityOpen;
  replyEditing = ui.replyEditing;
  thinkingRunId = agentStore.getState().thinkingRunId;
}

uiStore.subscribe(() => {
  syncCompatFromStores();
  usageChrome.syncPrimaryRunButtons();
});
agentStore.subscribe(syncCompatFromStores);
syncCompatFromStores();

async function ensureUsageReady() {
  await usageChrome.ensureUsageReady();
}

function isBusy() {
  return Boolean(uiStore.getState().loading);
}

function setPrimaryButtonsBusy(busy, labelOverride = "") {
  const isOn = Boolean(busy);
  if (analyzeBtn) {
    analyzeBtn.disabled = isOn;
    analyzeBtn.dataset.busy = isOn ? "true" : "false";
    if (labelOverride) analyzeBtn.dataset.busyLabel = labelOverride;
  }
  if (scanInboxBtn) {
    scanInboxBtn.disabled = isOn;
    scanInboxBtn.dataset.busy = isOn ? "true" : "false";
    if (labelOverride) scanInboxBtn.dataset.busyLabel = labelOverride;
  }
}

function sanitizeServiceDetail(text) {
  const t = normalize(String(text || ""));
  if (!t) return "";
  // Avoid leaking stack traces or raw internal payloads into the UI.
  const clipped = t.slice(0, 260);
  if (/traceback|exception|stack|error:\s/i.test(clipped)) return "";
  return clipped;
}

const ANALYZE_FETCH_TIMEOUT_MS = 90_000;
const INBOX_THREAD_FETCH_TIMEOUT_MS = 45_000;
const THINKING_SEQUENCE_CAP_MS = 4_000;

async function awaitThinkingSequenceCapped(promise, capMs) {
  const ms = Math.max(0, Number(capMs) || 0);
  await Promise.race([Promise.resolve(promise), delay(ms)]);
}

async function fetchJsonWithTimeout(url, payload, timeoutMs) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    const raw = await res.text().catch(() => "");
    if (!res.ok) {
      const detail = sanitizeServiceDetail(raw);
      return {
        ok: false,
        status: res.status,
        detail,
        data: null,
        kind: "http_error",
      };
    }

    let data;
    try {
      data = JSON.parse(raw);
    } catch (jsonErr) {
      console.warn("[xalvion:fetch] invalid JSON", { rawPreview: String(raw || "").slice(0, 240) });
      return { ok: false, status: res.status, detail: "", data: null, kind: "invalid_json" };
    }

    return { ok: true, status: res.status, detail: "", data };
  } catch (err) {
    const isAbort =
      err && typeof err === "object" && (err.name === "AbortError" || /aborted/i.test(String(err.message || "")));
    console.warn("[xalvion:fetch] request failed", { url, isAbort, message: String(err && err.message ? err.message : err) });
    return {
      ok: false,
      status: 0,
      detail: "",
      data: null,
      kind: isAbort ? "timeout" : "network",
    };
  } finally {
    clearTimeout(timeoutId);
  }
}

function armSlowNetworkNudge(runId, mode) {
  const start = Date.now();
  let stage = -1;
  const hints =
    mode === "inbox"
      ? [
          "Connecting to the operator…",
          "Still working — scanning visible rows.",
          "This is taking longer than usual. Retry anytime, or keep waiting.",
          "Large scans can take a while — still running.",
        ]
      : [
          "Connecting to the operator…",
          "Still working — reviewing policy and ticket context.",
          "This is taking longer than usual. Retry anytime, or keep waiting.",
          "Complex tickets can take longer — still running.",
        ];

  const id = setInterval(() => {
    if (runId !== agentStore.getState().thinkingRunId) {
      clearInterval(id);
      return;
    }
    const elapsed = Date.now() - start;
    if (elapsed < 850) return;
    let nextStage = 0;
    if (elapsed > 55_000) nextStage = 3;
    else if (elapsed > 14_000) nextStage = 2;
    else if (elapsed > 3200) nextStage = 1;
    else nextStage = 0;
    if (nextStage === stage) return;
    stage = nextStage;
    const msg = hints[Math.min(stage, hints.length - 1)];
    if (thinkingSubtitle) thinkingSubtitle.textContent = msg;
    showStatus(msg, false);
  }, 380);

  return () => clearInterval(id);
}

function renderConsequenceBar(data) {
  renderConsequenceBarGov({
    data,
    consequenceSignal,
    deriveConsequencePresentation,
    getDecisionData,
  });
}

function dedupeExtensionNodesById(id) {
  const safe = typeof CSS !== "undefined" && CSS.escape ? CSS.escape(id) : id.replace(/"/g, '\\"');
  let nodes;
  try {
    nodes = Array.from(document.querySelectorAll(`[id="${safe}"]`));
  } catch (_) {
    nodes = [];
    const all = document.querySelectorAll("[id]");
    for (let i = 0; i < all.length; i += 1) {
      if (all[i].id === id) nodes.push(all[i]);
    }
  }
  for (let i = 1; i < nodes.length; i += 1) {
    try {
      nodes[i].remove();
    } catch (_) {}
  }
  return nodes[0] || null;
}

function ensureTrustStrip() {
  dedupeExtensionNodesById("trustStrip");
  if (trustStripEl && trustStripEl.isConnected && trustStripEl.id === "trustStrip") {
    return trustStripEl;
  }
  const fromDom = document.getElementById("trustStrip");
  if (fromDom && fromDom.isConnected) {
    trustStripEl = fromDom;
    return trustStripEl;
  }
  trustStripEl = null;

  // Insert directly under the consequence bar to stay high-signal and compact.
  const panel = document.getElementById("resultPanel");
  const bar = panel?.querySelector(".consequence-bar");
  if (!panel || !bar) return null;
  const el = document.createElement("div");
  el.id = "trustStrip";
  el.className = "trust-strip tone-review";
  bar.insertAdjacentElement("afterend", el);
  trustStripEl = el;
  return trustStripEl;
}

function ensureDecisionMicrocopy() {
  dedupeExtensionNodesById("decisionMicrocopy");
  if (decisionMicrocopyEl && decisionMicrocopyEl.isConnected && decisionMicrocopyEl.id === "decisionMicrocopy") {
    return decisionMicrocopyEl;
  }
  const fromDom = document.getElementById("decisionMicrocopy");
  if (fromDom && fromDom.isConnected) {
    decisionMicrocopyEl = fromDom;
    return decisionMicrocopyEl;
  }
  decisionMicrocopyEl = null;

  const panel = document.getElementById("resultPanel");
  if (!panel) return null;
  const bar = panel.querySelector(".consequence-bar") || panel.querySelector("#consequenceSignal") || panel;
  if (!bar) return null;
  const el = document.createElement("div");
  el.id = "decisionMicrocopy";
  el.className = "decision-microcopy";
  el.style.display = "none";
  // Keep ordering stable: trust strip first (if any), then microcopy directly under the bar.
  ensureTrustStrip();
  const anchor = trustStripEl || panel.querySelector("#trustStrip");
  if (anchor && anchor.parentElement) {
    anchor.insertAdjacentElement("afterend", el);
  } else if (bar instanceof HTMLElement) {
    bar.insertAdjacentElement("afterend", el);
  } else {
    panel.insertAdjacentElement("afterbegin", el);
  }
  decisionMicrocopyEl = el;
  return decisionMicrocopyEl;
}

function setDecisionMicrocopy(text, tone = "") {
  const el = ensureDecisionMicrocopy();
  if (!el) return;
  const t = String(text || "").trim();
  el.textContent = t;
  el.style.display = t ? "block" : "none";
  el.dataset.tone = String(tone || "");
}

function renderTrustStrip(data) {
  const el = ensureTrustStrip();
  if (!el) return;
  renderTrustDominanceStripGov({ data, mountEl: el });
}

function renderApprovalCompact(data, reply) {
  if (!approvalCompact || !approvalCompactCopy) return;
  if (!reply) {
    approvalCompact.classList.remove("is-visible");
    return;
  }
  if (!approvalGateActive(data)) {
    approvalCompact.classList.remove("is-visible");
    return;
  }
  approvalCompactCopy.textContent = getApprovalCompactCopyText(data);
  approvalCompact.classList.add("is-visible");
}

function addBriefLine(container, label, value) {
  const row = document.createElement("div");
  row.className = "operator-brief-line";
  const k = String(label || "").trim();
  if (k) {
    const strong = document.createElement("strong");
    strong.textContent = `${k} `;
    row.appendChild(strong);
  }
  row.appendChild(document.createTextNode(value || "—"));
  container.appendChild(row);
}

function renderOperatorBrief(data) {
  renderOperatorBriefGov({
    data,
    operatorBriefBody,
    addBriefLine,
    buildOperatorBriefLines,
    getDecisionData,
  });
}

function resetReplyEditor() {
  uiStore.setState({ replyEditing: false, replySnapshotBeforeEdit: "" });
  if (replyTextarea) {
    replyTextarea.classList.add("is-hidden");
    replyTextarea.value = "";
  }
  if (replyStack) replyStack.classList.remove("is-editing");
  if (replyEditBanner) replyEditBanner.style.display = "";
  if (replyValue) replyValue.classList.remove("is-hidden");
  if (replyToggleEditBtn) replyToggleEditBtn.textContent = "Edit";
}

function setReplyEditing(on) {
  const editing = Boolean(on);
  if (editing) {
    uiStore.setState((s) => ({
      ...s,
      replyEditing: true,
      replySnapshotBeforeEdit: s.lastReply,
    }));
  } else {
    uiStore.setState({ replyEditing: false });
  }
  const text = uiStore.getState().lastReply || "";
  if (replyTextarea && replyValue && replyToggleEditBtn) {
    if (editing) {
      replyTextarea.value = text;
      replyTextarea.classList.remove("is-hidden");
      replyValue.classList.add("is-hidden");
      if (replyStack) replyStack.classList.add("is-editing");
      replyToggleEditBtn.textContent = "Preview";
      replyTextarea.focus();
    } else {
      let next = replyTextarea.classList.contains("is-hidden")
        ? uiStore.getState().lastReply
        : normalize(replyTextarea.value);
      const snap = uiStore.getState().replySnapshotBeforeEdit;
      if (!next && snap) {
        next = snap;
      }
      uiStore.setState({ lastReply: next, replySnapshotBeforeEdit: "" });
      if (replyValue) replyValue.textContent = next || "-";
      replyTextarea.classList.add("is-hidden");
      replyValue.classList.remove("is-hidden");
      if (replyStack) replyStack.classList.remove("is-editing");
      replyToggleEditBtn.textContent = "Edit";
      if (copyBtn) {
        copyBtn.disabled = !next;
        copyBtn.style.display = next ? "block" : "none";
      }
      if (insertBtn) {
        insertBtn.disabled = !next;
        insertBtn.style.display = next ? "block" : "none";
      }
    }
  }
}

function syncReplyFromTextarea() {
  if (!replyTextarea || !uiStore.getState().replyEditing) return;
  const next = normalize(replyTextarea.value);
  uiStore.setState({ lastReply: next });
  if (replyValue) replyValue.textContent = next || "-";
}

function showStatus(message, isError = false) {
  const payload =
    typeof message === "object" && message
      ? message
      : {
          title: isError ? "Something went wrong" : "",
          body: String(message || ""),
          action: null,
        };

  const next = {
    statusMessage: `${payload.title ? `${payload.title}\n` : ""}${payload.body || ""}`.trim(),
    statusIsError: Boolean(isError || payload.kind === "error"),
  };

  uiStore.setState(next);

  if (!statusBox) return;

  const err = uiStore.getState().statusIsError;
  const hasAny = Boolean(payload.title || payload.body);

  if (!hasAny) {
    statusBox.className = "status";
    if (statusTitle) statusTitle.textContent = "";
    if (statusBody) statusBody.textContent = "";
    if (statusActionBtn) {
      statusActionBtn.textContent = "";
      statusActionBtn.classList.add("is-hidden");
      statusActionBtn.onclick = null;
    }
    return;
  }

  statusBox.className = err ? "status show error" : "status show";
  if (statusTitle) statusTitle.textContent = payload.title || (err ? "Something went wrong" : "Status");
  if (statusBody) statusBody.textContent = payload.body || "";

  if (statusActionBtn) {
    const action = payload.action;
    if (action?.label && typeof action.onClick === "function") {
      statusActionBtn.textContent = action.label;
      statusActionBtn.classList.remove("is-hidden");
      statusActionBtn.onclick = action.onClick;
    } else {
      statusActionBtn.textContent = "";
      statusActionBtn.classList.add("is-hidden");
      statusActionBtn.onclick = null;
    }
  }
}

function showPanel() {
  if (resultPanel) resultPanel.classList.add("show");
}

function hidePanel() {
  if (resultPanel) resultPanel.classList.remove("show");
}

function setVisible(el, visible) {
  if (!el) return;
  el.style.display = visible ? "" : "none";
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
  confidenceMeter.style.width = confidenceMeterPercent(conf) + "%";
}

function getGrid() {
  return document.getElementById("resultMetaGrid") || resultPanel?.querySelector(".grid");
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
      detailId: "executionDetailValue",
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
      full: true,
    });
    impactValue = document.getElementById("impactValue");
    if (impactValue) impactValue.classList.add("reply-box");
  }

  if (!signalsCard) {
    signalsCard = createCard("signalsCard", "Signals", "signalsValue", {
      full: true,
      muted: true,
    });
    signalsValue = document.getElementById("signalsValue");
    if (signalsValue) signalsValue.classList.add("reply-box");
  }

  if (!decisionTraceCard) {
    decisionTraceCard = createCard("decisionTraceCard", "Decision Trace", "decisionTraceValue", {
      full: true,
      muted: true,
    });
    decisionTraceValue = document.getElementById("decisionTraceValue");
    if (decisionTraceValue) decisionTraceValue.classList.add("reply-box");
  }

  if (!memorySummaryCard) {
    memorySummaryCard = createCard("memorySummaryCard", "Memory Summary", "memorySummaryValue", {
      full: true,
      muted: true,
    });
    memorySummaryValue = document.getElementById("memorySummaryValue");
    if (memorySummaryValue) memorySummaryValue.classList.add("reply-box");
  }

  if (!sessionImpactCard) {
    sessionImpactCard = createCard("sessionImpactCard", "Session Impact", "sessionImpactValue", {
      full: true,
      muted: true,
    });
    sessionImpactValue = document.getElementById("sessionImpactValue");
    if (sessionImpactValue) sessionImpactValue.classList.add("reply-box");
  }
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

function renderExplainabilitySections(data) {
  if (!explainabilityWrap) return;

  const explainability = normalizeExplainability(data);
  const sections = explainability.sections;

  if (explainabilitySummary) {
    explainabilitySummary.textContent =
      explainability.summary || "Decision confidence, policy fit, learned behavior, and execution rationale.";
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
    uiStore.setState({ explainabilityOpen: false });
  }
}

function toggleExplainability(forceOpen = null) {
  if (!explainabilityWrap || explainabilityWrap.classList.contains("hidden")) return;
  uiStore.setState((s) => ({
    ...s,
    explainabilityOpen: typeof forceOpen === "boolean" ? forceOpen : !s.explainabilityOpen,
  }));
  explainabilityWrap.classList.toggle("open", uiStore.getState().explainabilityOpen);
}

function hideThinkingPanel() {
  if (thinkingPanel) thinkingPanel.classList.remove("show");
}

function startThinkingPanel() {
  resetThinkingSteps(thinkingSteps, thinkingSubtitle);
  if (thinkingPanel) thinkingPanel.classList.add("show");
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function playThinkingSequence(runId, mode = "single") {
  const sequence = buildThinkingSequence(mode);

  for (const item of sequence) {
    if (runId !== agentStore.getState().thinkingRunId) return;
    showStatus(item.status);
    setThinkingStep(thinkingSteps, item.index, "active", item.subtitle, thinkingSubtitle);
    await delay(180);
    if (runId !== agentStore.getState().thinkingRunId) return;
    setThinkingStep(thinkingSteps, item.index, "done", item.subtitle, thinkingSubtitle);
  }
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
  resetReplyEditor();

  agentStore.setState({ latestPayload: data });

  usageChrome.updateCapacityPillFromData(data);

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

  uiStore.setState({ lastReply: reply });
  if (replyStack) replyStack.classList.toggle("is-visible", !!reply);

  updateStatusBadge(status);
  setConfidence(confidence);

  renderConsequenceBar(data);
  renderTrustStrip(data);
  renderOperatorBrief(data);
  renderApprovalCompact(data, reply);

  // High-stakes microcopy + state tone (kept minimal, no layout changes).
  const pendingGate = approvalGateActive(data);
  const toolStatus = normalize(String(data.tool_status || "")).toLowerCase();
  if (toolStatus === "rejected" || statusLower === "escalated" || statusLower === "rejected") {
    setDecisionMicrocopy("Response held. Ticket escalated.", "risk");
    if (resultPanel) resultPanel.dataset.decisionTone = "risk";
  } else if (pendingGate) {
    setDecisionMicrocopy("Approval required — nothing moves until you decide.", "hold");
    if (resultPanel) resultPanel.dataset.decisionTone = "hold";
  } else {
    const riskLc = normalize(String(decision.risk_level ?? triage.risk_level ?? data.risk_level ?? "")).toLowerCase();
    const risky = riskLc === "high" || riskLc === "medium" || normalize(action).toLowerCase() === "review";
    if (risky) {
      setDecisionMicrocopy("Higher risk — read carefully before you send.", "risk");
      if (resultPanel) resultPanel.dataset.decisionTone = "risk";
    } else {
      setDecisionMicrocopy("Matches similar safe outcomes — still your send.", "safe");
      if (resultPanel) resultPanel.dataset.decisionTone = "safe";
    }
  }

  // Subtle enter animation when a decision becomes ready.
  if (resultPanel) {
    resultPanel.classList.remove("xv-decision-ready");
    window.requestAnimationFrame(() => resultPanel.classList.add("xv-decision-ready"));
  }

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
  setVisible(reasonCard, !!(reason || issueType === "shipping_issue"));
  setVisible(policyCard, !!policyRule);
  setVisible(aiSummaryCard, !!aiSummary);

  renderExecution(execution);
  renderImpact(impact);
  renderMetaCards({
    ...data,
    impact,
    history,
    decision_trace: getThinkingTrace(data).map((step) => `${step.step}: ${step.status}${step.detail ? ` (${step.detail})` : ""}`),
    memory_summary: history,
    session_impact:
      data.session_impact ||
      (impact.agent_minutes_saved
        ? {
            tickets_seen: 1,
            tickets_resolved: statusLower === "resolved" ? 1 : 0,
            agent_minutes_saved: impact.agent_minutes_saved,
            value_generated: impact.money_saved || 0,
          }
        : {}),
  });
  renderExplainabilitySections(
    applyStructuredExplainabilityToData({
      ...data,
      impact,
      reason,
      confidence,
      priority,
      risk_level: risk,
      execution,
    })
  );

  if (resultPanel) {
    const cards = Array.from(resultPanel.querySelectorAll(".card"));
    cards.forEach((card, index) => {
      card.style.animationDelay = `${Math.min(index * 0.012, 0.12)}s`;
    });
  }

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
  {
    const govReason = String(data?.governor_reason || decision?.governor_reason || "").trim();
    showHeaderInsight(govReason || buildHeaderInsight({ ...data, status, action, confidence, issue_type: issueType }));
  }
  hideThinkingPanel();
  showPanel();

  if (impact?.agent_minutes_saved > 0) {
    showStatus(`~${impact.agent_minutes_saved} min back on this ticket`);
  } else {
    showStatus("Reply ready.");
  }

  usageChrome.refreshUsageChrome();
  usageChrome.syncPrimaryRunButtons();
}

async function extractText(tabId) {
  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => {
      const gmailMessage =
        document.querySelector(".a3s")?.innerText || document.querySelector("div.a3s.aiL")?.innerText;

      if (gmailMessage && gmailMessage.trim()) {
        return gmailMessage.trim();
      }

      const gmailMain = document.querySelector('[role="main"]')?.innerText;
      if (gmailMain && gmailMain.trim()) {
        return gmailMain.trim();
      }

      return document.body?.innerText?.trim() || "";
    },
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
    },
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
    minutesSaved,
  };
}

async function analyze() {
  await ensureUsageReady();
  if (isBusy()) return;
  activeRunKind = "analyze";
  lastPrimaryIntent = "analyze";
  const preSnap = getUsageSnapshot(sessionStore.getState().planTier);
  if (preSnap.hardLimited && !preSnap.hasProAccess) {
    usageChrome.notifyGateAttempt?.("analyze");
    showStatus(
      "Included runs used for this window — copy, insert, and approvals still work. Add runway to go unlimited.",
      false
    );
    usageChrome.refreshUsageChrome();
    usageChrome.syncPrimaryRunButtons();
    return;
  }

  uiStore.setState({ loading: true });
  setPrimaryButtonsBusy(true);
  let disarmSlowNudge = () => {};
  let thinkingPromise = Promise.resolve();
  try {
    agentStore.setState((s) => ({
      ...s,
      thinkingRunId: s.thinkingRunId + 1,
      latestPayload: null,
    }));
    const currentRunId = agentStore.getState().thinkingRunId;

    hidePanel();
    hideHeaderInsight();
    hideInboxSummary();
    if (emptyState) emptyState.style.display = "none";
    showStatus({ title: "Analyzing", body: "Reading the active ticket and preparing the operator stack." }, false);

    if (copyBtn) {
      copyBtn.disabled = true;
      copyBtn.style.display = "none";
    }

    if (insertBtn) {
      insertBtn.disabled = true;
      insertBtn.style.display = "none";
    }

    uiStore.setState({ lastReply: "", replyEditing: false, replySnapshotBeforeEdit: "" });
    resetReplyEditor();
    toggleExplainability(false);
    startThinkingPanel();

    const tab = await chromeCtx.getActiveTab();

    if (!tab?.id) {
      hideThinkingPanel();
      showStatus(
        {
          kind: "error",
          title: "No active tab",
          body: "Open Gmail, Zendesk, or Gorgias in the foreground, then try again.",
          action: { label: "Retry", onClick: analyze },
        },
        true
      );
      if (emptyState) emptyState.style.display = "grid";
      return;
    }

    const text = await extractText(tab.id);

    if (!text) {
      agentStore.setState((s) => ({ ...s, thinkingRunId: s.thinkingRunId + 1 }));
      hideThinkingPanel();
      showStatus(
        {
          kind: "error",
          title: "Nothing to analyze on this page",
          body: "Open a Gmail thread or ticket view so we can read the message text. You do not need a reply box open for Analyze.",
          action: { label: "Retry", onClick: analyze },
        },
        true
      );
      if (emptyState) emptyState.style.display = "grid";
      return;
    }

    console.log("[xalvion:analyze] phase:fetch_start", { runId: currentRunId, timeoutMs: ANALYZE_FETCH_TIMEOUT_MS, textLen: text.length });

    const health = await pingOperatorHealth();
    if (!health.ok) {
      agentStore.setState((s) => ({ ...s, thinkingRunId: s.thinkingRunId + 1 }));
      hideThinkingPanel();
      const { title, body } = describeOperatorHealthFailure(health);
      showStatus(
        {
          kind: "error",
          title,
          body,
          action: { label: "Retry", onClick: analyze },
        },
        true
      );
      if (emptyState) emptyState.style.display = "grid";
      return;
    }

    disarmSlowNudge = armSlowNetworkNudge(currentRunId, "single");
    thinkingPromise = playThinkingSequence(currentRunId, "single");
    const result = await fetchJsonWithTimeout(OPERATOR_ANALYZE_URL, { text }, ANALYZE_FETCH_TIMEOUT_MS);

    disarmSlowNudge();
    if (!result.ok) {
      agentStore.setState((s) => ({ ...s, thinkingRunId: s.thinkingRunId + 1 }));
    }
    await awaitThinkingSequenceCapped(thinkingPromise, result.ok ? THINKING_SEQUENCE_CAP_MS : 900);
    hideThinkingPanel();

    console.log("[xalvion:analyze] phase:fetch_settled", {
      runId: currentRunId,
      ok: result.ok,
      status: result.status,
      kind: result.kind || "",
    });

    if (!result.ok) {
      const { title, body } = describeOperatorAnalyzeFailure(result, { actionLabel: "Analyze" });
      showStatus(
        {
          kind: "error",
          title,
          body,
          action: { label: "Retry", onClick: analyze },
        },
        true
      );
      if (emptyState) emptyState.style.display = "grid";
      return;
    }

    const data = result.data;
    if (!isRenderableAnalyzePayload(data)) {
      console.warn("[xalvion:analyze] phase:payload_invalid", { runId: currentRunId, type: typeof data });
      showStatus(
        {
          kind: "error",
          title: "Unexpected response",
          body: "The operator returned an empty or unsupported payload. Try again.",
          action: { label: "Retry", onClick: analyze },
        },
        true
      );
      if (emptyState) emptyState.style.display = "grid";
      return;
    }

    console.log("[xalvion:analyze] phase:render_start", { runId: currentRunId, keys: Object.keys(data).slice(0, 14) });
    try {
      render(data);
    } catch (renderErr) {
      console.warn("[xalvion:analyze] phase:render_failed", { runId: currentRunId, message: String(renderErr && renderErr.message ? renderErr.message : renderErr) });
      showStatus(
        {
          kind: "error",
          title: "Couldn’t show this decision",
          body: "Something went wrong while rendering the result. Try Analyze again.",
          action: { label: "Retry", onClick: analyze },
        },
        true
      );
      if (emptyState) emptyState.style.display = "grid";
      return;
    }
    console.log("[xalvion:analyze] phase:render_done", { runId: currentRunId });

    try {
      await recordSuccessfulOperatorRun(sessionStore.getState().planTier);
    } catch (usageErr) {
      console.warn("[xalvion:analyze] usage record skipped", usageErr);
    }
    usageChrome.notifyOperatorRunComplete?.(data);
    usageChrome.refreshUsageChrome();
    usageChrome.syncPrimaryRunButtons();
    showStatus({ title: "Reply ready", body: "Copy or insert — you’re in control of what ships." }, false);
  } catch (err) {
    disarmSlowNudge();
    agentStore.setState((s) => ({ ...s, thinkingRunId: s.thinkingRunId + 1 }));
    await awaitThinkingSequenceCapped(thinkingPromise, 600);
    hideThinkingPanel();
    console.warn("[xalvion:analyze] phase:terminal_error", { message: String(err && err.message ? err.message : err) });
    showStatus(
      {
        kind: "error",
        title: "Something went wrong",
        body: `Try Analyze again. If this keeps happening, confirm the operator API is reachable at ${OPERATOR_CONNECTION_LABEL}.`,
        action: { label: "Retry", onClick: analyze },
      },
      true
    );
    if (emptyState) emptyState.style.display = "grid";
  } finally {
    disarmSlowNudge();
    uiStore.setState({ loading: false });
    setPrimaryButtonsBusy(false);
    usageChrome.syncPrimaryRunButtons();
    activeRunKind = "";
  }
}

async function scanInbox() {
  await ensureUsageReady();
  if (isBusy()) return;
  activeRunKind = "scan";
  lastPrimaryIntent = "scan";
  const preSnap = getUsageSnapshot(sessionStore.getState().planTier);
  if (preSnap.hardLimited && !preSnap.hasProAccess) {
    usageChrome.notifyGateAttempt?.("scan");
    showStatus(
      "Included runs used — copy, insert, and approvals still work. Add runway to keep threads uninterrupted.",
      false
    );
    usageChrome.refreshUsageChrome();
    usageChrome.syncPrimaryRunButtons();
    return;
  }

  uiStore.setState({ loading: true });
  setPrimaryButtonsBusy(true);
  let disarmSlowNudge = () => {};
  let thinkingPromise = Promise.resolve();
  try {
    agentStore.setState((s) => ({
      ...s,
      thinkingRunId: s.thinkingRunId + 1,
      latestPayload: null,
    }));
    const currentRunId = agentStore.getState().thinkingRunId;

    hidePanel();
    hideHeaderInsight();
    hideInboxSummary();
    if (emptyState) emptyState.style.display = "none";
    showStatus({ title: "Scanning inbox", body: "Summarizing visible rows and flagging risk." }, false);

    if (copyBtn) {
      copyBtn.disabled = true;
      copyBtn.style.display = "none";
    }

    if (insertBtn) {
      insertBtn.disabled = true;
      insertBtn.style.display = "none";
    }

    uiStore.setState({ lastReply: "", replyEditing: false, replySnapshotBeforeEdit: "" });
    resetReplyEditor();
    toggleExplainability(false);
    startThinkingPanel();

    const tab = await chromeCtx.getActiveTab();

    if (!tab?.id) {
      hideThinkingPanel();
      showStatus(
        {
          kind: "error",
          title: "No active tab",
          body: "Open Gmail inbox in the foreground, then try Scan inbox again.",
          action: { label: "Retry", onClick: scanInbox },
        },
        true
      );
      if (emptyState) emptyState.style.display = "grid";
      return;
    }

    disarmSlowNudge = armSlowNetworkNudge(currentRunId, "inbox");
    thinkingPromise = playThinkingSequence(currentRunId, "inbox");

    const results = [];
    let firstFailure = null;
    try {
      let threads = await extractThreads(tab.id);

      const preLoopSnap = getUsageSnapshot(sessionStore.getState().planTier);
      if (!preLoopSnap.hasProAccess && threads.length) {
        const remaining = Math.max(0, preLoopSnap.hardThreshold - preLoopSnap.totalOperatorRuns);
        if (remaining <= 0) {
          agentStore.setState((s) => ({ ...s, thinkingRunId: s.thinkingRunId + 1 }));
          usageChrome.notifyGateAttempt?.("scan");
          showStatus(
            "Included runs used — keep operating; copy, insert, and approvals stay on. Add runway when you’re ready.",
            false
          );
          if (emptyState) emptyState.style.display = "grid";
          return;
        }
        if (threads.length > remaining) {
          threads = threads.slice(0, remaining);
          showStatus(`Capacity: analyzing first ${remaining} visible row(s) this window.`, false);
        }
      }

      if (!threads.length) {
        agentStore.setState((s) => ({ ...s, thinkingRunId: s.thinkingRunId + 1 }));
        showStatus(
          {
            kind: "error",
            title: "No inbox rows detected",
            body: "Make sure you’re viewing the inbox list (not a single message) and try again.",
            action: { label: "Retry", onClick: scanInbox },
          },
          true
        );
        if (emptyState) emptyState.style.display = "grid";
        return;
      }

      console.log("[xalvion:scan] phase:rows_ready", { runId: currentRunId, rows: threads.length });

      const health = await pingOperatorHealth();
      if (!health.ok) {
        agentStore.setState((s) => ({ ...s, thinkingRunId: s.thinkingRunId + 1 }));
        disarmSlowNudge();
        await awaitThinkingSequenceCapped(thinkingPromise, 600);
        hideThinkingPanel();
        const { title, body } = describeOperatorHealthFailure(health);
        showStatus(
          {
            kind: "error",
            title,
            body,
            action: { label: "Retry", onClick: scanInbox },
          },
          true
        );
        if (emptyState) emptyState.style.display = "grid";
        return;
      }

      for (let i = 0; i < threads.length; i += 1) {
        showStatus(`Analyzing ${i + 1}/${threads.length} visible tickets…`);
        const r = await fetchJsonWithTimeout(
          OPERATOR_ANALYZE_URL,
          { text: threads[i] },
          INBOX_THREAD_FETCH_TIMEOUT_MS
        );
        if (r.ok && isRenderableAnalyzePayload(r.data)) {
          results.push(r.data);
        } else {
          if (!firstFailure) firstFailure = r;
          console.warn("[xalvion:scan] row_skipped", { index: i, ok: r.ok, kind: r.kind || "", status: r.status });
        }
      }
    } finally {
      disarmSlowNudge();
      await awaitThinkingSequenceCapped(thinkingPromise, THINKING_SEQUENCE_CAP_MS);
      hideThinkingPanel();
    }

    console.log("[xalvion:scan] phase:loop_done", { runId: currentRunId, resultCount: results.length });

    if (!results.length) {
      const fromFetch =
        firstFailure && !firstFailure.ok
          ? describeOperatorAnalyzeFailure(firstFailure, { actionLabel: "Scan inbox" })
          : null;
      showStatus(
        {
          kind: "error",
          title: fromFetch ? fromFetch.title : "No inbox results",
          body: fromFetch
            ? fromFetch.body
            : "We couldn’t get a decision for the visible rows. Confirm the operator app is running, then try Scan again.",
          action: { label: "Retry", onClick: scanInbox },
        },
        true
      );
      if (emptyState) emptyState.style.display = "grid";
      return;
    }

    try {
      await recordSuccessfulOperatorRuns(sessionStore.getState().planTier, results.length);
    } catch (usageErr) {
      console.warn("[xalvion:scan] usage record skipped", usageErr);
    }
    usageChrome.refreshUsageChrome();
    usageChrome.syncPrimaryRunButtons();

    const summary = buildInboxSummary(results);
    const summaryText =
      `${summary.total} tickets scanned\n` +
      `⚡ ${summary.auto} look routine to close\n` +
      `🧠 ${summary.review} need a closer read\n` +
      `⚠️ ${summary.risk} higher-risk\n` +
      `~${summary.minutesSaved} min estimated back`;

    showInboxSummary(summaryText);
    showHeaderInsight(`Inbox scan done — ${summary.auto}/${summary.total} visible rows look routine to clear.`);
    showStatus(`Inbox done — ~${summary.minutesSaved} min estimated back`);
  } catch (err) {
    disarmSlowNudge();
    agentStore.setState((s) => ({ ...s, thinkingRunId: s.thinkingRunId + 1 }));
    await awaitThinkingSequenceCapped(thinkingPromise, 800);
    hideThinkingPanel();
    console.warn("[xalvion:scan] phase:terminal_error", { message: String(err && err.message ? err.message : err) });
    showStatus(
      {
        kind: "error",
        title: "Inbox scan didn’t finish",
        body: `Try again in a moment. If this repeats, confirm the operator API is reachable at ${OPERATOR_CONNECTION_LABEL}.`,
        action: { label: "Retry", onClick: scanInbox },
      },
      true
    );
    if (emptyState) emptyState.style.display = "grid";
  } finally {
    disarmSlowNudge();
    uiStore.setState({ loading: false });
    setPrimaryButtonsBusy(false);
    usageChrome.syncPrimaryRunButtons();
    activeRunKind = "";
  }
}

if (replyToggleEditBtn) {
  replyToggleEditBtn.addEventListener("click", () => {
    if (!lastReply && !replyEditing) return;
    setReplyEditing(!replyEditing);
  });
}

if (gateEditBtn) {
  gateEditBtn.addEventListener("click", () => {
    setReplyEditing(true);
  });
}

if (gateDoneBtn) {
  gateDoneBtn.addEventListener("click", () => {
    setReplyEditing(false);
    if (approvalCompact) approvalCompact.classList.remove("is-visible");
    showStatus("Logged — copy or insert when you’re ready.");
  });
}

if (replyTextarea) {
  replyTextarea.addEventListener("input", () => {
    syncReplyFromTextarea();
    const has = !!normalize(replyTextarea.value);
    if (copyBtn) {
      copyBtn.disabled = !has;
      copyBtn.style.display = has ? "block" : "none";
    }
    if (insertBtn) {
      insertBtn.disabled = !has;
      insertBtn.style.display = has ? "block" : "none";
    }
  });
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
      showStatus(
        { title: "Copied", body: "Draft copied — paste into Gmail manually when you’re ready." },
        false
      );

      setTimeout(() => {
        copyBtn.textContent = original;
      }, 780);
    } catch (err) {
      console.error("Copy failed:", err);
      showStatus(
        {
          kind: "error",
          title: "Copy failed",
          body: "Your browser blocked clipboard access for this panel. Try selecting the reply text and copying manually.",
        },
        true
      );
    }
  });
}

if (insertBtn) {
  let insertInFlight = false;
  insertBtn.addEventListener("click", async () => {
    if (!lastReply) return;
    if (insertInFlight) return;
    insertInFlight = true;
    insertBtn.disabled = true;

    try {
      const tab = await chromeCtx.getActiveTab();

      if (!tab?.id) {
        showStatus(
          {
            kind: "error",
            title: "No active tab",
            body: "Focus Gmail in the foreground, then try Insert again.",
          },
          true
        );
        return;
      }

      const res = await insertIntoGmail(tab.id, lastReply, chromeApi);

      if (!res.ok) {
        const code = res.code || "";
        const detail = (res.detail && String(res.detail).trim()) || "";
        let title = "Couldn’t place text in Gmail";
        let body = detail;
        if (code === "no_compose") {
          title = "Open a reply box in Gmail, then try Insert";
          body =
            detail ||
            "Click Reply or Compose in Gmail, then click inside the message body before tapping Insert here.";
        } else if (code === "compose_disconnected") {
          title = "Compose closed before Insert finished";
          body = detail || "That compose window closed. Open the reply again, then try Insert.";
        } else if (!body) {
          body =
            "Focus the Gmail tab, open a reply or compose box, then try Insert again. Use Copy in this panel if you need the draft on your clipboard — then paste into Gmail manually.";
        }
        const copyHint =
          code === "no_compose" || code === "compose_disconnected"
            ? " Or use Copy in this panel, then paste into Gmail manually."
            : "";
        showStatus({ kind: "error", title, body: body + copyHint }, true);
        return;
      }

      const original = insertBtn.textContent;
      insertBtn.textContent = "Inserted ✓";
      showStatus(
        { title: "Inserted in Gmail", body: "Your draft is in the message body — give it a final read before sending." },
        false
      );

      setTimeout(() => {
        insertBtn.textContent = original;
      }, 780);
    } catch (err) {
      console.error("Insert failed:", err);
      showStatus(
        {
          kind: "error",
          title: "Couldn’t reach Gmail",
          body: "Focus the Gmail tab, open a reply or compose box, then try Insert again. Or use Copy and paste the reply into Gmail manually.",
        },
        true
      );
    } finally {
      insertInFlight = false;
      insertBtn.disabled = !lastReply;
    }
  });
}
