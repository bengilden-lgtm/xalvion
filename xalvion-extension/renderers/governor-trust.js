/**
 * Xalvion Extension — Governor / trust rendering
 * Owner: xalvion-extension/renderers
 *
 * Purpose:
 * - Normalize and render governor-related signals (policy, risk, approval state).
 * - Keep existing sidepanel UI behavior stable while isolating logic for maintainability.
 */

export function normalizeGovernorFactors(value) {
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
}

export function normalizeViolations(value) {
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
}

function formatGovernorRisk(governor_risk_level, governor_risk_score) {
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
}

export function deriveGovernorPresentation(data, getDecisionData) {
  const d = data && typeof data === "object" ? data : {};
  const dec = (getDecisionData ? getDecisionData(d) : null) || {};
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

  if (!hasGov) {
    return {
      label: "",
      cls: "",
      title: "",
      summary: "",
      nextStep: "",
      riskLabel: "",
      riskScoreLabel: "",
      factors: [],
      violations: [],
      mode: "unknown",
    };
  }

  const govReason = String(d.governor_reason || dec.governor_reason || "").trim();
  const govRiskLevel = String(d.governor_risk_level || dec.governor_risk_level || "").toLowerCase();
  const govRiskScore = d.governor_risk_score ?? dec.governor_risk_score;
  const factors = normalizeGovernorFactors(d.governor_factors ?? dec.governor_factors).slice(0, 12);
  const violations = normalizeViolations(d.violations ?? dec.violations).slice(0, 12);
  const riskChip = formatGovernorRisk(govRiskLevel, govRiskScore);

  const nextStep =
    execMode === "blocked"
      ? "Edit or escalate before execution."
      : execMode === "review"
        ? "Review and approve before execution."
        : execMode === "auto"
          ? "Action can proceed without operator intervention."
          : "";

  let mode = execMode || "unknown";
  if (mode === "auto" && (violations.length > 0 || govRiskLevel === "high")) {
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
    riskLabel: govRiskLevel
      ? govRiskLevel === "low"
        ? "Low risk"
        : govRiskLevel === "medium"
          ? "Medium risk"
          : govRiskLevel === "high"
            ? "High risk"
            : ""
      : "",
    riskScoreLabel: riskChip,
    factors,
    violations,
    mode: mode === "auto" || mode === "review" || mode === "blocked" ? mode : "unknown",
  };
}

export function renderConsequenceBar({
  data,
  consequenceSignal,
  deriveConsequencePresentation,
  getDecisionData,
}) {
  if (!consequenceSignal) return;
  // Governor trust signal parity: when governor fields are present, they become source-of-truth.
  const pres = (() => {
    const gov = deriveGovernorPresentation(data, getDecisionData);
    if (gov && gov.mode && gov.mode !== "unknown") {
      const text =
        gov.mode === "blocked"
          ? "⛔ Blocked by policy"
          : gov.mode === "review"
            ? "⚡ Approval required"
            : gov.mode === "auto"
              ? "✓ Safe to automate"
              : "○ Manual review";
      return { cls: gov.cls || "signal-review", text, title: gov.summary || gov.title || "" };
    }
    return deriveConsequencePresentation(data);
  })();
  consequenceSignal.textContent = pres.text;
  consequenceSignal.className = `consequence-signal ${pres.cls}`;
  if (pres.title) consequenceSignal.setAttribute("title", pres.title);
  else consequenceSignal.removeAttribute("title");
  consequenceSignal.classList.remove("is-hidden");
}

export function renderOperatorBrief({
  data,
  operatorBriefBody,
  addBriefLine,
  buildOperatorBriefLines,
  getDecisionData,
}) {
  if (!operatorBriefBody) return;
  operatorBriefBody.replaceChildren();
  const lines = buildOperatorBriefLines(data);
  for (const line of lines) {
    addBriefLine(operatorBriefBody, line.label, line.value);
  }

  // Governor visibility (optional): concise reason + factors + next step.
  try {
    const gov = deriveGovernorPresentation(data, getDecisionData);
    if (gov && gov.mode && gov.mode !== "unknown") {
      if (gov.summary) addBriefLine(operatorBriefBody, "Governor", gov.summary);
      if (gov.nextStep) addBriefLine(operatorBriefBody, "Next step", gov.nextStep);
      const riskText = String(gov.riskScoreLabel || gov.riskLabel || "").trim();
      if (riskText) addBriefLine(operatorBriefBody, "Risk", riskText);
      const factors = Array.isArray(gov.factors) ? gov.factors.slice(0, 3) : [];
      if (factors.length) {
        addBriefLine(operatorBriefBody, "Governor factors", factors[0]);
        for (const f of factors.slice(1)) addBriefLine(operatorBriefBody, "", f);
      }
      const violations = Array.isArray(gov.violations) ? gov.violations.slice(0, 3) : [];
      if (violations.length) {
        addBriefLine(operatorBriefBody, "Policy checks", violations[0]);
        for (const v of violations.slice(1)) addBriefLine(operatorBriefBody, "", v);
      }
    }
  } catch {}
}

function _coerceRate(v) {
  const n = Number(v);
  return Number.isFinite(n) && n >= 0 && n <= 1 ? n : null;
}

export function normalizeTrustDominance(data) {
  const d = data && typeof data === "object" ? data : {};
  const td = d.trust_dominance && typeof d.trust_dominance === "object" ? d.trust_dominance : {};
  const dec = d.sovereign_decision && typeof d.sovereign_decision === "object" ? d.sovereign_decision : d.decision || {};

  const similar = Math.max(0, Math.floor(Number(td.similar_case_count ?? dec.similar_case_count ?? 0) || 0));
  const sr = _coerceRate(td.historical_success_rate ?? dec.historical_success_rate);
  const reopenRiskRaw = String(td.reopen_risk || "unknown").toLowerCase();
  const reopenRisk = reopenRiskRaw === "low" || reopenRiskRaw === "medium" || reopenRiskRaw === "high" ? reopenRiskRaw : "unknown";
  const bandRaw = String(td.outcome_confidence_band || "uncertain").toLowerCase();
  const band = bandRaw === "tight" || bandRaw === "moderate" || bandRaw === "uncertain" ? bandRaw : "uncertain";
  const sparse = Boolean(td.sparse_history ?? (similar < 5 || sr === null));
  const severityRaw = String(td.severity || "").toLowerCase();
  const severity = severityRaw === "safe" || severityRaw === "review" || severityRaw === "risk"
    ? severityRaw
    : reopenRisk === "high" || band === "uncertain"
      ? "risk"
      : sr !== null && sr >= 0.88 && !sparse && (reopenRisk === "low" || reopenRisk === "unknown") && band !== "uncertain"
        ? "safe"
        : "review";

  const why = Array.isArray(td.why_factors) ? td.why_factors.map((x) => String(x || "").trim()).filter(Boolean).slice(0, 3) : [];
  const note = sparse ? String(td.conservative_note || "limited history — conservative decision") : "";

  return { similar, sr, reopenRisk, band, sparse, severity, why, note };
}

export function renderTrustDominanceStrip({ data, mountEl }) {
  if (!mountEl) return;
  const norm = normalizeTrustDominance(data);
  const tokens = [];

  if (norm.sr !== null && norm.similar >= 5) {
    tokens.push({ key: "success", label: `${Math.round(norm.sr * 100)}% success`, tone: norm.severity });
  } else {
    tokens.push({ key: "success", label: "Limited history", tone: "review" });
  }
  tokens.push({ key: "cases", label: `based on ${norm.similar} cases`, tone: "review" });
  tokens.push({
    key: "reopen",
    label: `reopen risk: ${norm.reopenRisk === "unknown" ? "—" : norm.reopenRisk}`,
    tone: norm.reopenRisk === "high" ? "risk" : norm.reopenRisk === "low" ? "safe" : "review",
  });
  tokens.push({
    key: "band",
    label: `outcome band: ${norm.band}`,
    tone: norm.band === "tight" ? "safe" : norm.band === "moderate" ? "review" : "risk",
  });

  mountEl.className = `trust-strip tone-${norm.severity}`;
  mountEl.innerHTML = tokens
    .slice(0, 4)
    .map((t) => `<span class="trust-pill tone-${t.tone}" data-token="${t.key}">${t.label}</span>`)
    .join("");

  const detailLines = []
    .concat(norm.note ? [norm.note] : [])
    .concat(norm.why || []);
  if (detailLines.length) {
    mountEl.setAttribute("title", detailLines.slice(0, 3).join("\n"));
  } else {
    mountEl.removeAttribute("title");
  }
}

