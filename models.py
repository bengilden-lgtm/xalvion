
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class AgentRequestContext(BaseModel):
    surface: str = "workspace"
    page_url: str | None = None
    host: str | None = None
    page_title: str | None = None
    app_name: str | None = None
    thread_id: str | None = None
    subject: str | None = None
    sender: str | None = None
    dom_excerpt: str | None = None
    selected_text: str | None = None


class ExtensionAnalyzeRequest(BaseModel):
    text: str
    sentiment: int | None = None
    ltv: int | None = None
    order_status: str | None = None
    payment_intent_id: str | None = None
    charge_id: str | None = None
    page_url: str | None = None
    host: str | None = None
    page_title: str | None = None
    app_name: str | None = None
    thread_id: str | None = None
    subject: str | None = None
    sender: str | None = None
    dom_excerpt: str | None = None
    selected_text: str | None = None

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        text = (v or "").strip()
        if not text:
            raise ValueError("text required")
        if len(text) > 50000:
            raise ValueError("text too long")
        return text


class ThinkingTraceStep(BaseModel):
    step: str
    status: Literal["queued", "done", "error"]
    detail: str | None = None


class TriageMetadata(BaseModel):
    urgency: int = 0
    churn_risk: int = 0
    refund_likelihood: int = 0
    abuse_likelihood: int = 0
    complexity: int = 0
    recommended_owner: str = "ai"
    risk_level: Literal["low", "medium", "high"] = "low"


class SovereignDecision(BaseModel):
    action: Literal["none", "refund", "credit", "review", "charge"] = "none"
    amount: float = 0
    confidence: float = 0
    reason: str = ""
    priority: Literal["low", "medium", "high"] = "medium"
    queue: str = "new"
    status: str = "new"
    risk_level: Literal["low", "medium", "high"] = "low"
    requires_approval: bool = False
    tool_status: str = "no_action"
    # governor.py (final authority layer) - optional, additive, safe if absent
    execution_mode: Literal["auto", "review", "blocked"] | None = None
    governor_reason: str | None = None
    governor_risk_level: Literal["low", "medium", "high"] | None = None
    governor_risk_score: int | None = None
    governor_factors: list[str] | None = None
    approved: bool | None = None
    violations: list[str] | None = None
    # Outcome-aware decision scoring (additive; deterministic; sparse-safe defaults)
    decision_confidence_breakdown: dict[str, Any] | None = None
    similar_case_count: int | None = None
    historical_success_rate: float | None = None
    historical_reopen_rate: float | None = None
    outcome_confidence_band: Literal["low", "medium", "high"] | None = None


class ImpactProjections(BaseModel):
    type: str = "saved"
    amount: float = 0
    money_saved: float = 0
    auto_resolved: bool = False
    agent_minutes_saved: int = 0
    signals: list[str] = Field(default_factory=list)
    revenue_at_risk: float = 0
    revenue_saved: float = 0
    churn_risk_delta: float = 0
    refund_cost: float = 0
    time_saved: float = 0
    confidence_band: dict[str, float] = Field(default_factory=dict)

    @field_validator("confidence_band", mode="before")
    @classmethod
    def _coerce_confidence_band(cls, v: Any) -> dict[str, float]:
        if v is None or v == {}:
            return {}
        if isinstance(v, dict):
            out: dict[str, float] = {}
            for k, x in v.items():
                try:
                    out[str(k)] = float(x)
                except Exception:
                    continue
            return out
        return {}


class MemoryDelta(BaseModel):
    plan_tier: str = "free"
    repeat_customer: bool = False
    refund_count: int = 0
    credit_count: int = 0
    review_count: int = 0
    complaint_count: int = 0
    abuse_score: int = 0
    sentiment_avg: float = 5.0
    last_issue_type: str = "general_support"


class OutputEnvelope(BaseModel):
    internal_note: str = ""
    customer_note: str = ""
    audit_log: str = ""


class CanonicalAgentResponse(BaseModel):
    reply: str
    final: str
    response: str
    issue_type: str
    mode: str
    quality: float
    triage_metadata: TriageMetadata
    sovereign_decision: SovereignDecision
    impact_projections: ImpactProjections
    memory_delta: MemoryDelta
    thinking_trace: list[ThinkingTraceStep] = Field(default_factory=list)
    request_context: AgentRequestContext | None = None
    output: OutputEnvelope
    decision_explanation: dict[str, Any] | None = None
    decision_explainability: dict[str, Any] | None = None
    execution_tier: str = "approval_required"
    # governor.py (final authority layer) - optional, additive, safe if absent
    execution_mode: Literal["auto", "review", "blocked"] | None = None
    governor_reason: str | None = None
    governor_risk_score: int | None = None
    governor_risk_level: Literal["low", "medium", "high"] | None = None
    governor_factors: list[str] | None = None
    approved: bool | None = None
    violations: list[str] | None = None
    # Enterprise trust / audit (additive; safe for clients — no secrets or raw tool payloads)
    outcome_key: str | None = None
    audit_summary: dict[str, Any] | None = None
