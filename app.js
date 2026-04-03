(() => {
  "use strict";

  const API = "";
  const TOKEN_KEY = "xalvion_token";
  const USER_KEY = "xalvion_user";
  const TIER_KEY = "xalvion_tier";
  const DRAFT_KEY = "xalvion_workspace_draft";
  const GUEST_USAGE_KEY = "xalvion_guest_usage";
  const GUEST_USAGE_RESET_KEY = "xalvion_guest_usage_reset_at";
  const GUEST_USAGE_LIMIT = 3;
  const FREE_USAGE_LIMIT = 12;
  const GUEST_USAGE_RESET_WINDOW_MS = 12 * 60 * 60 * 1000;

  const AUTH_DEBUG =
    typeof location !== "undefined" &&
    (location.hostname === "localhost" || location.hostname === "127.0.0.1");

  function authDebugLog(label, detail) {
    if (!AUTH_DEBUG) return;
    try {
      const msg = detail && (detail.message || String(detail));
      if (msg) console.warn(`[xalvion:auth] ${label}`, msg);
      else console.warn(`[xalvion:auth] ${label}`);
    } catch {}
  }

// ===== SAFE FALLBACK FOR pulseRail =====
if (typeof window.pulseRail !== "function") {
  window.pulseRail = function () {
    console.warn("pulseRail fallback triggered");
  };
}
  const els = {
    messages: document.getElementById("messages"),
    messageInput: document.getElementById("messageInput"),
    sendBtn: document.getElementById("sendBtn"),
    signupBtn: document.getElementById("signupBtn"),
    loginBtn: document.getElementById("loginBtn"),
    devBtn: document.getElementById("devBtn"),
    logoutBtn: document.getElementById("logoutBtn"),
    newChatBtn: document.getElementById("newChatBtn"),
    usernameInput: document.getElementById("usernameInput"),
    passwordInput: document.getElementById("passwordInput"),
    notice: document.getElementById("notice"),
    noticeTitle: document.getElementById("noticeTitle"),
    noticeDetail: document.getElementById("noticeDetail"),
    backendStatus: document.getElementById("backendStatus"),
    authStatus: document.getElementById("authStatus"),
    streamStatus: document.getElementById("streamStatus"),
    statInteractions: document.getElementById("statInteractions"),
    statQuality: document.getElementById("statQuality"),
    statConfidence: document.getElementById("statConfidence"),
    statActions: document.getElementById("statActions"),
    planTier: document.getElementById("planTier"),
    planUsage: document.getElementById("planUsage"),
    planUsed: document.getElementById("planUsed"),
    planRemaining: document.getElementById("planRemaining"),
    planBar: document.getElementById("planBar"),
    usagePanelCopy: document.getElementById("usagePanelCopy"),
    systemPanelCopy: document.getElementById("systemPanelCopy"),
    brandSubcopy: document.getElementById("brandSubcopy"),
    workspaceSubcopy: document.getElementById("workspaceSubcopy"),
    workspaceHeadline: document.getElementById("workspaceHeadline"),
    dashboardCard: document.getElementById("dashboardCard"),
    usageCard: document.getElementById("usageCard"),
    accountCard: document.getElementById("accountCard"),
    paymentIntentInput: document.getElementById("paymentIntentInput"),
    chargeIdInput: document.getElementById("chargeIdInput"),
    railInner: document.querySelector(".rail-inner"),
    messagesShell: document.getElementById("messagesShell"),
    upgradeButtons: Array.from(document.querySelectorAll("[data-upgrade]")),
    fillButtons: Array.from(document.querySelectorAll("[data-fill]")),
    stripeStatus: document.getElementById("stripeStatus"),
    stripeConnectBtn: document.getElementById("stripeConnectBtn"),
    stripeDisconnectBtn: document.getElementById("stripeDisconnectBtn"),
    stripeAccountPill: document.getElementById("stripeAccountPill"),
    stripeModePill: document.getElementById("stripeModePill"),
    stripeIntegrationCopy: document.getElementById("stripeIntegrationCopy"),
    refundCenterCard: document.getElementById("refundCenterCard"),
    refundTierAccess: document.getElementById("refundTierAccess"),
    refundHistoryCount: document.getElementById("refundHistoryCount"),
    refundCenterCopy: document.getElementById("refundCenterCopy"),
    openRefundModalBtn: document.getElementById("openRefundModalBtn"),
    refreshRefundHistoryBtn: document.getElementById("refreshRefundHistoryBtn"),
    refundHistoryList: document.getElementById("refundHistoryList"),
    refundModal: document.getElementById("refundModal"),
    closeRefundModalBtn: document.getElementById("closeRefundModalBtn"),
    cancelRefundModalBtn: document.getElementById("cancelRefundModalBtn"),
    executeRefundBtn: document.getElementById("executeRefundBtn"),
    refundModalNote: document.getElementById("refundModalNote"),
    refundPaymentIntentInput: document.getElementById("refundPaymentIntentInput"),
    refundChargeInput: document.getElementById("refundChargeInput"),
    refundAmountInput: document.getElementById("refundAmountInput"),
    refundReasonSelect: document.getElementById("refundReasonSelect"),
    crmCard: document.getElementById("crmCard"),
    crmSummary: document.getElementById("crmSummary"),
    crmNewCount: document.getElementById("crmNewCount"),
    crmDueCount: document.getElementById("crmDueCount"),
    refreshLeadsBtn: document.getElementById("refreshLeadsBtn"),
    addLeadBtn: document.getElementById("addLeadBtn"),
    leadUsernameInput: document.getElementById("leadUsernameInput"),
    leadSourceInput: document.getElementById("leadSourceInput"),
    leadTextInput: document.getElementById("leadTextInput"),
    leadList: document.getElementById("leadList"),
    followupList: document.getElementById("followupList"),
    crmTodayCard: document.getElementById("crmTodayCard"),
    crmTodaySummary: document.getElementById("crmTodaySummary"),
    crmTodayDueCount: document.getElementById("crmTodayDueCount"),
    crmTodayNewCount: document.getElementById("crmTodayNewCount"),
    crmTodayClosedCount: document.getElementById("crmTodayClosedCount"),
    crmTodayBestSource: document.getElementById("crmTodayBestSource"),
    crmHotList: document.getElementById("crmHotList"),
    revenueSummary: document.getElementById("revenueSummary"),
    revenueLeadsCount: document.getElementById("revenueLeadsCount"),
    revenueReplyRate: document.getElementById("revenueReplyRate"),
    revenueClosingRate: document.getElementById("revenueClosingRate"),
    revenueWinRate: document.getElementById("revenueWinRate"),
    revenueTotalValue: document.getElementById("revenueTotalValue"),
    revenueBestSource: document.getElementById("revenueBestSource"),
    sourceList: document.getElementById("sourceList"),
    forecastSummary: document.getElementById("forecastSummary"),
    forecastPipelineValue: document.getElementById("forecastPipelineValue"),
    forecastWeightedRevenue: document.getElementById("forecastWeightedRevenue"),
    forecastProjectedRevenue: document.getElementById("forecastProjectedRevenue"),
    forecastCoverage: document.getElementById("forecastCoverage"),
    forecastStageList: document.getElementById("forecastStageList"),
    forecastDealList: document.getElementById("forecastDealList"),
    upgradeValueSummary: document.getElementById("upgradeValueSummary")
  };

  const state = {
    token: localStorage.getItem(TOKEN_KEY) || "",
    username: localStorage.getItem(USER_KEY) || "",
    tier: localStorage.getItem(TIER_KEY) || "free",
    usage: Number(localStorage.getItem(GUEST_USAGE_KEY) || 0) || 0,
    limit: GUEST_USAGE_LIMIT,
    remaining: Math.max(0, GUEST_USAGE_LIMIT - (Number(localStorage.getItem(GUEST_USAGE_KEY) || 0) || 0)),
    sending: false,
    actionsCount: 0,
    totalInteractions: 0,
    avgConfidence: 0,
    avgQuality: 0,
    latestRun: null,
    stickToBottom: true,
    stripeConnected: false,
    stripeAccountId: "",
    stripeMode: "",
    refundHistory: [],
    crmLeads: [],
    crmSummary: { new: 0, contacted: 0, replied: 0, closed: 0, due_followups: 0 },
    crmDailySummary: { due_followups: 0, new_today: 0, closed_today: 0, best_source: "manual", hottest_open: [], reminders: [] },
    revenueMetrics: { totals: {}, by_source: [], best_source: "manual", forecast: {} },
    lastLimitNoticeKey: "",
    authSubmitting: false,
    usagePct: 0,
    approachingLimit: false,
    atLimit: false,
    valueSignals: null,
    dashboardStats: null
  };

  const ICONS = {
    copy: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <rect x="5" y="5" width="8" height="8" rx="1.5"></rect>
        <path d="M3 11V3a1 1 0 011-1h8"></path>
      </svg>
    `,
    check: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M3 8l3.5 3.5L13 4"></path>
      </svg>
    `,
    spark: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M8 1.8l1.2 3 3 1.2-3 1.2-1.2 3-1.2-3-3-1.2 3-1.2 1.2-3Z"></path>
        <path d="M12.4 10.8l.6 1.6 1.6.6-1.6.6-.6 1.6-.6-1.6-1.6-.6 1.6-.6.6-1.6Z"></path>
      </svg>
    `,
    person: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="8" cy="5.5" r="2.5"></circle>
        <path d="M3 13c0-2.76 2.24-5 5-5s5 2.24 5 5"></path>
      </svg>
    `,
    refund: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M13 5a5 5 0 10-1.4 3.46"></path>
        <path d="M13 1.5V5h-3.5"></path>
        <path d="M5.2 8h5.6"></path>
        <path d="M5.8 10.5h4.4"></path>
      </svg>
    `,
    credit: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <rect x="2" y="3" width="12" height="10" rx="2"></rect>
        <path d="M2 6.5h12"></path>
        <path d="M5 10h2.5"></path>
      </svg>
    `,
    review: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="8" cy="8" r="5.5"></circle>
        <path d="M8 5.2v3.2"></path>
        <path d="M8 10.9h.01"></path>
      </svg>
    `,
    status: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M3 12.5h10"></path>
        <path d="M4.5 10V6.5"></path>
        <path d="M8 10V4.5"></path>
        <path d="M11.5 10V7.5"></path>
      </svg>
    `,
    shield: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M8 2L3 4v4c0 3 2.5 5.5 5 6 2.5-.5 5-3 5-6V4L8 2z"></path>
      </svg>
    `,
    pulse: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M1 8h2.5l2-4.5 2.5 9L10 6l1.5 2H15"></path>
      </svg>
    `,
    money: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <rect x="1.5" y="4" width="13" height="9" rx="2"></rect>
        <path d="M8 7.5a1.5 1.5 0 100 3 1.5 1.5 0 000-3z"></path>
        <path d="M4.5 9h-.5M12 9h-.5"></path>
      </svg>
    `,
    warn: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M8 2L1.5 13h13L8 2z"></path>
        <path d="M8 6v3.5"></path>
        <path d="M8 11.5h.01"></path>
      </svg>
    `,
    ticket: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M2.5 5.2V4A1.5 1.5 0 014 2.5h8A1.5 1.5 0 0113.5 4v1.2a1.7 1.7 0 010 5.6V12A1.5 1.5 0 0112 13.5H4A1.5 1.5 0 012.5 12v-1.2a1.7 1.7 0 010-5.6Z"></path>
        <path d="M8 5v6"></path>
      </svg>
    `,
    chevron: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M4.5 6.5L8 10l3.5-3.5"></path>
      </svg>
    `,
    send: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M13.5 2.5L7 9"></path>
        <path d="M13.5 2.5L9 13.5 7 9l-4.5-2 11-4.5Z"></path>
      </svg>
    `,
    approve: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M3 8.4 6.2 11.4 13 4.6"></path>
      </svg>
    `,
    reject: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M4 4l8 8"></path>
        <path d="M12 4 4 12"></path>
      </svg>
    `,
    edit: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M3 11.8 3.4 9.4 9.9 2.9a1.4 1.4 0 0 1 2 0l1.2 1.2a1.4 1.4 0 0 1 0 2l-6.5 6.5L4.2 13z"></path>
        <path d="M9 4l3 3"></path>
      </svg>
    `
  };

  function ensureInjectedStyles() {
    if (document.getElementById("xalvion-runtime-styles")) return;

    const style = document.createElement("style");
    style.id = "xalvion-runtime-styles";
    style.textContent = `
      .messages{
        gap:10px !important;
        padding:12px 16px 10px !important;
        scroll-padding-bottom:10px !important;
      }

      .msg-group{
        display:flex;
        flex-direction:column;
        gap:6px;
        animation:xalvionIn .16s cubic-bezier(.22,1,.36,1) both;
      }

      .msg-group.user{align-items:flex-end}
      .msg-group.assistant{align-items:flex-start}

      @keyframes xalvionIn{
        from{opacity:0;transform:translateY(6px)}
        to{opacity:1;transform:translateY(0)}
      }

      .msg-card{
        width:min(820px,100%);
        max-width:min(820px,100%);
        border-radius:16px;
        border:1px solid rgba(255,255,255,.06);
        overflow:hidden;
        position:relative;
        box-shadow:0 8px 20px rgba(0,0,0,.10);
        transition:
          transform .16s cubic-bezier(.22,1,.36,1),
          border-color .16s ease,
          box-shadow .16s ease,
          background .16s ease;
      }

      .msg-card:hover{
        transform:translateY(-1px);
        border-color:rgba(255,255,255,.09);
        box-shadow:0 12px 24px rgba(0,0,0,.14);
      }

      .msg-card.user{
        background:
          linear-gradient(180deg, rgba(90,120,255,.11), rgba(90,120,255,.05)),
          rgba(255,255,255,.018);
        border-color:rgba(125,145,255,.14);
      }

      .msg-card.assistant{
        background:
          linear-gradient(180deg, rgba(255,255,255,.028), rgba(255,255,255,.012)),
          radial-gradient(circle at 84% 18%, rgba(139,111,255,.04), transparent 28%);
      }

      .msg-head{
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:10px;
        padding:8px 10px 7px;
        border-bottom:1px solid rgba(255,255,255,.04);
      }

      .msg-who{
        display:flex;
        align-items:center;
        gap:7px;
        min-width:0;
        font-size:9px;
        text-transform:uppercase;
        letter-spacing:.14em;
        color:rgba(188,202,240,.54);
        font-weight:800;
      }

      .msg-badge{
        width:18px;
        height:18px;
        border-radius:6px;
        display:flex;
        align-items:center;
        justify-content:center;
        background:rgba(255,255,255,.04);
        border:1px solid rgba(255,255,255,.05);
        flex:0 0 18px;
      }

      .msg-badge svg{
        width:10px;
        height:10px;
        opacity:.9;
      }

      .msg-time{
        white-space:nowrap;
        color:rgba(175,191,233,.40);
        font-size:9px;
        letter-spacing:.08em;
        text-transform:uppercase;
      }

      .msg-body{
        padding:9px 10px 10px;
        display:flex;
        flex-direction:column;
        gap:8px;
      }

      .reply-text{
        font-size:13.5px;
        line-height:1.5;
        color:rgba(239,244,255,.97);
        word-break:break-word;
        white-space:pre-wrap;
      }

      .msg-card.user .reply-text{
        color:rgba(218,228,252,.92);
      }

      .assistant-footer{
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:8px;
        flex-wrap:wrap;
      }

      .assistant-meta{
        display:flex;
        align-items:center;
        gap:5px;
        flex-wrap:wrap;
      }

      .meta-chip{
        display:inline-flex;
        align-items:center;
        gap:5px;
        min-height:20px;
        padding:0 7px;
        border-radius:999px;
        border:1px solid rgba(255,255,255,.06);
        background:rgba(255,255,255,.025);
        color:rgba(220,230,252,.74);
        font-size:9px;
        font-weight:700;
        letter-spacing:.02em;
        transition:
          transform .14s ease,
          background .14s ease,
          border-color .14s ease,
          color .14s ease;
      }

      .meta-chip:hover{
        transform:translateY(-1px);
        background:rgba(255,255,255,.04);
        border-color:rgba(255,255,255,.10);
        color:rgba(232,239,255,.90);
      }

      .meta-chip svg{
        width:9px;
        height:9px;
        opacity:.8;
      }

      .meta-chip.safe{
        border-color:rgba(52,211,153,.14);
        background:rgba(52,211,153,.06);
        color:rgba(205,255,230,.94);
      }

      .meta-chip.review{
        border-color:rgba(245,158,11,.14);
        background:rgba(245,158,11,.06);
        color:rgba(255,234,194,.94);
      }

      .meta-chip.risky{
        border-color:rgba(248,113,113,.14);
        background:rgba(248,113,113,.06);
        color:rgba(255,220,220,.94);
      }

      .assistant-tools{
        display:flex;
        align-items:center;
        gap:6px;
        flex-wrap:wrap;
      }

      .mini-btn{
        display:inline-flex;
        align-items:center;
        justify-content:center;
        gap:6px;
        min-height:24px;
        padding:0 8px;
        border-radius:8px;
        border:1px solid rgba(255,255,255,.07);
        background:rgba(255,255,255,.035);
        color:rgba(232,238,255,.88);
        transition:
          transform .14s ease,
          background .14s ease,
          border-color .14s ease,
          color .14s ease,
          box-shadow .14s ease;
        cursor:pointer;
        font-size:10px;
        font-weight:700;
      }

      .mini-btn:hover{
        transform:translateY(-1px);
        background:rgba(255,255,255,.055);
        border-color:rgba(255,255,255,.10);
        color:rgba(245,248,255,.96);
        box-shadow:0 6px 16px rgba(0,0,0,.12);
      }

      .mini-btn svg{
        width:12px;
        height:12px;
      }

      .copy-btn{
        min-width:24px;
      }

      .mini-btn.approve-btn{
        background:rgba(52,211,153,.12);
        border-color:rgba(52,211,153,.18);
        color:rgba(221,255,239,.96);
        padding:0 10px;
      }

      .mini-btn.reject-btn{
        background:rgba(248,113,113,.10);
        border-color:rgba(248,113,113,.18);
        color:rgba(255,224,224,.96);
        padding:0 10px;
      }

      .mini-btn.edit-btn{
        background:rgba(96,165,250,.10);
        border-color:rgba(96,165,250,.18);
        color:rgba(224,236,255,.96);
        padding:0 10px;
      }

      .approval-banner{
        display:flex;
        align-items:flex-start;
        gap:8px;
        padding:9px 10px;
        border-radius:12px;
        border:1px solid rgba(245,158,11,.18);
        background:rgba(245,158,11,.08);
        color:rgba(255,239,210,.96);
        font-size:11px;
        line-height:1.5;
      }

      .approval-banner svg{
        width:13px;
        height:13px;
        flex:0 0 13px;
        margin-top:1px;
      }

      .details-wrap{
        margin-top:0;
      }

      .details-toggle{
        list-style:none;
        display:inline-flex;
        align-items:center;
        gap:6px;
        min-height:24px;
        padding:0 8px;
        border-radius:8px;
        border:1px solid rgba(255,255,255,.06);
        background:rgba(255,255,255,.02);
        color:rgba(208,220,252,.72);
        font-size:10px;
        font-weight:700;
        cursor:pointer;
        user-select:none;
        transition:
          transform .14s ease,
          background .14s ease,
          border-color .14s ease,
          color .14s ease;
      }

      .details-toggle::-webkit-details-marker{display:none}

      .details-toggle:hover{
        transform:translateY(-1px);
        background:rgba(255,255,255,.04);
        border-color:rgba(255,255,255,.10);
        color:rgba(236,242,255,.94);
      }

      .details-wrap[open] .details-toggle{
        background:rgba(255,255,255,.045);
        border-color:rgba(139,111,255,.14);
      }

      .details-wrap[open] .details-toggle .chev{
        transform:rotate(180deg);
      }

      .details-toggle .chev{
        width:11px;
        height:11px;
        transition:transform .18s ease;
      }

      .details-panel{
        margin-top:7px;
        display:grid;
        gap:7px;
        border-radius:12px;
        border:1px solid rgba(255,255,255,.05);
        background:
          linear-gradient(180deg, rgba(255,255,255,.022), rgba(255,255,255,.010)),
          radial-gradient(circle at 88% 18%, rgba(139,111,255,.045), transparent 28%);
        padding:8px;
        animation:xalvionDetailsIn .16s ease;
      }

      @keyframes xalvionDetailsIn{
        from{opacity:0;transform:translateY(-2px)}
        to{opacity:1;transform:translateY(0)}
      }

      .details-grid{
        display:grid;
        grid-template-columns:repeat(2,minmax(0,1fr));
        gap:6px;
      }

      .details-box{
        display:grid;
        gap:2px;
        padding:7px;
        border-radius:10px;
        border:1px solid rgba(255,255,255,.045);
        background:rgba(255,255,255,.018);
        transition:background .14s ease,border-color .14s ease,transform .14s ease;
      }

      .details-box:hover{
        transform:translateY(-1px);
        background:rgba(255,255,255,.028);
        border-color:rgba(255,255,255,.08);
      }

      .details-label{
        font-size:8px;
        letter-spacing:.12em;
        text-transform:uppercase;
        font-weight:800;
        color:rgba(188,201,238,.44);
      }

      .details-value{
        font-size:11px;
        line-height:1.35;
        color:rgba(240,245,255,.92);
        word-break:break-word;
      }

      .details-note{
        padding:7px 8px;
        border-radius:10px;
        border:1px solid rgba(255,255,255,.045);
        background:rgba(255,255,255,.018);
        color:rgba(205,218,250,.76);
        font-size:11px;
        line-height:1.45;
        white-space:pre-wrap;
        word-break:break-word;
      }

      .details-insight-stack{
        display:grid;
        gap:6px;
        padding:2px 0 4px;
      }

      .details-insight{
        display:grid;
        gap:3px;
        padding:8px 9px;
        border-radius:10px;
        border:1px solid rgba(255,255,255,.04);
        background:rgba(5,8,16,.42);
      }

      .details-insight-k{
        font-size:8px;
        letter-spacing:.14em;
        text-transform:uppercase;
        font-weight:800;
        color:rgba(139,111,255,.72);
      }

      .details-insight-v{
        font-size:11px;
        line-height:1.42;
        color:rgba(228,235,255,.88);
        word-break:break-word;
      }

      .details-trace{
        font-size:10px;
        line-height:1.4;
        color:rgba(198,210,240,.62);
        font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
        white-space:pre-wrap;
        word-break:break-word;
        max-height:96px;
        overflow:auto;
      }

      .operator-reply-editor-wrap{
        margin-top:10px;
        display:grid;
        gap:6px;
      }

      .operator-reply-editor-wrap[hidden]{
        display:none !important;
      }

      .operator-editor-label{
        font-size:9px;
        letter-spacing:.12em;
        text-transform:uppercase;
        font-weight:800;
        color:rgba(188,201,238,.5);
      }

      .operator-reply-editor{
        width:100%;
        min-height:80px;
        max-height:220px;
        padding:10px 12px;
        border-radius:12px;
        border:1px solid rgba(255,255,255,.09);
        background:rgba(6,8,15,.55);
        color:rgba(240,245,255,.95);
        font-size:12px;
        line-height:1.45;
        resize:vertical;
        font-family:inherit;
      }

      .operator-reply-editor:focus{
        outline:none;
        border-color:rgba(139,111,255,.28);
        box-shadow:0 0 0 1px rgba(139,111,255,.12);
      }

      .mini-btn.apply-edit-btn{
        background:rgba(52,211,153,.08);
        border-color:rgba(52,211,153,.16);
        color:rgba(220,255,236,.92);
        padding:0 10px;
      }

      .approval-hint{
        font-size:10px;
        color:rgba(206,219,250,.55);
        padding:4px 2px 0;
        line-height:1.35;
      }

      .stream-steps{
        display:flex;
        flex-wrap:wrap;
        gap:5px;
        margin-bottom:0;
      }

      .stream-step{
        display:inline-flex;
        align-items:center;
        gap:6px;
        min-height:20px;
        padding:0 7px;
        border-radius:999px;
        border:1px solid rgba(255,255,255,.05);
        background:rgba(255,255,255,.02);
        color:rgba(206,219,250,.62);
        font-size:9px;
        letter-spacing:.04em;
        text-transform:uppercase;
        font-weight:800;
        transition:all .18s ease;
      }

      .stream-step-dot{
        width:5px;
        height:5px;
        border-radius:50%;
        background:rgba(255,255,255,.18);
        transition:all .18s ease;
      }

      .stream-step.active{
        border-color:rgba(79,158,255,.16);
        background:rgba(79,158,255,.08);
        color:rgba(224,236,255,.94);
      }

      .stream-step.active .stream-step-dot{
        background:#60a5fa;
        box-shadow:0 0 7px rgba(96,165,250,.55);
      }

      .stream-step.done{
        border-color:rgba(52,211,153,.14);
        background:rgba(52,211,153,.08);
        color:rgba(212,255,232,.92);
      }

      .stream-step.done .stream-step-dot{
        background:#34d399;
        box-shadow:0 0 7px rgba(52,211,153,.55);
      }

      .typing{
        display:inline-flex;
        align-items:center;
        gap:5px;
      }

      .typing-dot{
        width:5px;
        height:5px;
        border-radius:50%;
        background:rgba(220,232,255,.52);
        animation:xalvionTyping 1s infinite ease-in-out;
      }

      .typing-dot:nth-child(2){animation-delay:.12s}
      .typing-dot:nth-child(3){animation-delay:.24s}

      @keyframes xalvionTyping{
        0%,80%,100%{transform:translateY(0);opacity:.4}
        40%{transform:translateY(-3px);opacity:1}
      }

      .empty-state{
        width:100%;
        min-height:100%;
        margin:0;
        padding:20px 12px 28px;
        display:flex;
        flex-direction:column;
        align-items:center;
        justify-content:flex-start;
        box-sizing:border-box;
      }

      .empty-state .empty-card{
        width:min(940px,100%);
      }

      .empty-state .empty-card h1{
        margin-top:14px;
      }

      .empty-state .empty-card p{
        margin-top:14px;
        color:rgba(220,232,252,.92);
        font-size:14.5px;
        line-height:1.72;
        max-width:none;
      }

      .rev-card,.ops-card{
        border-radius:22px;
        padding:14px;
        background:rgba(255,255,255,.03);
        border:1px solid rgba(255,255,255,.06);
        display:grid;
        gap:12px;
        transition:border-color .16s ease, background .16s ease, transform .16s ease;
      }

      .rev-card:hover,.ops-card:hover{
        border-color:rgba(139,111,255,.10);
        background:rgba(255,255,255,.035);
        transform:translateY(-1px);
      }

      .rev-grid,.ops-grid{
        display:grid;
        grid-template-columns:1fr 1fr;
        gap:8px;
      }

      .rev-metric,.ops-metric{
        border-radius:14px;
        border:1px solid rgba(255,255,255,.06);
        background:rgba(255,255,255,.028);
        padding:10px;
        display:grid;
        gap:4px;
      }

      .rev-metric-label,.ops-metric-label{
        font-size:10px;
        letter-spacing:.12em;
        text-transform:uppercase;
        font-weight:800;
        color:rgba(188,201,238,.46);
      }

      .rev-metric-value,.ops-metric-value{
        font-size:18px;
        font-weight:800;
        color:rgba(244,247,255,.96);
      }

      .rev-bar{
        width:100%;
        height:10px;
        border-radius:999px;
        overflow:hidden;
        background:rgba(255,255,255,.05);
        border:1px solid rgba(255,255,255,.05);
        position:relative;
      }

      .rev-bar > div{
        width:0%;
        height:100%;
        border-radius:inherit;
        background:linear-gradient(90deg, rgba(124,92,252,.95), rgba(66,153,225,.95));
        transition:width .25s ease;
      }

      .ops-run-line{
        display:flex;
        align-items:flex-start;
        gap:8px;
        min-height:28px;
        color:rgba(220,230,252,.82);
        font-size:12px;
        line-height:1.55;
      }

      .ops-run-line svg{
        width:12px;
        height:12px;
        margin-top:2px;
        opacity:.82;
        flex:0 0 12px;
      }

      .composer-input-wrap{
        transition:
          box-shadow .18s ease,
          border-color .18s ease,
          background .18s ease,
          transform .18s ease !important;
      }

      .composer-input-wrap:focus-within{
        transform:translateY(-1px);
      }

      .composer-live{
        box-shadow:0 0 0 1px rgba(96,165,250,.20), 0 0 26px rgba(96,165,250,.10);
      }

      .shell-live{
        animation:xalvionShellPulse 1.6s ease;
      }

      @keyframes xalvionShellPulse{
        0%{box-shadow:0 30px 80px rgba(0,0,0,.34)}
        40%{box-shadow:0 30px 80px rgba(0,0,0,.34), 0 0 0 1px rgba(139,111,255,.16), 0 0 26px rgba(139,111,255,.12)}
        100%{box-shadow:0 30px 80px rgba(0,0,0,.34)}
      }

      .send-btn{
        width:38px !important;
        height:38px !important;
        min-width:38px !important;
        max-width:38px !important;
        flex:0 0 38px !important;
        align-self:flex-end !important;
        display:inline-flex !important;
        align-items:center !important;
        justify-content:center !important;
        padding:0 !important;
        border-radius:10px !important;
        border:1px solid rgba(255,255,255,.08) !important;
        background:rgba(255,255,255,.04) !important;
        box-shadow:
          0 8px 18px rgba(0,0,0,.12),
          inset 0 1px 0 rgba(255,255,255,.05) !important;
        transition:
          transform .14s ease,
          background .14s ease,
          border-color .14s ease,
          box-shadow .14s ease,
          filter .14s ease !important;
      }

      .send-btn:hover{
        transform:translateY(-1px) scale(1.02) !important;
        background:rgba(255,255,255,.075) !important;
        border-color:rgba(255,255,255,.13) !important;
        box-shadow:
          0 12px 22px rgba(0,0,0,.16),
          0 0 0 1px rgba(255,255,255,.02),
          inset 0 1px 0 rgba(255,255,255,.07) !important;
      }

      .send-btn:active{
        transform:translateY(0) scale(.97) !important;
      }

      .send-btn:disabled{
        opacity:.68;
        transform:none !important;
      }

      .send-btn svg{
        width:15px !important;
        height:15px !important;
        transform:none !important;
      }

      .mobile-scroll-mode,
      .mobile-scroll-mode body{
        overflow-y:auto !important;
        overflow-x:hidden !important;
        height:auto !important;
        min-height:100% !important;
      }

      .mobile-scroll-mode .app{
        height:auto !important;
        min-height:var(--app-height, 100dvh) !important;
      }

      .mobile-scroll-mode .sidebar,
      .mobile-scroll-mode .main,
      .mobile-scroll-mode .rail{
        height:auto !important;
        min-height:0 !important;
      }

      .mobile-scroll-mode .main{
        overflow:visible !important;
      }

      .mobile-scroll-mode .workspace,
      .mobile-scroll-mode .messages-shell,
      .mobile-scroll-mode .composer-wrap{
        overflow:visible !important;
      }

      .mobile-scroll-mode .messages{
        height:auto !important;
        max-height:none !important;
        overflow:visible !important;
      }

      @media (max-width: 980px){
        .mobile-scroll-mode .app{
          grid-template-columns:1fr !important;
          gap:10px !important;
        }

        .mobile-scroll-mode .sidebar,
        .mobile-scroll-mode .rail{
          display:none !important;
        }

        .mobile-scroll-mode .main{
          min-height:var(--app-height, 100dvh) !important;
        }

        .mobile-scroll-mode .workspace{
          min-height:0 !important;
        }
      }

      @media (max-width: 720px){
        .msg-card{width:100%}
        .details-grid,.rev-grid,.ops-grid{grid-template-columns:1fr}
        .messages{padding:10px 10px 8px !important}
        .send-btn{
          width:36px !important;
          height:36px !important;
          min-width:36px !important;
          max-width:36px !important;
          flex:0 0 36px !important;
        }
      }
    `;
    document.head.appendChild(style);
  }

  
  function ensureCrmStyles() {
    if (document.getElementById("xalvion-crm-styles")) return;

    const style = document.createElement("style");
    style.id = "xalvion-crm-styles";
    style.textContent = `
      .crm-list{
        display:grid;
        gap:10px;
      }

      .crm-hot-item{
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:10px;
        padding:10px 12px;
        border-radius:14px;
        border:1px solid rgba(255,255,255,.06);
        background:rgba(255,255,255,.025);
      }

      .crm-hot-copy{
        display:grid;
        gap:3px;
        min-width:0;
      }

      .crm-hot-title{
        font-size:12px;
        font-weight:800;
        color:rgba(244,247,255,.96);
      }

      .crm-hot-sub{
        font-size:11px;
        color:rgba(198,210,238,.72);
        white-space:normal;
      }

      .crm-item{
        display:grid;
        gap:10px;
        padding:12px;
        border-radius:16px;
        border:1px solid rgba(255,255,255,.06);
        background:rgba(255,255,255,.025);
      }

      .crm-item-head{
        display:flex;
        align-items:flex-start;
        justify-content:space-between;
        gap:10px;
      }

      .crm-item-title{
        font-size:13px;
        font-weight:800;
        color:rgba(244,247,255,.96);
        line-height:1.35;
      }

      .crm-item-sub{
        margin-top:4px;
        font-size:11px;
        color:rgba(204,216,246,.72);
        line-height:1.55;
        white-space:pre-wrap;
        word-break:break-word;
      }

      .crm-chip-row{
        display:flex;
        flex-wrap:wrap;
        gap:6px;
      }

      .crm-chip{
        display:inline-flex;
        align-items:center;
        gap:6px;
        min-height:22px;
        padding:0 8px;
        border-radius:999px;
        border:1px solid rgba(255,255,255,.06);
        background:rgba(255,255,255,.03);
        color:rgba(224,233,255,.78);
        font-size:10px;
        font-weight:700;
        letter-spacing:.03em;
      }

      .crm-chip.status-contacted{border-color:rgba(96,165,250,.18);background:rgba(96,165,250,.08);color:rgba(226,237,255,.96);}
      .crm-chip.status-replied{border-color:rgba(52,211,153,.18);background:rgba(52,211,153,.08);color:rgba(222,255,238,.96);}
      .crm-chip.status-closed{border-color:rgba(248,113,113,.18);background:rgba(248,113,113,.08);color:rgba(255,228,228,.96);}

      .crm-message{
        padding:10px 11px;
        border-radius:12px;
        border:1px solid rgba(255,255,255,.05);
        background:rgba(255,255,255,.02);
        color:rgba(235,241,255,.90);
        font-size:11.5px;
        line-height:1.65;
        white-space:pre-wrap;
        word-break:break-word;
      }

      .crm-actions{
        display:flex;
        flex-wrap:wrap;
        gap:8px;
      }

      .crm-btn{
        min-height:30px;
        padding:0 10px;
        border-radius:10px;
        border:1px solid rgba(255,255,255,.08);
        background:rgba(255,255,255,.04);
        color:rgba(241,245,255,.94);
        font-size:11px;
        font-weight:700;
        cursor:pointer;
      }

      .crm-btn:hover{
        transform:translateY(-1px);
        background:rgba(255,255,255,.07);
        border-color:rgba(255,255,255,.14);
      }

      .crm-btn.followup{border-color:rgba(245,158,11,.18);background:rgba(245,158,11,.10);color:rgba(255,240,210,.96);}
      .crm-btn.reply{border-color:rgba(52,211,153,.18);background:rgba(52,211,153,.08);color:rgba(222,255,238,.96);}
      .crm-btn.close{border-color:rgba(248,113,113,.18);background:rgba(248,113,113,.08);color:rgba(255,228,228,.96);}
    `;
    document.head.appendChild(style);
  }

function setText(el, value) {
    if (el) el.textContent = String(value ?? "");
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function isAuthenticated() {
    return Boolean(state.token && state.username);
  }

  function getGuestUsage() {
    return Math.max(0, Number(localStorage.getItem(GUEST_USAGE_KEY) || 0) || 0);
  }

  function setGuestUsage(value) {
    const usage = Math.max(0, Number(value || 0) || 0);
    localStorage.setItem(GUEST_USAGE_KEY, String(usage));
    return usage;
  }

  function clearGuestUsage() {
    localStorage.removeItem(GUEST_USAGE_KEY);
    localStorage.removeItem(GUEST_USAGE_RESET_KEY);
    state.lastLimitNoticeKey = "";
  }

  function maybeResetGuestUsage(force = false) {
    if (isAuthenticated()) return false;

    const now = Date.now();
    const lastReset = Number(localStorage.getItem(GUEST_USAGE_RESET_KEY) || 0) || 0;
    const shouldReset = force || !lastReset || (now - lastReset) >= GUEST_USAGE_RESET_WINDOW_MS;

    if (!shouldReset) return false;

    localStorage.setItem(GUEST_USAGE_RESET_KEY, String(now));
    setGuestUsage(0);
    state.usage = 0;
    state.remaining = GUEST_USAGE_LIMIT;
    state.lastLimitNoticeKey = "";
    return true;
  }

  function getEffectiveLimit(tier = state.tier, providedLimit = state.limit) {
    const normalizedTier = String(tier || "free").toLowerCase();

    if (!isAuthenticated()) return GUEST_USAGE_LIMIT;
    if (normalizedTier === "free") return FREE_USAGE_LIMIT;

    const numericProvided = Number(providedLimit);
    if (Number.isFinite(numericProvided) && numericProvided > 0) return numericProvided;
    if (normalizedTier === "pro") return 500;
    if (normalizedTier === "elite") return 5000;
    return FREE_USAGE_LIMIT;
  }

  function getEffectiveUsage(candidateUsage = state.usage) {
    const numericUsage = Math.max(0, Number(candidateUsage || 0) || 0);
    if (!isAuthenticated()) return Math.max(numericUsage, getGuestUsage());
    return numericUsage;
  }

  function getLimitMessageConfig() {
    if (!isAuthenticated()) {
      return {
        key: `guest-${getEffectiveUsage(state.usage)}`,
        title: "You’ve hit the free preview limit",
        detail: `Create a free account to unlock ${FREE_USAGE_LIMIT} free runs and keep the operator workflow live.`,
        body: `You’ve used all ${GUEST_USAGE_LIMIT} guest runs.

You just felt the core workflow. Create a free account to unlock ${FREE_USAGE_LIMIT} free runs, keep your workspace state, and continue preparing support decisions with approval controls.`
      };
    }

    const vs = state.valueSignals;
    const d = state.dashboardStats || {};
    const money = Number(d.money_saved || 0);
    const prefix =
      vs && typeof vs.tickets_handled === "number"
        ? `You've handled ${vs.tickets_handled} tickets this month. ${formatMoney(money)} in actions surfaced. `
        : money > 0
          ? `${formatMoney(money)} already moved through billing actions. `
          : "";
    return {
      key: `free-${getEffectiveUsage(state.usage)}`,
      title: "You’ve hit the free plan limit",
      detail: `${prefix}Upgrade to Pro to keep approval-first automation running and unlock more capacity.`,
      body: `${prefix}You’ve used all ${FREE_USAGE_LIMIT} free runs.

You just saved real support effort. Upgrade to Pro to keep the approval-first operator live, unlock more capacity, and continue scanning tickets without interruption.`
    };
  }

  function pushLimitMessage(force = false) {
    const { key, title, detail, body } = getLimitMessageConfig();
    if (!force && state.lastLimitNoticeKey === key) return;
    state.lastLimitNoticeKey = key;

    setNotice("warning", title, detail);

    if (!els.messages) return;

    clearEmptyState();
    const row = addAssistantMessage(body);
    const footer = getAssistantFooterNode(row);
    if (footer) {
      footer.innerHTML = "";
      const meta = document.createElement("div");
      meta.className = "assistant-meta";
      meta.appendChild(
        createMetaChip({
          icon: ICONS.warn,
          text: isAuthenticated() ? "Upgrade required" : "Signup required",
          tone: "review"
        })
      );
      meta.appendChild(
        createMetaChip({
          icon: ICONS.ticket,
          text: `${getEffectiveUsage(state.usage)} / ${getEffectiveLimit(state.tier, state.limit)} used`
        })
      );
      footer.appendChild(meta);
    }

    scrollMessagesToBottom(true);
    refreshMessageShellGlow();
  }

  function enforceWorkspaceLimit() {
    const limit = getEffectiveLimit(state.tier, state.limit);
    const usage = getEffectiveUsage(state.usage);

    if (usage < limit) return true;

    updatePlanUI(state.tier, usage, limit, Math.max(0, limit - usage));
    pulseRail("usage");
    pushLimitMessage();

    if (!isAuthenticated()) {
      els.usernameInput?.focus();
      return false;
    }

    if (String(state.tier || "free").toLowerCase() === "free") {
      return false;
    }

    return true;
  }

  function consumeWorkspaceRun(serverUsage = null) {
    const currentLimit = getEffectiveLimit(state.tier, state.limit);
    let nextUsage = Number.isFinite(Number(serverUsage)) ? Number(serverUsage) : getEffectiveUsage(state.usage) + 1;
    nextUsage = Math.max(0, nextUsage);

    if (!isAuthenticated()) {
      setGuestUsage(nextUsage);
    }

    updatePlanUI(state.tier, nextUsage, currentLimit, Math.max(0, currentLimit - nextUsage));
  }

  function headers(withJson = true) {
    const out = {};
    if (withJson) out["Content-Type"] = "application/json";
    if (state.token) out.Authorization = `Bearer ${state.token}`;
    return out;
  }

  async function apiPost(path, body) {
    const res = await fetch(`${API}${path}`, {
      method: "POST",
      headers: headers(true),
      body: JSON.stringify(body || {})
    });

    const data = await res.json().catch(() => ({}));

    if (res.status === 401) {
      invalidateSessionFrom401();
      throw new Error(detailFromApiBody(data) || "Session expired.");
    }

    if (!res.ok) {
      throw new Error(detailFromApiBody(data) || "Request failed.");
    }

    return data;
  }
  async function apiGet(path) {
    const res = await fetch(`${API}${path}`, {
      headers: headers(false)
    });

    const data = await res.json().catch(() => ({}));

    if (res.status === 401) {
      invalidateSessionFrom401();
      throw new Error(detailFromApiBody(data) || "Session expired.");
    }

    if (!res.ok) {
      throw new Error(detailFromApiBody(data) || "Request failed.");
    }

    return data;
  }


  function persistAuth() {
    if (state.token) localStorage.setItem(TOKEN_KEY, state.token);
    else localStorage.removeItem(TOKEN_KEY);

    if (state.username) localStorage.setItem(USER_KEY, state.username);
    else localStorage.removeItem(USER_KEY);

    if (state.tier) localStorage.setItem(TIER_KEY, state.tier);
    else localStorage.removeItem(TIER_KEY);
  }

  function clearAuth() {
    state.token = "";
    state.username = "";
    state.tier = "free";
    state.usage = 0;
    state.limit = GUEST_USAGE_LIMIT;
    state.remaining = GUEST_USAGE_LIMIT;
    clearGuestUsage();
    persistAuth();
  }

  function invalidateSessionFrom401() {
    clearAuth();
    updatePlanUI("free", 0, 3, 3);
    updateAuthStatus();
    updateTopbarStatus();
    updateStripeUI();
    updateRefundUI();
    renderRefundHistory([]);
  }

  function detailFromApiBody(data) {
    const d = data && data.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d) && d.length) {
      const parts = d
        .map((item) => {
          if (!item || typeof item !== "object") return "";
          if (typeof item.msg === "string") return item.msg;
          return "";
        })
        .filter(Boolean);
      if (parts.length) return parts.join(" ");
    }
    return "";
  }

  async function parseApiResponse(res) {
    const text = await res.text();
    const trimmed = (text || "").trim();
    if (!trimmed) return {};
    try {
      return JSON.parse(trimmed);
    } catch {
      return { detail: trimmed.slice(0, 800) };
    }
  }

  function isStreamFailureResult(data) {
    if (!data || typeof data !== "object") return false;
    const mode = String(data.mode || "").toLowerCase();
    const reason = String(data.reason || "").toLowerCase();
    const tool = String(data.tool_status || (data.tool_result && data.tool_result.status) || "").toLowerCase();
    return (
      mode === "error"
      || mode === "timeout"
      || reason === "stream_error"
      || reason === "stream_timeout"
      || tool === "error"
      || tool === "timeout"
    );
  }

  function describeAuthRuleViolations(username, password) {
    const u = String(username || "");
    const p = String(password || "");
    const parts = [];
    if (u.length < 3 || u.length > 64) {
      parts.push("Username must be 3–64 characters.");
    }
    if (u && !/^[a-zA-Z0-9._-]+$/.test(u)) {
      parts.push("Username may only use letters, numbers, dot (.), underscore (_), and dash (-).");
    }
    if (p.length < 8) {
      parts.push("Password must be at least 8 characters.");
    }
    return parts;
  }

  function setAuthSubmitting(value) {
    state.authSubmitting = Boolean(value);
    if (els.signupBtn) els.signupBtn.disabled = state.authSubmitting;
    if (els.loginBtn) els.loginBtn.disabled = state.authSubmitting;
  }

  function loadDraft() {
    try {
      return localStorage.getItem(DRAFT_KEY) || "";
    } catch {
      return "";
    }
  }

  function saveDraft(value) {
    try {
      if (value) localStorage.setItem(DRAFT_KEY, value);
      else localStorage.removeItem(DRAFT_KEY);
    } catch {}
  }

  function formatTier(value) {
    const tier = String(value || "free").toLowerCase();
    return tier.charAt(0).toUpperCase() + tier.slice(1);
  }

  function formatMetric(value, digits = 0) {
    const num = Number(value || 0);
    return Number.isFinite(num) ? num.toFixed(digits) : digits ? (0).toFixed(digits) : "0";
  }

  function formatMoney(value) {
    const num = Number(value || 0);
    return `$${Number.isFinite(num) ? num.toFixed(0) : "0"}`;
  }

  function relativeTime(date = new Date()) {
    const d = date instanceof Date ? date : new Date(date);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  function planCopy(tier) {
    switch (String(tier || "free").toLowerCase()) {
      case "pro":
        return "Priority handling, larger usage limits, and a more serious operating surface for real support volume.";
      case "elite":
        return "Maximum capacity, premium control, and the strongest Xalvion operator environment.";
      default:
        return "Entry access with clear capacity limits and a visible upgrade path when usage pressure builds.";
    }
  }

  function canUseRefundCenter() {
    const tier = String(state.tier || "free").toLowerCase();
    return tier === "pro" || tier === "elite";
  }

  function refundStatusTone(status) {
    const value = String(status || "").toLowerCase();
    if (value.includes("refund") || value === "executed" || value === "succeeded" || value === "success") return "success";
    if (value.includes("fail") || value.includes("error") || value.includes("blocked")) return "error";
    return "pending";
  }

  function formatRefundTimestamp(value) {
    if (!value) return "Just now";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return String(value);
    return parsed.toLocaleString([], {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  }

  function renderRefundHistory(logs = []) {
    state.refundHistory = Array.isArray(logs) ? logs.slice() : [];

    if (els.refundHistoryCount) {
      setText(els.refundHistoryCount, String(state.refundHistory.length));
    }

    if (!els.refundHistoryList) return;

    if (!state.refundHistory.length) {
      els.refundHistoryList.innerHTML = '<div class="refund-empty">No refund activity yet. When a refund runs, it will appear here with status and timestamp.</div>';
      return;
    }

    els.refundHistoryList.innerHTML = state.refundHistory.map((log) => {
      const status = String(log.status || "pending");
      const tone = refundStatusTone(status);
      const amount = Number(log.amount || 0);
      const title = amount > 0 ? `Refunded ${formatMoney(amount)}` : "Refund activity";
      const reason = log.reason ? escapeHtml(log.reason) : "No reason provided";
      const timestamp = formatRefundTimestamp(log.timestamp);
      const username = log.username ? escapeHtml(log.username) : "workspace";
      return `
        <div class="refund-item">
          <div class="refund-item-head">
            <div class="refund-item-title">${escapeHtml(title)}</div>
            <div class="refund-pill ${tone}">${escapeHtml(status)}</div>
          </div>
          <div class="refund-item-meta">
            <span>${escapeHtml(timestamp)}</span>
            <span>·</span>
            <span>${username}</span>
          </div>
          <div class="refund-item-meta">
            <span>${reason}</span>
          </div>
        </div>
      `;
    }).join("");
  }

  function updateRefundUI() {
    const allowed = canUseRefundCenter();
    const accessLabel = allowed ? "Ready" : "Locked";

    if (els.refundTierAccess) {
      setText(els.refundTierAccess, accessLabel);
    }

    if (els.refundCenterCard) {
      els.refundCenterCard.classList.toggle("refund-disabled", !allowed);
    }

    if (els.openRefundModalBtn) {
      els.openRefundModalBtn.disabled = !allowed;
    }

    if (els.executeRefundBtn) {
      els.executeRefundBtn.disabled = !allowed;
    }

    if (els.refundModalNote) {
      els.refundModalNote.textContent = allowed
        ? "Live refund execution is available on this plan. Use a PaymentIntent or Charge ID from Stripe."
        : "Refund execution is locked until your plan allows live billing actions.";
    }

    if (els.refundCenterCopy) {
      els.refundCenterCopy.textContent = allowed
        ? "Open the refund UI, paste a PaymentIntent or Charge ID, and run a refund from the workspace."
        : "Upgrade to Pro or Elite to unlock live refund execution from the workspace.";
    }
  }

  function openRefundModal() {
    updateRefundUI();
    if (!canUseRefundCenter()) {
      setNotice("warning", "Refunds locked", "Upgrade to Pro or Elite to unlock live refund execution.");
      return;
    }
    if (els.refundModal) {
      els.refundModal.classList.add("open");
      els.refundModal.setAttribute("aria-hidden", "false");
    }
  }

  function closeRefundModal() {
    if (els.refundModal) {
      els.refundModal.classList.remove("open");
      els.refundModal.setAttribute("aria-hidden", "true");
    }
  }

  async function loadRefundHistory() {
    updateRefundUI();

    if (!state.token || !state.username) {
      renderRefundHistory([]);
      return;
    }

    try {
      const query = new URLSearchParams({
        action: "refund",
        username: state.username,
        limit: "8",
        offset: "0"
      });
      const res = await fetch(`${API}/admin/action-logs?${query.toString()}`, {
        headers: headers(false)
      });
      const data = await res.json().catch(() => ({}));

      if (res.status === 401) {
        invalidateSessionFrom401();
        renderRefundHistory([]);
        return;
      }

      if (res.status === 403) {
        renderRefundHistory([]);
        return;
      }

      if (!res.ok) {
        throw new Error(detailFromApiBody(data) || "Could not load refund history.");
      }

      renderRefundHistory(Array.isArray(data.logs) ? data.logs : []);
    } catch (error) {
      renderRefundHistory([]);
    }
  }

  async function executeRefundFromModal() {
    updateRefundUI();

    if (!state.token || !state.username) {
      setNotice("warning", "Authentication required", "Log in before running a live refund.");
      return;
    }

    if (!canUseRefundCenter()) {
      setNotice("warning", "Refunds locked", "Upgrade to Pro or Elite to unlock live refund execution.");
      return;
    }

    const paymentIntentId = String(els.refundPaymentIntentInput?.value || "").trim();
    const chargeId = String(els.refundChargeInput?.value || "").trim();
    const amountRaw = String(els.refundAmountInput?.value || "").trim();
    const refundReason = String(els.refundReasonSelect?.value || "requested_by_customer").trim();

    if (!paymentIntentId && !chargeId) {
      setNotice("warning", "Payment reference required", "Paste a PaymentIntent ID or Charge ID before running a refund.");
      return;
    }

    const amount = amountRaw ? Number(amountRaw) : null;
    if (amountRaw && (!Number.isFinite(amount) || amount <= 0)) {
      setNotice("warning", "Invalid amount", "Enter a valid refund amount or leave it blank for a full refund.");
      return;
    }

    if (els.executeRefundBtn) els.executeRefundBtn.disabled = true;

    try {
      const result = await executeStripeRefund({
        paymentIntentId,
        chargeId,
        amount,
        refundReason
      });

      const amountLabel = Number(result.amount || 0) > 0 ? ` ${formatMoney(result.amount)}` : "";

      setNotice(
        "success",
        "Refund processed",
        `Live refund${amountLabel} completed${result.refund_id ? ` · ${result.refund_id}` : ""}.`
      );

      if (els.refundPaymentIntentInput) els.refundPaymentIntentInput.value = "";
      if (els.refundChargeInput) els.refundChargeInput.value = "";
      if (els.refundAmountInput) els.refundAmountInput.value = "";

      closeRefundModal();
      await loadRefundHistory();
    } catch (error) {
      setNotice("error", "Refund failed", error.message || "Could not execute refund.");
    } finally {
      if (els.executeRefundBtn) els.executeRefundBtn.disabled = !canUseRefundCenter();
    }
  }

  function updateStripeUI() {
    const connected = Boolean(state.stripeConnected);

    if (els.stripeStatus) {
      els.stripeStatus.textContent = connected ? "Connected" : "Not connected";
      els.stripeStatus.classList.toggle("is-connected", connected);
    }

    if (els.stripeConnectBtn) {
      const label = els.stripeConnectBtn.querySelector(".stripe-connect-label");
      if (label) {
        label.textContent = connected ? "Reconnect Stripe" : "Connect Stripe";
      } else {
        els.stripeConnectBtn.textContent = connected ? "Reconnect Stripe" : "Connect Stripe";
      }
      els.stripeConnectBtn.disabled = false;
    }

    if (els.stripeDisconnectBtn) {
      els.stripeDisconnectBtn.hidden = !connected;
      els.stripeDisconnectBtn.disabled = !connected;
    }

    if (els.stripeAccountPill) {
      els.stripeAccountPill.textContent = connected && state.stripeAccountId ? state.stripeAccountId : "No account linked";
    }

    if (els.stripeModePill) {
      els.stripeModePill.textContent = connected ? state.stripeMode || "Connected" : "Awaiting connection";
    }

    if (els.stripeIntegrationCopy) {
      els.stripeIntegrationCopy.textContent = connected
        ? "Stripe is connected. Refund execution is now live for this workspace."
        : "Connect Stripe to execute refunds instead of only preparing them.";
    }
  }

  async function loadIntegrations() {
    if (!state.token) {
      state.stripeConnected = false;
      state.stripeAccountId = "";
      state.stripeMode = "";
      updateStripeUI();
      return;
    }

    try {
      const res = await fetch(`${API}/integrations/status`, { headers: headers(false) });
      const data = await res.json().catch(() => ({}));
      if (res.status === 401) {
        invalidateSessionFrom401();
        throw new Error(detailFromApiBody(data) || "Session expired.");
      }
      if (!res.ok) throw new Error(detailFromApiBody(data) || "Could not load integrations.");

      state.stripeConnected = Boolean(data.stripe_connected);
      state.stripeAccountId = String(data.stripe_account_id || "");

      const livemode =
        typeof data.stripe_livemode === "boolean"
          ? data.stripe_livemode
          : Boolean(data.stripe_livemode);

      const scope = String(data.stripe_scope || "").trim();

      state.stripeMode = String(
        data.mode ||
          data.stripe_mode ||
          (state.stripeConnected ? `${livemode ? "Live" : "Test"}${scope ? ` · ${scope}` : ""}` : "")
      );

      updateStripeUI();
    } catch (error) {
      state.stripeConnected = false;
      state.stripeAccountId = "";
      state.stripeMode = "";
      updateStripeUI();
    }
  }

  async function connectStripe() {
    if (!state.token || !state.username) {
      setNotice("warning", "Authentication required", "Log in before connecting Stripe.");
      return;
    }

    if (els.stripeConnectBtn) els.stripeConnectBtn.disabled = true;

    try {
      const res = await fetch(`${API}/integrations/stripe/connect`, { headers: headers(false) });
      const data = await res.json().catch(() => ({}));
      if (res.status === 401) {
        invalidateSessionFrom401();
        const msg =
          detailFromApiBody(data) ||
          "Sign in again. Your saved session does not match an account on this server.";
        throw new Error(msg);
      }
      if (!res.ok) throw new Error(detailFromApiBody(data) || "Could not start Stripe connection.");
      if (!data.url) throw new Error("Missing Stripe connection URL.");
      window.location.href = data.url;
    } catch (error) {
      if (els.stripeConnectBtn) els.stripeConnectBtn.disabled = false;
      setNotice("error", "Stripe connection failed", error.message || "Could not connect Stripe.");
    }
  }

  async function disconnectStripe() {
    if (!state.token || !state.username) {
      setNotice("warning", "Authentication required", "Log in before disconnecting Stripe.");
      return;
    }

    if (els.stripeDisconnectBtn) els.stripeDisconnectBtn.disabled = true;

    try {
      const res = await fetch(`${API}/integrations/stripe/disconnect`, {
        method: "POST",
        headers: headers()
      });
      const data = await res.json().catch(() => ({}));
      if (res.status === 401) {
        invalidateSessionFrom401();
        throw new Error(detailFromApiBody(data) || "Sign in again to disconnect Stripe.");
      }
      if (!res.ok) throw new Error(detailFromApiBody(data) || "Could not disconnect Stripe.");

      state.stripeConnected = false;
      state.stripeAccountId = "";
      state.stripeMode = "";
      updateStripeUI();
      setNotice("success", "Stripe disconnected", "Refund execution has been disabled until Stripe is connected again.");
    } catch (error) {
      setNotice("error", "Disconnect failed", error.message || "Could not disconnect Stripe.");
    } finally {
      if (els.stripeDisconnectBtn) els.stripeDisconnectBtn.disabled = false;
    }
  }

  async function executeStripeRefund({
    paymentIntentId = "",
    chargeId = "",
    amount = null,
    refundReason = "requested_by_customer"
  }) {
    const payload = {
      payment_intent_id: paymentIntentId || null,
      charge_id: chargeId || null,
      refund_reason: refundReason
    };

    if (typeof amount === "number" && Number.isFinite(amount) && amount > 0) {
      payload.amount = amount;
    }

    return apiPost("/actions/refund", payload);
  }

  async function executeStripeCharge({
    customerId,
    paymentMethodId,
    amount,
    currency = "usd",
    description = "Xalvion support charge"
  }) {
    return apiPost("/actions/charge", {
      customer_id: customerId,
      payment_method_id: paymentMethodId,
      amount,
      currency,
      description
    });
  }

  async function runWorkspaceRefundFromInput(amount = null) {
    const paymentIntentId = String(
      els.paymentIntentInput?.value || els.refundPaymentIntentInput?.value || ""
    ).trim();
    const chargeId = String(els.chargeIdInput?.value || els.refundChargeInput?.value || "").trim();

    if (!state.stripeConnected) {
      setNotice("warning", "Stripe required", "Connect Stripe before executing live refunds.");
      return;
    }

    if (!paymentIntentId && !chargeId) {
      setNotice(
        "warning",
        "Payment reference required",
        "Paste a payment intent ID (pi_…) or charge ID (ch_…) in the workspace fields or refund modal before running a live refund."
      );
      return;
    }

    try {
      const result = await executeStripeRefund({
        paymentIntentId,
        chargeId,
        amount,
        refundReason: "requested_by_customer"
      });

      setNotice(
        "success",
        "Refund executed",
        `Refund ${result.refund_id} completed in ${result.currency || "USD"}.`
      );
    } catch (error) {
      setNotice("error", "Refund failed", error.message || "Could not execute refund.");
    }
  }

  function hydrateStripeCallbackState() {
    try {
      const url = new URL(window.location.href);
      const stripe = url.searchParams.get("stripe");
      const detail = url.searchParams.get("detail");

      if (!stripe) return;

      if (stripe === "success" || stripe === "connected") {
        setNotice(
          "success",
          "Stripe connected",
          detail || "Refund execution is now live for this workspace."
        );
      } else if (stripe === "cancel") {
        setNotice("warning", "Stripe connection canceled", detail || "Stripe was not connected.");
      } else if (stripe === "error" || stripe === "connect_error") {
        setNotice("error", "Stripe connection failed", detail || "Could not complete Stripe connection.");
      } else if (stripe === "disconnected") {
        setNotice("success", "Stripe disconnected", detail || "Stripe has been disconnected from this workspace.");
      }

      url.searchParams.delete("stripe");
      url.searchParams.delete("detail");
      window.history.replaceState(
        {},
        document.title,
        url.pathname + (url.searchParams.toString() ? `?${url.searchParams.toString()}` : "") + url.hash
      );
    } catch {}
  }

  function refreshMessageShellGlow() {
    if (!els.messagesShell) return;
    els.messagesShell.classList.remove("shell-live");
    void els.messagesShell.offsetWidth;
    els.messagesShell.classList.add("shell-live");
    window.setTimeout(() => {
      els.messagesShell?.classList.remove("shell-live");
    }, 1700);
  }

  function setNotice(kind, title, detail) {
    if (!els.notice) return;
    els.notice.classList.remove("success", "warning", "error", "info");
    els.notice.classList.add(kind || "info");
    setText(els.noticeTitle, title);
    setText(els.noticeDetail, detail);
  }

  function updateBackendStatus(ok) {
    setText(els.backendStatus, ok ? "Service: online" : "Service: offline");
  }

  function updateAuthStatus() {
    if (state.username) setText(els.authStatus, `Session: ${state.username}`);
    else setText(els.authStatus, "Session: guest");
  }

  function updateStreamStatus(text = "Response: ready") {
    setText(els.streamStatus, text);
  }

  function updatePlanUI(tier = state.tier, usage = state.usage, limit = state.limit, remaining = state.remaining) {
    state.tier = String(tier || "free").toLowerCase();

    const resolvedUsage = getEffectiveUsage(usage);
    const resolvedLimit = getEffectiveLimit(state.tier, limit);
    const computedRemaining = Math.max(0, resolvedLimit - resolvedUsage);
    const resolvedRemaining = Number.isFinite(Number(remaining))
      ? Math.max(0, Math.min(Number(remaining), computedRemaining))
      : computedRemaining;

    state.usage = resolvedUsage;
    state.limit = resolvedLimit;
    state.remaining = resolvedRemaining;

    if (!isAuthenticated()) {
      setGuestUsage(state.usage);
    }

    setText(els.planTier, formatTier(state.tier));
    setText(els.planUsage, `${state.usage} / ${state.limit}`);
    setText(els.planUsed, `Used ${state.usage}`);
    setText(els.planRemaining, `Remaining ${state.remaining}`);

    if (els.planBar) {
      const width = Math.min(100, Math.max(0, (state.usage / Math.max(1, state.limit)) * 100));
      els.planBar.style.width = `${width}%`;
    }

    if (els.usagePanelCopy) els.usagePanelCopy.textContent = planCopy(state.tier);
    updateRefundUI();
    persistAuth();
    syncUsageApproachNotice();
  }

  function estimateAgentMinutesSavedFromDashboard(d = {}) {
    const actions = Number(d.actions || state.actionsCount || 0);
    const auto = Number(d.auto_resolved || 0);
    return Math.round(actions * 6 + auto * 2);
  }

  function refreshUpgradeValueSummary() {
    const el = els.upgradeValueSummary;
    if (!el) return;
    const d = state.dashboardStats || {};
    const tickets = Number(d.total_tickets ?? d.total_interactions ?? state.totalInteractions ?? 0);
    const money = Number(d.money_saved ?? 0);
    const mins = estimateAgentMinutesSavedFromDashboard(d);
    el.textContent = `${tickets} tickets handled · ${formatMoney(money)} in actions · ~${mins} min saved`;
    el.style.display = tickets > 0 || money > 0 || mins > 0 ? "block" : "none";
  }

  function ensureUsageApproachNoticeEl() {
    if (!els.usagePanelCopy || !els.usagePanelCopy.parentNode) return null;
    let el = document.getElementById("usageApproachNotice");
    if (el) return el;
    el = document.createElement("div");
    el.id = "usageApproachNotice";
    el.className = "muted-copy";
    el.style.marginTop = "8px";
    el.style.fontSize = "12px";
    el.style.lineHeight = "1.45";
    el.style.display = "none";
    els.usagePanelCopy.insertAdjacentElement("afterend", el);
    return el;
  }

  function renderUsageIntelligence(userData) {
    const el = ensureUsageApproachNoticeEl();
    if (!el) return;
    if (!userData || !userData.approaching_limit || userData.at_limit) {
      el.style.display = "none";
      el.innerHTML = "";
      return;
    }
    const tier = String(userData.tier || state.tier || "free").toLowerCase();
    if (tier === "elite") {
      el.style.display = "none";
      el.innerHTML = "";
      return;
    }
    const vs = userData.value_signals || state.valueSignals || {};
    const th = Number(vs.tickets_handled ?? userData.usage ?? state.usage ?? 0);
    const money = formatMoney(Number(vs.money_moved ?? 0));
    const tm = Number(vs.time_saved_minutes ?? 0);
    const unlock = String(vs.upgrade_unlocks || "").trim();
    el.style.display = "block";
    el.innerHTML = `<div>${th} tickets handled · ${money} in actions · ~${tm} min saved</div>
<div>${escapeHtml(unlock)}</div>
<button type="button" class="ghost-btn" style="margin-top:6px;padding:6px 10px;font-size:12px">Upgrade for continuous coverage →</button>`;
    const btn = el.querySelector("button");
    if (btn) {
      btn.onclick = () => upgradePlan("pro");
    }
  }

  function syncUsageApproachNotice() {
    if (!isAuthenticated()) {
      const el = ensureUsageApproachNoticeEl();
      if (el) {
        el.style.display = "none";
        el.innerHTML = "";
      }
      return;
    }
    renderUsageIntelligence({
      approaching_limit: state.approachingLimit,
      at_limit: state.atLimit,
      tier: state.tier,
      usage: state.usage,
      value_signals: state.valueSignals,
    });
  }

  function applyUsageWarningFromStream(payload) {
    if (!payload || typeof payload !== "object") return;
    if (payload.approaching_limit) state.approachingLimit = true;
    if (typeof payload.usage_pct === "number" && Number.isFinite(payload.usage_pct)) {
      state.usagePct = payload.usage_pct;
    }
    if (payload.remaining !== undefined && payload.remaining !== null) {
      const r = Number(payload.remaining);
      if (Number.isFinite(r)) state.remaining = Math.max(0, r);
    }
    const unlock = String(payload.upgrade_unlocks || "").trim();
    const thRaw = payload.tickets_handled;
    const ticketsHandled =
      thRaw !== undefined && thRaw !== null ? Number(thRaw) : state.usage;
    state.valueSignals = {
      ...(state.valueSignals && typeof state.valueSignals === "object" ? state.valueSignals : {}),
      tickets_handled: Number.isFinite(ticketsHandled) ? ticketsHandled : state.usage,
      upgrade_unlocks: unlock || (state.valueSignals && state.valueSignals.upgrade_unlocks) || "",
      capacity_message: (state.valueSignals && state.valueSignals.capacity_message) || "",
    };
    renderUsageIntelligence({
      approaching_limit: true,
      at_limit: state.atLimit,
      tier: state.tier,
      usage: state.usage,
      value_signals: state.valueSignals,
    });
  }

  function actionLabel(data) {
    const decision = data?.decision || {};
    const action = String(data?.action || decision.action || "none").toLowerCase();
    const amount = Number(data?.amount || decision.amount || 0);
    const requiresApproval = Boolean(data?.requires_approval || decision.requires_approval || data?.execution?.requires_approval);

    if (requiresApproval && action === "refund") return amount > 0 ? `Refund ${formatMoney(amount)} pending approval` : "Refund pending approval";
    if (requiresApproval && action === "charge") return amount > 0 ? `Charge ${formatMoney(amount)} pending approval` : "Charge pending approval";
    if (requiresApproval && action === "credit") return amount > 0 ? `Credit ${formatMoney(amount)} pending approval` : "Credit pending approval";
    const toolResult = data?.action_result || data?.tool_result || {};
    const toolType = String(toolResult.type || "").toLowerCase();
    const emailSent = Boolean(toolResult?.email?.ok);
    if (toolType === "tracking") return emailSent ? "Tracking emailed to customer" : "Tracking prepared";
    if (toolType === "escalation") return "Case escalated";
    if (action === "refund") return amount > 0 ? `Refunded ${formatMoney(amount)}` : "Refund processed";
    if (action === "credit") return amount > 0 ? `Credited ${formatMoney(amount)}` : "Credit applied";
    if (action === "review") return "Escalated to review";
    return "Response only";
  }

  function queueLabel(value) {
    const label = String(value || "new").replaceAll("_", " ");
    return label.charAt(0).toUpperCase() + label.slice(1);
  }

  function confidenceTone(confidence) {
    const value = Number(confidence || 0);
    if (value < 0.5) return "risky";
    if (value < 0.75) return "review";
    return "safe";
  }

  function riskLabel(data = {}) {
    const decision = data.decision || data.sovereign_decision || {};
    const triage = data.triage || data.triage_metadata || {};
    return String(decision.risk_level || triage.risk_level || "medium");
  }

  function displayActionLabel(data = {}) {
    const decision = data.decision || data.sovereign_decision || {};
    const rawIssueType = String(
      data.issue_type
      || data.meta?.issue_type
      || data.runtime_ticket?.issue_type
      || decision.issue_type
      || data.type
      || "general_support"
    ).toLowerCase();
    const rawAction = String(data.action || decision.action || "none").toLowerCase();
    const requiresApproval = Boolean(data.requires_approval || decision.requires_approval || data.execution?.requires_approval);
    if (requiresApproval && rawAction === "refund") return "Refund approval required";
    if (requiresApproval && rawAction === "charge") return "Charge approval required";
    if (requiresApproval && rawAction === "credit") return "Credit approval required";
    if (rawAction === "review") {
      if (rawIssueType === "shipping_issue") return "Shipping review started";
      if (rawIssueType === "damaged_order") return "Damage review started";
      if (
        rawIssueType.includes("billing")
        || rawIssueType === "refund_request"
        || rawIssueType === "billing_duplicate_charge"
      ) return "Billing review started";
      return "Review started";
    }
    return actionLabel(data);
  }

  function displayQueueLabel(data = {}) {
    const decision = data.decision || data.sovereign_decision || {};
    const rawQueue = String(decision.queue || "new").toLowerCase();
    if (rawQueue === "refund_risk") return "Billing check";
    if (rawQueue === "waiting") return "In progress";
    return queueLabel(rawQueue);
  }

  function displayRiskLabel(data = {}) {
    const rawRisk = String(riskLabel(data) || "medium").toLowerCase();
    const decision = data.decision || data.sovereign_decision || {};
    const rawAction = String(data.action || decision.action || "none").toLowerCase();
    if (rawRisk === "medium" && rawAction === "review") return "Needs review";
    return `${rawRisk} risk`;
  }

  function noticeTitleForResult(data = {}) {
    const decision = data.decision || data.sovereign_decision || {};
    const rawIssueType = String(
      data.issue_type
      || data.meta?.issue_type
      || data.runtime_ticket?.issue_type
      || decision.issue_type
      || data.type
      || "general_support"
    ).toLowerCase();
    const rawAction = String(data.action || decision.action || "none").toLowerCase();
    const toolResult = data?.action_result || data?.tool_result || {};
    const toolType = String(toolResult.type || "").toLowerCase();
    const emailSent = Boolean(toolResult?.email?.ok);
    if (toolType === "tracking") return emailSent ? "Tracking emailed" : "Tracking prepared";
    if (toolType === "escalation") return "Case escalated";
    if (toolType === "billing") return "Billing update prepared";
    if (rawAction === "review") {
      if (rawIssueType === "shipping_issue") return "Shipping review started";
      if (rawIssueType === "damaged_order") return "Damage review started";
      if (
        rawIssueType.includes("billing")
        || rawIssueType === "refund_request"
        || rawIssueType === "billing_duplicate_charge"
      ) return "Billing review started";
      return "Review started";
    }
    if (rawAction === "refund") return "Refund processed";
    if (rawAction === "credit") return "Credit applied";
    return "Case processed";
  }

  function updateTopbarStatus() {
    if (els.workspaceHeadline) {
      els.workspaceHeadline.textContent = state.username
        ? `Operator workspace · ${state.username}`
        : "Operator workspace · AI prepares, you approve";
    }

    if (els.workspaceSubcopy) {
      if (state.latestRun) {
        const decision = state.latestRun.decision || {};
        const posture = operatorPostureLabel(state.latestRun);
        els.workspaceSubcopy.textContent = `${formatTier(state.tier)} operator · ${displayActionLabel(state.latestRun)} · ${displayQueueLabel({ decision })} · ${posture} · ${formatMetric(state.latestRun.confidence || 0, 2)} conf.`;
      } else {
        els.workspaceSubcopy.textContent = state.username
          ? `${formatTier(state.tier)} plan · approval-first operator workspace · sovereign routing visible on every run.`
          : "Guest preview · run a case to see routing, posture, and the operator brief.";
      }
    }

    if (els.brandSubcopy) {
      els.brandSubcopy.textContent = state.username
        ? `Signed in as ${state.username}. Workspace state, plan data, and support activity stay persistent.`
        : "Premium AI support operations with visible action handling and a cleaner customer-ready surface.";
    }

    updateAuthStatus();
  }

  function updateSystemNarrative(data = null) {
    if (!els.systemPanelCopy) return;

    if (!data) {
      els.systemPanelCopy.textContent = "Use a common case type to prefill the composer and test response quality quickly.";
      return;
    }

    const decision = data.decision || {};
    const triage = data.triage || {};
    const approval = getApprovalContext(data);
    const parts = [
      `${displayActionLabel(data)}`,
      `${displayQueueLabel({ decision })}`,
      `${String(decision.risk_level || triage.risk_level || "medium")} risk`,
      `${approval.requiresApproval && !approval.approved ? "approval gate" : operatorPostureLabel(data)}`
    ];

    els.systemPanelCopy.textContent = `${parts.join(" · ")}. ${explainWhyAction(data)}`;
  }

  function updateStickiness() {
    if (!els.messages) return;
    const distanceFromBottom = els.messages.scrollHeight - els.messages.clientHeight - els.messages.scrollTop;
    state.stickToBottom = distanceFromBottom < 140;
  }

  function scrollMessagesToBottom(force = false) {
    if (!els.messages) return;
    if (force || state.stickToBottom) {
      els.messages.scrollTop = els.messages.scrollHeight;
    }
  }

  function createTypingMarkup() {
    return `
      <span class="typing" aria-hidden="true">
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
      </span>
    `;
  }

  function getUserBadge() {
    return `
      <span class="msg-badge">${ICONS.person}</span>
      <span>Customer</span>
    `;
  }

  function getAssistantBadge() {
    return `
      <span class="msg-badge">${ICONS.spark}</span>
      <span>Xalvion</span>
    `;
  }

  function createMessageGroup(role, bodyHtml, isPlaceholder = false) {
    const wrapper = document.createElement("div");
    wrapper.className = `msg-group ${role === "user" ? "user" : "assistant"}`;

    const card = document.createElement("div");
    card.className = `msg-card ${role === "user" ? "user" : "assistant"}`;

    const when = relativeTime(new Date());
    const headLabel = role === "user" ? getUserBadge() : getAssistantBadge();

    card.innerHTML = `
      <div class="msg-head">
        <div class="msg-who">${headLabel}</div>
        <div class="msg-time">${escapeHtml(when)}</div>
      </div>
      <div class="msg-body">
        <div class="reply-text js-reply-text">${bodyHtml}</div>
        ${role === "assistant" ? `<div class="assistant-footer js-assistant-footer"></div>` : ""}
      </div>
    `;

    if (isPlaceholder) card.dataset.placeholder = "true";
    wrapper.appendChild(card);
    return wrapper;
  }

  function addEmptyState() {
    if (!els.messages) return;
    if (els.messages.querySelector(".empty-state")) return;

    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = `
      <div class="empty-card">
        <div class="empty-eyebrow">
          <div class="empty-eyebrow-dot" aria-hidden="true"></div>
          Workspace
        </div>
        <h1>Workspace ready</h1>
        <p>Run a support case below and stream the response into this thread with readable action context and premium presentation.</p>
      </div>
    `;
    els.messages.appendChild(empty);
  }

  function clearEmptyState() {
    els.messages?.querySelector(".empty-state")?.remove();
  }

  function addUserMessage(text) {
    clearEmptyState();
    const row = createMessageGroup("user", escapeHtml(text).replace(/\n/g, "<br>"));
    els.messages?.appendChild(row);
    scrollMessagesToBottom(true);
    refreshMessageShellGlow();
    return row;
  }

  function addAssistantMessage(initialText = "") {
    clearEmptyState();
    const initial = initialText ? escapeHtml(initialText).replace(/\n/g, "<br>") : createTypingMarkup();
    const row = createMessageGroup("assistant", initial, true);
    els.messages?.appendChild(row);
    scrollMessagesToBottom(true);
    refreshMessageShellGlow();
    return row;
  }

  function getAssistantCopyNode(row) {
    return row?.querySelector(".js-reply-text") || null;
  }

  function getAssistantFooterNode(row) {
    return row?.querySelector(".js-assistant-footer") || null;
  }

  function setAssistantCopy(row, text) {
    const node = getAssistantCopyNode(row);
    if (!node) return;
    node.innerHTML = escapeHtml(text || "").replace(/\n/g, "<br>");
  }

  function appendAssistantChunk(row, chunk) {
    const node = getAssistantCopyNode(row);
    if (!node) return;

    if (node.querySelector(".typing")) node.innerHTML = "";

    const current = node.textContent || "";
    node.innerHTML = escapeHtml(current + chunk).replace(/\n/g, "<br>");
    scrollMessagesToBottom();
  }

  function createMetaChip({ icon, text, tone = "" }) {
    const chip = document.createElement("span");
    chip.className = `meta-chip ${tone}`.trim();
    chip.innerHTML = `${icon}<span>${escapeHtml(text)}</span>`;
    return chip;
  }

  function createMetaRow(data = {}) {
    const meta = document.createElement("div");
    meta.className = "assistant-meta";

    const confidence = Number(data.confidence || 0);

    meta.appendChild(
      createMetaChip({
        icon: ICONS.pulse,
        text: `${formatMetric(confidence, 2)} conf`,
        tone: confidenceTone(confidence)
      })
    );

    meta.appendChild(
      createMetaChip({
        icon: ICONS.spark,
        text: displayActionLabel(data)
      })
    );

    meta.appendChild(
      createMetaChip({
        icon: ICONS.ticket,
        text: displayQueueLabel(data)
      })
    );

    meta.appendChild(
      createMetaChip({
        icon: ICONS.shield,
        text: displayRiskLabel(data)
      })
    );

    return meta;
  }

  function getApprovalContext(data = {}) {
    const decision = data.decision || {};
    const ticket = data.ticket || {};
    const actionLog = data.action_log || ticket.action_log || {};

    const ticketId = Number(ticket.id || data.ticket_id || 0) || null;
    const action = String(decision.action || data.action || actionLog.action || "none").toLowerCase();
    const amount = Number(decision.amount || data.amount || actionLog.amount || 0) || 0;
    const requiresApproval = Boolean(data.requires_approval || decision.requires_approval || data.execution?.requires_approval || ticket.requires_approval || actionLog.requires_approval);
    const approved = Boolean(ticket.approved || actionLog.approved);
    const status = String(data.tool_status || actionLog.status || ticket.status || "").toLowerCase();

    return {
      ticketId,
      action,
      amount,
      requiresApproval,
      approved,
      status,
      canApprove: requiresApproval && !approved && !!ticketId && isAuthenticated(),
      paymentIntentId: normalizeReference("pi_"),
      chargeId: normalizeReference("ch_"),
    };
  }

  function operatorPostureLabel(data = {}) {
    const approval = getApprovalContext(data);
    if (approval.requiresApproval && !approval.approved) return "Approval gate";
    const action = String(data.action || data.decision?.action || "none").toLowerCase();
    if (action === "review") return "Human review";
    if (Number(data.confidence || 0) > 0 && Number(data.confidence || 0) < 0.62) return "Verify signals";
    return "Clear to send";
  }

  function normalizeWorkspaceResult(data) {
    if (!data || typeof data !== "object") return data;
    const out = { ...data };
    const sov = out.sovereign_decision;
    if (sov && typeof sov === "object") {
      out.decision = { ...(out.decision || {}), ...sov };
    }
    const imp = out.impact_projections;
    if (imp && typeof imp === "object") {
      out.impact = { ...(out.impact || {}), ...imp };
    }
    const tri = out.triage_metadata;
    if (tri && typeof tri === "object") {
      out.triage = { ...(out.triage || {}), ...tri };
    }
    return out;
  }

  function explainWhyAction(data = {}) {
    const d = data.decision || data.sovereign_decision || {};
    const reason = String(data.reason || d.reason || "").trim();
    if (reason) return reason;
    const action = String(data.action || d.action || "none").toLowerCase();
    if (action === "none") return "Response-only path: no billing motion selected.";
    return `Prepared motion: ${action} · routed to ${displayQueueLabel({ decision: d })}.`;
  }

  function signalsSummaryLine(data = {}) {
    const t = data.triage || data.triage_metadata || {};
    const parts = [];
    const u = Number(t.urgency);
    const c = Number(t.churn_risk);
    const rf = Number(t.refund_likelihood);
    const ab = Number(t.abuse_likelihood);
    if (u > 0) parts.push(`urgency ${u}`);
    if (c > 0) parts.push(`churn ${c}`);
    if (rf > 0) parts.push(`refund exposure ${rf}`);
    if (ab > 0) parts.push(`abuse signal ${ab}`);
    return parts.length ? parts.join(" · ") : "Triage signals within a normal band for this lane.";
  }

  function queueMeansLine(data = {}) {
    const decision = data.decision || {};
    const q = String(decision.queue || "new").toLowerCase();
    const map = {
      new: "Intake lane — case is staged; no execution commitment yet.",
      waiting: "Active lane — work in progress before closure.",
      escalated: "Human lane — judgment or policy check expected.",
      refund_risk: "Billing-risk lane — verify ledger detail before money movement.",
      vip: "Priority lane — higher visibility handling.",
      resolved: "Closed lane — outcome recorded."
    };
    return map[q] || `${queueLabel(q)} — routed per policy.`;
  }

  function safetyVerdictLine(data = {}) {
    const approval = getApprovalContext(data);
    const c = Number(data.confidence || 0);
    const tone = confidenceTone(c);
    if (approval.requiresApproval && !approval.approved) {
      return "Financial or policy gate active — explicit approval before execution.";
    }
    if (tone === "risky") return "Confidence is low — read signals before customer send.";
    if (tone === "review") return "Borderline confidence — quick scan recommended.";
    return "Posture is safe to continue with standard operator review.";
  }

  function nextOperatorStepLine(data = {}) {
    const approval = getApprovalContext(data);
    if (approval.requiresApproval && !approval.approved && approval.canApprove) {
      return "Refine the reply if needed, then approve or reject the prepared action.";
    }
    if (approval.requiresApproval && !approval.approved && !approval.canApprove) {
      return "Sign in with the ticket owner account to release the approval gate.";
    }
    const action = String(data.action || data.decision?.action || "none").toLowerCase();
    if (action === "review") return "Copy the reply into your helpdesk thread and own the follow-up.";
    return "Copy the customer-ready reply, confirm notes, and mark the loop closed.";
  }

  function thinkingTraceSnippet(data = {}, maxSteps = 4) {
    const tr = data.thinking_trace;
    if (!Array.isArray(tr) || !tr.length) return "";
    return tr
      .slice(0, maxSteps)
      .map((step) => {
        const s = step && typeof step === "object" ? step : {};
        const name = String(s.step || s.name || "step");
        const st = String(s.status || "");
        const det = String(s.detail || "").trim();
        return det ? `${name}: ${st} (${det})` : `${name}: ${st}`;
      })
      .join("\n");
  }

  function createApprovalBanner(data = {}) {
    const approval = getApprovalContext(data);
    if (!approval.requiresApproval || approval.approved) return null;

    const banner = document.createElement("div");
    banner.className = "approval-banner";
    const amountText = approval.amount > 0 ? ` ${formatMoney(approval.amount)}` : "";
    const actionText = approval.action && approval.action !== "none" ? `${approval.action}${amountText}` : "prepared action";
    const gateHint =
      !approval.canApprove && approval.ticketId
        ? `<div class="approval-hint">Sign in as the ticket owner to enable Approve / Reject from this workspace.</div>`
        : "";
    banner.innerHTML = `${ICONS.warn}<div><strong>Approval gate</strong><br>${escapeHtml(`Prepared ${actionText} — execution is held until an operator approves.`)}${gateHint}</div>`;
    return banner;
  }

  async function resolveApproval(ticketId, action, body = {}) {
    const res = await fetch(`${API}/tickets/${ticketId}/${action}`, {
      method: "POST",
      headers: headers(true),
      body: JSON.stringify(body || {})
    });

    const data = await res.json().catch(() => ({}));
    if (res.status === 401) {
      invalidateSessionFrom401();
      throw new Error(detailFromApiBody(data) || "Session expired.");
    }
    if (!res.ok) {
      throw new Error(detailFromApiBody(data) || `Could not ${action} this action.`);
    }
    return data;
  }

  function normalizeApprovalResponse(data = {}, previous = {}) {
    const ticket = data.ticket || {};
    const actionLog = ticket.action_log || previous.action_log || {};
    return {
      ...previous,
      ...data,
      ticket,
      action_log: actionLog,
      reply: data.reply || data.response || data.final || ticket.final_reply || previous.reply || "",
      response: data.response || data.reply || data.final || ticket.final_reply || previous.response || "",
      final: data.final || data.reply || data.response || ticket.final_reply || previous.final || "",
      action: data.action || ticket.action || previous.action || "none",
      amount: Number.isFinite(Number(data.amount)) ? Number(data.amount) : (Number(ticket.amount || previous.amount || 0) || 0),
      reason: data.reason || actionLog.reason || ticket.internal_note || previous.reason || "",
      tool_status: data.tool_status || actionLog.status || ticket.status || previous.tool_status || "unknown",
      decision: {
        ...(previous.decision || {}),
        ...(data.decision || {}),
        action: (data.decision || {}).action || data.action || ticket.action || previous.action || "none",
        amount: Number((data.decision || {}).amount || data.amount || ticket.amount || previous.amount || 0) || 0,
        queue: (data.decision || {}).queue || ticket.queue || (previous.decision || {}).queue || "new",
        priority: (data.decision || {}).priority || ticket.priority || (previous.decision || {}).priority || "medium",
        risk_level: (data.decision || {}).risk_level || ticket.risk_level || (previous.decision || {}).risk_level || "medium",
        requires_approval: Boolean((data.decision || {}).requires_approval || ticket.requires_approval || false)
      },
      impact: {
        ...(previous.impact || {}),
        ...(data.impact || {}),
        amount: Number((data.impact || {}).amount || data.amount || ticket.amount || previous.amount || 0) || 0,
        auto_resolved: Boolean((data.impact || {}).auto_resolved || (!ticket.requires_approval && String(ticket.status || "").toLowerCase() === "resolved"))
      },
      output: {
        ...(previous.output || {}),
        ...(data.output || {}),
        internal_note: ((data.output || {}).internal_note || ticket.internal_note || (previous.output || {}).internal_note || "")
      },
      confidence: Number(data.confidence || ticket.confidence || previous.confidence || 0) || 0,
      quality: Number(data.quality || ticket.quality || previous.quality || 0) || 0,
      requires_approval: Boolean((data.decision || {}).requires_approval || ticket.requires_approval || false),
    };
  }

  function getCopyTextFromRow(row, fallback = "") {
    const ta = row?.querySelector(".decision-edit-textarea");
    if (ta && String(ta.value || "").trim()) return String(ta.value).trim();
    const fromDom = (getAssistantCopyNode(row)?.innerText || "").trim();
    if (fromDom) return fromDom;
    return String(fallback || "").trim();
  }

  function deriveConsequenceSignal(data = {}) {
    const dec = data.decision || data.sovereign_decision || {};
    const tier = String(data.execution_tier || "").toLowerCase();
    if (tier === "safe_autopilot_ready") {
      return {
        cls: "signal-safe",
        text: "✓ Safe to automate",
        title: "Meets all automation safety criteria"
      };
    }
    if (tier === "assist_only") {
      return {
        cls: "signal-review",
        text: "○ Manual review",
        title: "Risk signals require human decision"
      };
    }
    if (tier === "approval_required") {
      return {
        cls: "signal-approval",
        text: "⚡ Approval required",
        title: "Awaiting operator approval"
      };
    }

    const action = String(data.action || dec.action || "none").toLowerCase();
    const risk = String(dec.risk_level || data.triage?.risk_level || "medium").toLowerCase();
    const req = Boolean(
      data.requires_approval || dec.requires_approval || data.decision_state === "pending_decision"
    );
    const money = action === "refund" || action === "charge" || action === "credit";
    if (req && money) return { cls: "signal-approval", text: "⚡ Approval required", title: "" };
    if (action === "review" || risk === "high" || risk === "medium") {
      return { cls: "signal-review", text: "⚠ Review recommended", title: "" };
    }
    return { cls: "signal-safe", text: "✓ Safe to send", title: "" };
  }

  function mountOperatorDecisionPanel(row, data, initialReply) {
    row.querySelector(".decision-panel")?.remove();
    const msgBody = row.querySelector(".msg-body");
    if (!msgBody || !data) return;

    const ticket = data.ticket || {};
    const ticketId = Number(ticket.id || 0) || null;
    const approval = getApprovalContext(data);
    const pendingGate = Boolean(approval.requiresApproval && !approval.approved);
    const sig = deriveConsequenceSignal(data);
    const originalAi = String(initialReply || getAssistantCopyNode(row)?.innerText || "").trim();

    const panel = document.createElement("div");
    panel.className = "decision-panel";
    panel.innerHTML = `
      <div class="decision-panel-top">
        <span class="consequence-signal ${sig.cls}" data-role="consequence">${escapeHtml(sig.text)}</span>
        <div class="decision-controls" data-role="controls"></div>
      </div>
      <div class="decision-panel-note" data-role="note" style="display:none"></div>
      <div class="decision-panel-error" data-role="err" style="display:none"></div>
      <div class="edit-mode-container" data-role="edit" style="display:none"></div>
    `;
    msgBody.appendChild(panel);

    const cons = panel.querySelector("[data-role='consequence']");
    if (cons && sig.title) cons.setAttribute("title", sig.title);

    const controls = panel.querySelector("[data-role='controls']");
    const noteEl = panel.querySelector("[data-role='note']");
    const errEl = panel.querySelector("[data-role='err']");
    const editWrap = panel.querySelector("[data-role='edit']");

    const showErr = (t) => {
      errEl.textContent = t || "";
      errEl.style.display = t ? "block" : "none";
    };

    const setTerminal = (pill, note) => {
      controls.innerHTML = `<span class="decision-state-pill">${escapeHtml(pill)}</span>`;
      if (note) {
        noteEl.textContent = note;
        noteEl.style.display = "block";
      }
    };

    const postPill = row.dataset.opPostPill;
    if (postPill) {
      delete row.dataset.opPostPill;
      setTerminal(postPill, "Sent to customer.");
      return;
    }
    const tst = String(data.tool_status || "").toLowerCase();
    const st = String(data.status || ticket.status || "").toLowerCase();
    if (tst === "rejected" || st === "escalated") {
      setTerminal("Rejected", "Response held. Ticket escalated.");
      return;
    }
    if (approval.approved) {
      setTerminal("Approved", "Sent to customer.");
      return;
    }

    const wireActions = () => {
      controls.innerHTML = "";
      const rej = document.createElement("button");
      rej.type = "button";
      rej.className = "btn-reject";
      rej.textContent = "Reject";
      const ed = document.createElement("button");
      ed.type = "button";
      ed.className = "btn-edit";
      ed.textContent = "Edit";
      const ap = document.createElement("button");
      ap.type = "button";
      ap.className = "btn-approve";
      ap.textContent = "Approve";
      controls.append(rej, ed, ap);

      ed.addEventListener("click", () => {
        showErr("");
        editWrap.style.display = "grid";
        editWrap.innerHTML = `
          <div>
            <div class="original-response-label">Original AI response</div>
            <div class="original-response">${escapeHtml(originalAi)}</div>
          </div>
          <textarea class="decision-edit-textarea" aria-label="Edited reply">${escapeHtml(getCopyTextFromRow(row, initialReply))}</textarea>
          <div class="edit-actions">
            <button type="button" class="btn-cancel-edit" data-act="cancel">Cancel</button>
            <button type="button" class="btn-send-edited" data-act="send">Send Edited</button>
          </div>
        `;
        const ta = editWrap.querySelector(".decision-edit-textarea");
        ta?.focus();
        editWrap.querySelector("[data-act='cancel']")?.addEventListener("click", () => {
          editWrap.style.display = "none";
          editWrap.innerHTML = "";
        });
        editWrap.querySelector("[data-act='send']")?.addEventListener("click", async () => {
          const next = String(ta?.value || "").trim();
          if (!next) {
            showErr("Edited reply cannot be empty.");
            return;
          }
          if (pendingGate && ticketId && approval.canApprove) {
            [rej, ed, ap].forEach((b) => {
              b.disabled = true;
            });
            ap.textContent = "…";
            try {
              const response = await resolveApproval(ticketId, "approve", {
                payment_intent_id: approval.paymentIntentId,
                charge_id: approval.chargeId,
                refund_reason: "requested_by_customer",
                final_reply: next
              });
              const normalized = normalizeWorkspaceResult(normalizeApprovalResponse(response, data));
              state.latestRun = normalized;
              row.dataset.opPostPill = "Sent as edited";
              setAssistantCopy(row, normalized.reply || next);
              editWrap.style.display = "none";
              editWrap.innerHTML = "";
              rebindResultFooter(row, normalized);
              updateStatsFromResult(normalized);
              updateRevenueCard(normalized);
              updateLatestRunCard(normalized);
              updateSystemNarrative(normalized);
              updateTopbarStatus();
              setNotice("success", "Approved", response.message || "Edited reply saved.");
            } catch (error) {
              showErr(error.message || "Approve failed.");
              [rej, ed, ap].forEach((b) => {
                b.disabled = false;
              });
              ap.textContent = "Approve";
            }
          } else {
            setAssistantCopy(row, next);
            editWrap.style.display = "none";
            editWrap.innerHTML = "";
            setTerminal("Edited", "Copy the card text when you send to the customer.");
            setNotice("info", "Reply updated", "No server gate on this run — text updated on the card.");
          }
        });
      });

      rej.addEventListener("click", async () => {
        showErr("");
        if (!ticketId) {
          showErr("No ticket id — cannot reject.");
          return;
        }
        if (!pendingGate) {
          setTerminal("Rejected", "Response held for manual review.");
          setNotice("warning", "Marked for review", "Log this case in your helpdesk — no server rejection for this run.");
          return;
        }
        if (!approval.canApprove) {
          showErr("Sign in as the ticket owner to reject.");
          return;
        }
        rej.disabled = true;
        ed.disabled = true;
        ap.disabled = true;
        try {
          const response = await resolveApproval(ticketId, "reject", {
            internal_note: "Rejected by operator"
          });
            const normalized = normalizeWorkspaceResult(normalizeApprovalResponse(response, data));
            state.latestRun = normalized;
            rebindResultFooter(row, normalized);
          updateStatsFromResult(normalized);
          updateRevenueCard(normalized);
          updateLatestRunCard(normalized);
          updateSystemNarrative(normalized);
          updateTopbarStatus();
          setNotice("warning", "Rejected", response.message || "Ticket escalated.");
        } catch (error) {
          showErr(error.message || "Reject failed.");
          rej.disabled = false;
          ed.disabled = false;
          ap.disabled = false;
        }
      });

      ap.addEventListener("click", async () => {
        showErr("");
        if (!ticketId && pendingGate) {
          showErr("No ticket id.");
          return;
        }
        if (pendingGate && !approval.canApprove) {
          showErr("Sign in as the ticket owner to approve.");
          return;
        }
        if (pendingGate && approval.canApprove) {
          [rej, ed, ap].forEach((b) => {
            b.disabled = true;
          });
          ap.textContent = "…";
          try {
            const response = await resolveApproval(ticketId, "approve", {
              payment_intent_id: approval.paymentIntentId,
              charge_id: approval.chargeId,
              refund_reason: "requested_by_customer"
            });
            const normalized = normalizeWorkspaceResult(normalizeApprovalResponse(response, data));
            state.latestRun = normalized;
            rebindResultFooter(row, normalized);
            updateStatsFromResult(normalized);
            updateRevenueCard(normalized);
            updateLatestRunCard(normalized);
            updateSystemNarrative(normalized);
            updateTopbarStatus();
            setNotice("success", "Approved", response.message || "Operator approved.");
          } catch (error) {
            showErr(error.message || "Approve failed.");
            [rej, ed, ap].forEach((b) => {
              b.disabled = false;
            });
            ap.textContent = "Approve";
          }
          return;
        }
        setTerminal("Approved", "Sent to customer.");
        setNotice("success", "Cleared", "Operator cleared this response — copy when ready.");
      });
    };

    wireActions();
  }

  function rebindResultFooter(row, normalized) {
    row.querySelector(".decision-panel")?.remove();
    const replyText = normalized.reply || normalized.response || normalized.final || "";
    setAssistantCopy(row, replyText);
    const footer = getAssistantFooterNode(row);
    if (footer) {
      footer.innerHTML = "";
      footer.appendChild(createMetaRow(normalized));
      const toolsWrap = document.createElement("div");
      addCopyControl(toolsWrap, replyText, row);
      footer.appendChild(toolsWrap);
    }
    const details = row.querySelector(".details-wrap");
    if (details) details.replaceWith(createDetailsPanel(normalized));
    mountOperatorDecisionPanel(row, normalized, replyText);
  }

  function addCopyControl(container, replyText, row = null) {
    const tools = document.createElement("div");
    tools.className = "assistant-tools";

    const copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.className = "mini-btn copy-btn";
    copyBtn.innerHTML = ICONS.copy;
    copyBtn.setAttribute("aria-label", "Copy response");

    copyBtn.addEventListener("click", async () => {
      try {
        const text = row ? getCopyTextFromRow(row, replyText) : String(replyText || "");
        await navigator.clipboard.writeText(text);
        copyBtn.innerHTML = ICONS.check;
        window.setTimeout(() => {
          copyBtn.innerHTML = ICONS.copy;
        }, 1200);
      } catch {}
    });

    tools.appendChild(copyBtn);
    container.appendChild(tools);
  }

  function createDetailBox(label, value) {
    const safeValue = value === null || typeof value === "undefined" || value === "" ? "—" : String(value);
    return `
      <div class="details-box">
        <div class="details-label">${escapeHtml(label)}</div>
        <div class="details-value">${escapeHtml(safeValue)}</div>
      </div>
    `;
  }

  function buildExplainabilityBriefHtml(ex) {
    if (!ex || typeof ex !== "object") return "";
    const sum = ex.summary ? `<p class="details-note" style="margin-bottom:10px">${escapeHtml(String(ex.summary))}</p>` : "";
    const rr = ex.risk_reasoning || {};
    const pt = ex.policy_trigger || {};
    const mi = ex.memory_influence || {};
    const memFull = mi.signal ? String(mi.signal) : "—";
    const memTrunc = memFull.length > 40 ? `${memFull.slice(0, 40)}…` : memFull;
    const stats = `<div class="details-grid" style="grid-template-columns:repeat(3,minmax(0,1fr));margin-bottom:10px;gap:8px">
      ${createDetailBox("Risk", String(rr.level || "—"))}
      ${createDetailBox("Policy", pt.triggered ? "Applied" : "None")}
      ${createDetailBox("Memory", memTrunc)}
    </div>`;
    const oe = ex.outcome_expectation;
    const oeBlock =
      oe && oe.signal
        ? `<div class="details-insight"><div class="details-insight-k">Pattern expectation</div><div class="details-insight-v">${escapeHtml(String(oe.signal))}</div></div>`
        : "";
    const why = ex.why_not_other_actions
      ? `<div class="muted-copy" style="font-size:12px;margin-top:8px;line-height:1.45">${escapeHtml(String(ex.why_not_other_actions))}</div>`
      : "";
    return sum + stats + oeBlock + why;
  }

  function buildDecisionExplanationInsightsHtml(ex) {
    if (!ex || typeof ex !== "object") return "";
    const rows = [];
    const ra = ex.risk_assessment;
    if (ra && typeof ra === "object" && ra.signal) {
      rows.push({ k: "Risk assessment", v: String(ra.signal) });
    }
    const pi = ex.policy_influence;
    if (pi && typeof pi === "object" && pi.signal) {
      rows.push({ k: "Policy influence", v: String(pi.signal) });
    }
    const mi = ex.memory_influence;
    if (mi && typeof mi === "object" && mi.signal) {
      rows.push({ k: "Memory influence", v: String(mi.signal) });
    }
    const ar = ex.approval_rationale;
    if (ar && typeof ar === "object" && ar.reason) {
      rows.push({ k: "Approval rationale", v: String(ar.reason) });
    }
    if (ex.summary) {
      rows.push({ k: "Decision narrative", v: String(ex.summary) });
    }
    if (!rows.length) return "";
    return rows
      .map(
        (r) => `<div class="details-insight">
          <div class="details-insight-k">${escapeHtml(r.k)}</div>
          <div class="details-insight-v">${escapeHtml(r.v)}</div>
        </div>`
      )
      .join("");
  }

  function createDetailsPanel(data = {}) {
    const details = document.createElement("details");
    details.className = "details-wrap";

    const decision = data.decision || {};
    const output = data.output || {};
    const impact = data.impact || {};
    const toolStatus = String(data.tool_status || data.execution?.status || "resolved");
    const internalNote = String(output.internal_note || "").trim();
    const policyNote = String(data.reason || decision.reason || "").trim();
    const trace = thinkingTraceSnippet(data, 5);
    const execDetail = String(data.execution?.detail || data.tool_result?.message || "").trim();

    const approvalBanner = createApprovalBanner(data);
    const explainabilityBrief = buildExplainabilityBriefHtml(data.decision_explainability);
    const explanationInsightsHtml = explainabilityBrief
      ? ""
      : buildDecisionExplanationInsightsHtml(data.decision_explanation);

    const insightBlock = `
      <div class="details-insight-stack">
        ${explainabilityBrief}
        ${explanationInsightsHtml}
        <div class="details-insight">
          <div class="details-insight-k">Why this path</div>
          <div class="details-insight-v">${escapeHtml(explainWhyAction(data))}</div>
        </div>
        <div class="details-insight">
          <div class="details-insight-k">Signals</div>
          <div class="details-insight-v">${escapeHtml(signalsSummaryLine(data))}</div>
        </div>
        <div class="details-insight">
          <div class="details-insight-k">Queue meaning</div>
          <div class="details-insight-v">${escapeHtml(queueMeansLine(data))}</div>
        </div>
        <div class="details-insight">
          <div class="details-insight-k">Safety</div>
          <div class="details-insight-v">${escapeHtml(safetyVerdictLine(data))}</div>
        </div>
        <div class="details-insight">
          <div class="details-insight-k">Next operator step</div>
          <div class="details-insight-v">${escapeHtml(nextOperatorStepLine(data))}</div>
        </div>
        ${
          execDetail
            ? `<div class="details-insight">
          <div class="details-insight-k">Execution</div>
          <div class="details-insight-v">${escapeHtml(execDetail)}</div>
        </div>`
            : ""
        }
        ${
          trace
            ? `<div class="details-insight">
          <div class="details-insight-k">Decision trace</div>
          <div class="details-trace">${escapeHtml(trace)}</div>
        </div>`
            : ""
        }
      </div>
    `;

    details.innerHTML = `
      <summary class="details-toggle">
        <span>Operator brief</span>
        <span class="chev">${ICONS.chevron}</span>
      </summary>
      <div class="details-panel">
        ${approvalBanner ? approvalBanner.outerHTML : ""}
        ${insightBlock}
        <div class="details-grid">
          ${createDetailBox("Surface action", displayActionLabel(data))}
          ${createDetailBox("Queue", queueLabel(decision.queue || "new"))}
          ${createDetailBox("Risk", riskLabel(data))}
          ${createDetailBox("Priority", String(decision.priority || "medium"))}
          ${createDetailBox("Tool status", toolStatus)}
          ${createDetailBox("Value surfaced", formatMoney(impact.money_saved || impact.amount || data.amount || 0))}
        </div>
        ${policyNote && policyNote !== internalNote ? `<div class="details-note">${escapeHtml(policyNote)}</div>` : ""}
        ${internalNote ? `<div class="details-note">${escapeHtml(internalNote)}</div>` : ""}
      </div>
    `;

    return details;
  }

  function createStreamSteps() {
    const wrap = document.createElement("div");
    wrap.className = "stream-steps";
    wrap.innerHTML = `
      <div class="stream-step active"><div class="stream-step-dot"></div><span>Reviewing</span></div>
      <div class="stream-step"><div class="stream-step-dot"></div><span>Routing</span></div>
      <div class="stream-step"><div class="stream-step-dot"></div><span>Responding</span></div>
      <div class="stream-step"><div class="stream-step-dot"></div><span>Finalizing</span></div>
    `;
    return wrap;
  }

  function advanceStreamStep(el, stepIndex) {
    if (!el) return;
    const steps = el.querySelectorAll(".stream-step");
    steps.forEach((step, i) => {
      step.classList.remove("active", "done");
      if (i < stepIndex) step.classList.add("done");
      if (i === stepIndex) step.classList.add("active");
    });
  }

  function removeStreamSteps(el) {
    if (el) el.remove();
  }

  function hardBindCoreButtons() {
    const send = els.sendBtn;
    const input = els.messageInput;

    if (send && !send.dataset.xalvionBound) {
      send.dataset.xalvionBound = "true";
      send.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        void sendMessage();
      });
    }

    if (input && !input.dataset.xalvionEnterBound) {
      input.dataset.xalvionEnterBound = "true";
      input.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey && !event.metaKey && !event.ctrlKey) {
          event.preventDefault();
          void sendMessage();
        }
      });
    }
  }

  function buildSupportPayload() {
    return {
      message: (els.messageInput?.value || "").trim(),
      payment_intent_id: normalizeReference("pi_"),
      charge_id: normalizeReference("ch_")
    };
  }

  function normalizeReference(prefix) {
    const el = prefix === "pi_" ? els.paymentIntentInput : els.chargeIdInput;
    const value = String(el?.value || "").trim();
    return value.startsWith(prefix) ? value : null;
  }

  function autoResizeTextarea() {
    if (!els.messageInput) return;
    els.messageInput.style.height = "auto";
    els.messageInput.style.height = `${Math.min(240, Math.max(50, els.messageInput.scrollHeight))}px`;
  }

  function setSending(value) {
    state.sending = Boolean(value);

    if (els.sendBtn) {
      els.sendBtn.disabled = state.sending;
      els.sendBtn.innerHTML = state.sending ? ICONS.status : ICONS.send;
      els.sendBtn.setAttribute("aria-label", state.sending ? "Sending" : "Send message");
    }

    if (els.messageInput) {
      els.messageInput.disabled = state.sending;
      const wrap = els.messageInput.closest(".composer-input-wrap") || els.messageInput.closest(".composer");
      wrap?.classList.toggle("composer-live", state.sending);
    }

    updateStreamStatus(state.sending ? "Response: streaming" : "Response: ready");
  }

  function parseSseEvents(text) {
    const events = [];
    const parts = text.split("\n\n");

    for (const part of parts) {
      if (!part.trim()) continue;

      let eventName = "message";
      let dataValue = "";

      for (const line of part.split("\n")) {
        if (line.startsWith("event:")) eventName = line.slice(6).trim();
        if (line.startsWith("data:")) dataValue += line.slice(5).trim();
      }

      if (!dataValue) continue;

      try {
        events.push({ event: eventName, data: JSON.parse(dataValue) });
      } catch {}
    }

    return events;
  }

  async function handleStandardReply(payload) {
    const res = await fetch(`${API}/support`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify(payload)
    });

    const data = await parseApiResponse(res);

    if (res.status === 402) {
      pushLimitMessage(true);
      throw new Error(detailFromApiBody(data) || "Plan limit reached. Upgrade to continue.");
    }

    if (!res.ok) {
      throw new Error(detailFromApiBody(data) || `Support request failed (${res.status}).`);
    }
    return data;
  }

  async function handleStreamReply(payload, row, stepsEl) {
    const res = await fetch(`${API}/support/stream`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify(payload)
    });

    if (!res.ok || !res.body) {
      const data = await parseApiResponse(res);
      if (res.status === 402) {
        pushLimitMessage(true);
        throw new Error(detailFromApiBody(data) || "Plan limit reached. Upgrade to continue.");
      }
      throw new Error(detailFromApiBody(data) || `Streaming failed (${res.status}).`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalData = null;

    const processEvents = (raw) => {
      const parsedEvents = parseSseEvents(raw);
      for (const item of parsedEvents) {
        if (item.event === "chunk") {
          appendAssistantChunk(row, item.data.text || "");
          scrollMessagesToBottom();
        }

        if (item.event === "status") {
          const stage = String(item.data.stage || "");
          const label = item.data.label || stage || "streaming";

          if (stage === "reviewing") advanceStreamStep(stepsEl, 0);
          else if (stage === "routing") advanceStreamStep(stepsEl, 1);
          else if (stage === "acting" || stage === "responding") advanceStreamStep(stepsEl, 2);
          else if (stage === "finalizing") advanceStreamStep(stepsEl, 3);

          updateStreamStatus(`Response: ${label}`);
        }

        if (item.event === "result") {
          finalData = item.data;
        }

        if (item.event === "usage_warning" && item.data) {
          applyUsageWarningFromStream(item.data);
        }

        if (item.event === "done") {
          /* stream may emit usage_warning after done */
        }
      }
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";

      for (const part of parts) {
        processEvents(`${part}\n\n`);
      }
    }

    if (buffer.trim()) {
      processEvents(buffer);
    }

    return finalData;
  }

  function updateStatsFromResult(data = {}) {
    state.totalInteractions += 1;
    state.avgConfidence =
      state.totalInteractions === 1
        ? Number(data.confidence || 0)
        : (state.avgConfidence * (state.totalInteractions - 1) + Number(data.confidence || 0)) / state.totalInteractions;

    state.avgQuality =
      state.totalInteractions === 1
        ? Number(data.quality || 0)
        : (state.avgQuality * (state.totalInteractions - 1) + Number(data.quality || 0)) / state.totalInteractions;

    setText(els.statInteractions, formatMetric(state.totalInteractions, 0));
    setText(els.statConfidence, formatMetric(state.avgConfidence, 2));
    setText(els.statQuality, formatMetric(state.avgQuality, 2));

    if (String(data.action || "none").toLowerCase() !== "none") {
      state.actionsCount += 1;
      setText(els.statActions, formatMetric(state.actionsCount, 0));
    }
  }

  function ensureOpsCard() {
    let card = document.getElementById("xalvionOpsCard");
    if (card) return card;

    card = document.createElement("div");
    card.id = "xalvionOpsCard";
    card.className = "ops-card";
    card.innerHTML = `
      <div class="panel-head">
        <div>
          <div class="panel-title">Latest operator run</div>
          <div class="panel-copy">Posture, value surfaced, and time saved — same signals your sidepanel traces, condensed for the rail.</div>
        </div>
      </div>
      <div class="ops-grid">
        <div class="ops-metric">
          <div class="ops-metric-label">Action</div>
          <div class="ops-metric-value" id="opsLatestAction">—</div>
        </div>
        <div class="ops-metric">
          <div class="ops-metric-label">Queue</div>
          <div class="ops-metric-value" id="opsLatestQueue">—</div>
        </div>
        <div class="ops-metric">
          <div class="ops-metric-label">Confidence</div>
          <div class="ops-metric-value" id="opsLatestConfidence">0.00</div>
        </div>
        <div class="ops-metric">
          <div class="ops-metric-label">Protected</div>
          <div class="ops-metric-value" id="opsLatestValue">$0</div>
        </div>
        <div class="ops-metric">
          <div class="ops-metric-label">Est. time saved</div>
          <div class="ops-metric-value" id="opsTimeSaved">—</div>
        </div>
        <div class="ops-metric">
          <div class="ops-metric-label">Posture</div>
          <div class="ops-metric-value" id="opsPosture">—</div>
        </div>
      </div>
      <div class="ops-run-line" id="opsRunNarrative">${ICONS.spark}<span>Waiting for the next operator run.</span></div>
    `;

    if (els.railInner) els.railInner.appendChild(card);
    else if (els.usageCard?.parentElement) els.usageCard.parentElement.appendChild(card);

    return card;
  }

  function updateLatestRunCard(data = {}) {
    ensureOpsCard();

    const latestAction = document.getElementById("opsLatestAction");
    const latestQueue = document.getElementById("opsLatestQueue");
    const latestConfidence = document.getElementById("opsLatestConfidence");
    const latestValue = document.getElementById("opsLatestValue");
    const latestTime = document.getElementById("opsTimeSaved");
    const latestPosture = document.getElementById("opsPosture");
    const latestNarrative = document.getElementById("opsRunNarrative");

    const decision = data.decision || {};
    const triage = data.triage || {};
    const impact = data.impact || {};
    const mins = Number(impact.agent_minutes_saved || impact.time_saved_est_min || 0);

    if (latestAction) latestAction.textContent = displayActionLabel(data);
    if (latestQueue) latestQueue.textContent = displayQueueLabel({ decision });
    if (latestConfidence) latestConfidence.textContent = formatMetric(data.confidence || 0, 2);
    if (latestValue) latestValue.textContent = formatMoney(impact.money_saved || impact.amount || data.amount || 0);
    if (latestTime) {
      latestTime.textContent = mins > 0 ? `${Math.round(mins)} min` : "—";
    }
    if (latestPosture) latestPosture.textContent = operatorPostureLabel(data);

    if (latestNarrative) {
      const reason = explainWhyAction(data);
      const value = formatMoney(impact.money_saved || impact.amount || data.amount || 0);
      const posture = operatorPostureLabel(data);
      const risk = String(decision.risk_level || triage.risk_level || "medium");
      latestNarrative.innerHTML = `${ICONS.spark}<span>${escapeHtml(`Operator system · ${posture} · ${risk} risk · value surfaced ${value}. ${reason}`)}</span>`;
    }
  }

  function updateRevenueCard(data = {}) {
    let card = document.getElementById("xalvionRevenueCard");

    if (!card) {
      card = document.createElement("div");
      card.id = "xalvionRevenueCard";
      card.className = "rev-card";
      card.innerHTML = `
        <div class="panel-head">
          <div>
            <div class="panel-title">Revenue layer</div>
            <div class="panel-copy">The business effect of each decision should be visible inside the workspace.</div>
          </div>
        </div>
        <div class="rev-grid">
          <div class="rev-metric">
            <div class="rev-metric-label">Value protected</div>
            <div class="rev-metric-value" id="revMoneySaved">$0</div>
          </div>
          <div class="rev-metric">
            <div class="rev-metric-label">Auto resolution</div>
            <div class="rev-metric-value" id="revAutoRate">0%</div>
          </div>
          <div class="rev-metric">
            <div class="rev-metric-label">Refund total</div>
            <div class="rev-metric-value" id="revRefunds">$0</div>
          </div>
          <div class="rev-metric">
            <div class="rev-metric-label">High-risk saves</div>
            <div class="rev-metric-value" id="revChurn">0</div>
          </div>
        </div>
        <div class="rev-bar"><div id="revBar"></div></div>
        <div class="panel-copy" id="revRoiLabel">Processing first tickets…</div>
      `;

      if (els.railInner) els.railInner.appendChild(card);
      else if (els.usageCard?.parentElement) els.usageCard.parentElement.appendChild(card);
    }

    const impact = data.impact || {};
    const decision = data.decision || {};
    const toolStatus = String(data.tool_status || "");

    const moneySaved = Number(impact.money_saved || impact.amount || data.amount || 0);
    const refundTotal = String(data.action || "").toLowerCase() === "refund" ? Number(data.amount || 0) : 0;
    const autoRate = state.totalInteractions > 0 ? Math.round((state.actionsCount / state.totalInteractions) * 100) : 0;
    const churnSaved = Number(decision.priority === "high" && toolStatus !== "error");

    const revMoneySaved = document.getElementById("revMoneySaved");
    const revAutoRate = document.getElementById("revAutoRate");
    const revRefunds = document.getElementById("revRefunds");
    const revChurn = document.getElementById("revChurn");
    const revBar = document.getElementById("revBar");
    const revRoiLabel = document.getElementById("revRoiLabel");

    if (revMoneySaved) revMoneySaved.textContent = formatMoney(moneySaved);
    if (revAutoRate) revAutoRate.textContent = `${autoRate}%`;
    if (revRefunds) revRefunds.textContent = formatMoney(refundTotal);
    if (revChurn) revChurn.textContent = String(churnSaved ? 1 : 0);
    if (revBar) revBar.style.width = `${Math.min(100, autoRate)}%`;

    if (revRoiLabel) {
      revRoiLabel.textContent = moneySaved > 0
        ? `${formatMoney(moneySaved)} of visible value was protected on this case.`
        : "The workspace is collecting business impact as support runs complete.";
    }
  }

  function isMobileViewport() {
    return window.matchMedia("(max-width: 980px)").matches;
  }

  function getMobileViewportHeight() {
    const visualHeight = window.visualViewport?.height;
    const height = typeof visualHeight === "number" && visualHeight > 0 ? visualHeight : window.innerHeight;
    return `${height}px`;
  }

  function syncMobileViewport() {
    document.documentElement.style.setProperty("--app-height", getMobileViewportHeight());

    if (!isMobileViewport()) {
      document.body.classList.remove("mobile-scroll-mode");
      if (els.messages) {
        els.messages.style.overflowY = "auto";
        els.messages.style.webkitOverflowScrolling = "touch";
        els.messages.style.maxHeight = "";
      }
      return;
    }

    document.body.classList.add("mobile-scroll-mode");

    if (els.messages) {
      els.messages.style.overflowY = "visible";
      els.messages.style.webkitOverflowScrolling = "auto";
      els.messages.style.maxHeight = "none";
    }
  }

  function scrollComposerIntoView() {
    if (!isMobileViewport()) return;
    const composer = els.messageInput?.closest(".composer-wrap") || els.messageInput?.closest(".composer") || els.messageInput;
    if (!composer) return;

    window.setTimeout(() => {
      composer.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
    }, 180);
  }

  function buildKeyboardOverlay() {
    if (document.getElementById("xalvionShortcutOverlay")) return;

    const overlay = document.createElement("div");
    overlay.id = "xalvionShortcutOverlay";
    overlay.style.cssText = `
      position:fixed;
      inset:0;
      background:rgba(6,8,15,.66);
      backdrop-filter:blur(16px);
      z-index:99;
      display:none;
      align-items:center;
      justify-content:center;
      padding:20px;
    `;

    overlay.innerHTML = `
      <div style="
        width:min(560px,100%);
        border-radius:24px;
        border:1px solid rgba(255,255,255,.08);
        background:linear-gradient(180deg, rgba(18,22,34,.88), rgba(9,13,25,.92));
        box-shadow:0 30px 80px rgba(0,0,0,.34);
        padding:20px;
        color:rgba(245,248,255,.97);
      ">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:14px;">
          <div style="font-size:16px;font-weight:800;letter-spacing:-.02em;">Workspace shortcuts</div>
          <button id="xalvionShortcutClose" type="button" style="
            width:34px;height:34px;border-radius:10px;border:1px solid rgba(255,255,255,.08);
            background:rgba(255,255,255,.04);color:#fff;cursor:pointer;
          ">×</button>
        </div>
        <div style="display:grid;gap:10px;">
          ${[
            ["?", "Open this shortcut panel"],
            ["/", "Focus the composer"],
            ["Ctrl/Cmd + Enter", "Send current message"],
            ["N", "Start a fresh thread"],
            ["D", "Load preview access demo"],
            ["E", "Export current thread"]
          ]
            .map(
              ([key, desc]) => `
            <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 12px;border-radius:14px;border:1px solid rgba(255,255,255,.06);background:rgba(255,255,255,.025);">
              <div style="font-size:13px;color:rgba(224,234,255,.9);">${escapeHtml(desc)}</div>
              <div style="font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;color:rgba(196,211,248,.74);">${escapeHtml(key)}</div>
            </div>
          `
            )
            .join("")}
        </div>
      </div>
    `;

    document.body.appendChild(overlay);

    const closeBtn = document.getElementById("xalvionShortcutClose");
    closeBtn?.addEventListener("click", () => {
      overlay.style.display = "none";
    });

    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) overlay.style.display = "none";
    });
  }

  function toggleKeyboardOverlay(show) {
    const overlay = document.getElementById("xalvionShortcutOverlay");
    if (!overlay) return;
    overlay.style.display = show ? "flex" : "none";
  }

  async function sendMessage() {
    const payload = buildSupportPayload();
    if (!payload.message || state.sending) return;

    if (!enforceWorkspaceLimit()) {
      if (!isAuthenticated()) {
        const reset = maybeResetGuestUsage(true);
        if (reset) {
          updatePlanUI("free", getGuestUsage(), GUEST_USAGE_LIMIT, Math.max(0, GUEST_USAGE_LIMIT - getGuestUsage()));
          setNotice("info", "Preview reset", "Guest preview access was refreshed for this session.");
        }
      }
      if (!enforceWorkspaceLimit()) return;
    }

    ensureInjectedStyles();
    clearEmptyState();

    addUserMessage(payload.message);

    if (els.messageInput) {
      els.messageInput.value = "";
      autoResizeTextarea();
      saveDraft("");
    }

    const row = addAssistantMessage("");
    const stepsEl = createStreamSteps();
    const replyNode = getAssistantCopyNode(row);
    if (replyNode) {
      replyNode.innerHTML = createTypingMarkup();
      replyNode.parentElement.insertBefore(stepsEl, replyNode);
    }

    setSending(true);
    setNotice("info", "Running support case", "Streaming live action states from the support pipeline.");

    const stepTimers = [
      window.setTimeout(() => advanceStreamStep(stepsEl, 1), 600),
      window.setTimeout(() => advanceStreamStep(stepsEl, 2), 1400),
      window.setTimeout(() => advanceStreamStep(stepsEl, 3), 2400)
    ];

    try {
      let data = null;

      try {
        data = await handleStreamReply(payload, row, stepsEl);
      } catch (streamErr) {
        authDebugLog("support_stream_fallback", streamErr);
        try {
          data = await handleStandardReply(payload);
          const fb = data.reply || data.response || data.final || "";
          setAssistantCopy(row, fb || "No response returned.");
        } catch (stdErr) {
          const combined =
            (stdErr && stdErr.message) ||
            (streamErr && streamErr.message) ||
            "Support request failed.";
          throw new Error(combined);
        }
      }

      if (!data) {
        authDebugLog("support_empty_stream", "falling back to POST /support");
        try {
          data = await handleStandardReply(payload);
          const fb = data.reply || data.response || data.final || "";
          setAssistantCopy(row, fb || "No response returned.");
        } catch (stdErr) {
          throw new Error(stdErr.message || "No response returned.");
        }
      }

      if (data && isStreamFailureResult(data)) {
        authDebugLog("support_stream_failure_payload", data.reason || data.mode || data.tool_status);
        try {
          const std = await handleStandardReply(payload);
          if (std && !isStreamFailureResult(std)) {
            data = std;
            const fb = std.reply || std.response || std.final || "";
            if (fb) setAssistantCopy(row, fb);
          }
        } catch (retryErr) {
          authDebugLog("support_standard_after_stream_payload_failed", retryErr);
        }
      }

      stepTimers.forEach((timer) => window.clearTimeout(timer));
      removeStreamSteps(stepsEl);

      if (!data) throw new Error("No response returned.");

      data = normalizeWorkspaceResult(data);
      state.latestRun = data;

      const replyText = data.reply || data.response || data.final || "No response returned.";
      setAssistantCopy(row, replyText);

      const footer = getAssistantFooterNode(row);
      if (footer) {
        footer.innerHTML = "";
        footer.appendChild(createMetaRow(data));

        const toolsWrap = document.createElement("div");
        addCopyControl(toolsWrap, replyText, row);
        footer.appendChild(toolsWrap);

        const details = createDetailsPanel(data);
        footer.parentElement.appendChild(details);
        mountOperatorDecisionPanel(row, data, replyText);
      }

      updateStatsFromResult(data);
      updateRevenueCard(data);
      updateLatestRunCard(data);
      updateSystemNarrative(data);

      const hasServerUsage = Number.isFinite(Number(data.usage));
      const planTier = data.tier || state.tier;
      const planLimit = Number(data.plan_limit || data.limit || state.limit || GUEST_USAGE_LIMIT);
      const planRemaining = Number.isFinite(Number(data.remaining)) ? Number(data.remaining) : null;
      const responseUsername = String(data.username || "").trim().toLowerCase();
      const responseIsGuest = !responseUsername || responseUsername === "guest" || responseUsername === "dev_user";

      if (!isAuthenticated() && responseIsGuest) {
        const localGuestUsage = getGuestUsage();
        const nextGuestUsage = hasServerUsage
          ? Math.max(Number(data.usage || 0), localGuestUsage + 1)
          : (localGuestUsage + 1);

        updatePlanUI(
          "free",
          nextGuestUsage,
          GUEST_USAGE_LIMIT,
          Math.max(0, GUEST_USAGE_LIMIT - nextGuestUsage)
        );
      } else if (hasServerUsage || planTier) {
        if (hasServerUsage) {
          updatePlanUI(
            planTier,
            Number(data.usage || 0),
            planLimit,
            planRemaining
          );
        } else {
          state.tier = planTier || state.tier;
          consumeWorkspaceRun();
        }
      } else {
        consumeWorkspaceRun();
      }

      if (data.username && data.username !== "guest" && data.username !== "dev_user") {
        state.username = data.username;
        persistAuth();
      }

      const usageAfterRun = getEffectiveUsage(state.usage);
      const limitAfterRun = getEffectiveLimit(state.tier, state.limit);
      const limitReachedAfterRun = usageAfterRun >= limitAfterRun && (String(state.tier || "free").toLowerCase() === "free" || !isAuthenticated());

      updateTopbarStatus();
      setNotice(data.action === "review" ? "warning" : "success", noticeTitleForResult(data), replyText);

      if (limitReachedAfterRun) {
        pushLimitMessage(true);
      } else {
        state.lastLimitNoticeKey = "";
      }
    } catch (error) {
      stepTimers.forEach((timer) => window.clearTimeout(timer));
      removeStreamSteps(stepsEl);
      const errText =
        (error && error.message) ||
        "Something went wrong while processing this support request.";
      setAssistantCopy(row, errText);
      setNotice("error", "Request failed", errText);
      authDebugLog("support_failed", error);
    } finally {
      setSending(false);
      scrollMessagesToBottom(true);
      refreshMessageShellGlow();
    }
  }

  async function applyAuthenticatedSession(data, username, noticeOpts) {
    state.token = data.token || "";
    state.username = data.username || username;
    clearGuestUsage();
    const limRaw = Number(data.limit);
    const lim = Number.isFinite(limRaw) && limRaw > 0 ? limRaw : FREE_USAGE_LIMIT;
    const use = Math.max(0, Number(data.usage || 0) || 0);
    const remRaw = Number(data.remaining);
    const rem = Number.isFinite(remRaw) ? Math.max(0, remRaw) : Math.max(0, lim - use);
    updatePlanUI(data.tier || "free", use, lim, rem);
    persistAuth();
    updateTopbarStatus();
    await loadIntegrations();
    if (noticeOpts) {
      setNotice(noticeOpts.kind, noticeOpts.title, noticeOpts.detail);
    }
    await hydrateMe();
    await loadDashboardSummary();
    await loadRefundHistory();
    await loadCrmLeads();
    await loadRevenueMetrics();
  }

  async function signup() {
    if (state.authSubmitting) return;

    const username = (els.usernameInput?.value || "").trim();
    const password = (els.passwordInput?.value || "").trim();

    if (!username || !password) {
      setNotice("warning", "Missing credentials", "Enter a username and password to create your workspace account.");
      return;
    }

    const ruleIssues = describeAuthRuleViolations(username, password);
    if (ruleIssues.length) {
      setNotice("warning", "Check account requirements", ruleIssues.join(" "));
      return;
    }

    setAuthSubmitting(true);
    try {
      const res = await fetch(`${API}/signup`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ username, password })
      });

      const data = await parseApiResponse(res);
      if (!res.ok) {
        throw new Error(
          detailFromApiBody(data) || `Signup failed (${res.status}).`
        );
      }

      const loginRes = await fetch(`${API}/login`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ username, password })
      });
      const loginData = await parseApiResponse(loginRes);
      if (!loginRes.ok) {
        throw new Error(
          detailFromApiBody(loginData) ||
            "Account created but automatic login failed. Use Log in with the same password."
        );
      }

      await applyAuthenticatedSession(loginData, username, {
        kind: "success",
        title: "Account ready",
        detail: `Signed in as ${username}. Usage, plan, integrations, and CRM are synced.`
      });
    } catch (error) {
      authDebugLog("signup_failed", error);
      setNotice("error", "Signup failed", error.message || "Could not create account.");
    } finally {
      setAuthSubmitting(false);
    }
  }

  async function login() {
    if (state.authSubmitting) return;

    const username = (els.usernameInput?.value || "").trim();
    const password = (els.passwordInput?.value || "").trim();

    if (!username || !password) {
      setNotice("warning", "Missing credentials", "Enter your username and password to log in.");
      return;
    }

    setAuthSubmitting(true);
    try {
      const res = await fetch(`${API}/login`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ username, password })
      });

      const data = await parseApiResponse(res);
      if (!res.ok) {
        throw new Error(detailFromApiBody(data) || `Login failed (${res.status}).`);
      }

      await applyAuthenticatedSession(data, username, {
        kind: "success",
        title: "Logged in",
        detail: `Welcome back, ${username}. Your workspace is synced.`
      });
    } catch (error) {
      authDebugLog("login_failed", error);
      clearAuth();
      updateTopbarStatus();
      updatePlanUI("free", 0, 3, 3);
      setNotice("error", "Login failed", error.message || "Could not log in.");
    } finally {
      setAuthSubmitting(false);
    }
  }

  async function logout() {
    clearAuth();
    updatePlanUI("free", 0, 3, 3);
    updateTopbarStatus();
    setNotice("success", "Logged out", "Guest workspace restored.");
    await hydrateMe();
    await loadDashboardSummary();
    await loadIntegrations();
    await loadRefundHistory();
    await loadCrmLeads();
    await loadRevenueMetrics();
  }

  function activatePreviewAccess() {
    maybeResetGuestUsage(true);
    updatePlanUI("free", getGuestUsage(), GUEST_USAGE_LIMIT, Math.max(0, GUEST_USAGE_LIMIT - getGuestUsage()));
    const demoText = "A customer says: I was charged twice for one order and wants it fixed today.";
    if (els.messageInput) {
      els.messageInput.value = demoText;
      autoResizeTextarea();
      saveDraft(demoText);
      els.messageInput.focus();
    }
    setNotice("info", "Quick demo loaded", "A high-intent billing case is ready to run through the workspace.");
  }

  async function upgradePlan(tier) {
    if (!tier) return;

    if (!state.token || !state.username) {
      setNotice("warning", "Authentication required", "Create an account or log in before upgrading the workspace plan.");
      return;
    }

    try {
      await loadDashboardSummary();

      const res = await fetch(`${API}/billing/upgrade`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ tier })
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Upgrade failed.");

      if (data.checkout_url) {
        refreshUpgradeValueSummary();
        window.location.href = data.checkout_url;
        return;
      }

      updatePlanUI(
        data.tier || tier,
        Number(data.usage || state.usage),
        Number(data.limit || state.limit),
        Number(data.remaining || state.remaining)
      );
      setNotice("success", "Plan updated", `Workspace upgraded to ${formatTier(tier)}.`);
      updateTopbarStatus();
    } catch (error) {
      setNotice("error", "Upgrade failed", error.message || "Could not upgrade the plan.");
    }
  }

  async function healthCheck() {
    try {
      const res = await fetch(`${API}/health`, { headers: headers(false) });
      updateBackendStatus(res.ok);

      if (!res.ok) {
        setNotice(
          "warning",
          "Backend delayed",
          "The API is responding slowly or partially. The workspace will retry automatically."
        );
        return;
      }

      const data = await res.json().catch(() => ({}));
      if (data?.status === "ok") updateBackendStatus(true);
    } catch {
      updateBackendStatus(false);
      setNotice("error", "Backend unavailable", "The API is not responding right now. Reload when the deployment is live.");
    }
  }

  async function hydrateMe() {
    if (!state.token) {
      state.usagePct = 0;
      state.approachingLimit = false;
      state.atLimit = false;
      state.valueSignals = null;
      updatePlanUI("free", getGuestUsage(), GUEST_USAGE_LIMIT, Math.max(0, GUEST_USAGE_LIMIT - getGuestUsage()));
      updateAuthStatus();
      syncUsageApproachNotice();
      return { ok: true, staleCleared: false };
    }

    try {
      const res = await fetch(`${API}/me`, { headers: headers(false) });
      const data = await res.json().catch(() => ({}));

      if (res.status === 401) {
        invalidateSessionFrom401();
        return { ok: false, staleCleared: true };
      }

      if (!res.ok) throw new Error("me failed");

      state.username = data.username || state.username;
      const upct = Number(data.usage_pct);
      state.usagePct = Number.isFinite(upct) ? upct : 0;
      state.approachingLimit = Boolean(data.approaching_limit);
      state.atLimit = Boolean(data.at_limit);
      state.valueSignals =
        data.value_signals && typeof data.value_signals === "object" ? data.value_signals : null;

      updatePlanUI(
        data.tier || state.tier,
        Number(data.usage || state.usage),
        Number(data.limit || state.limit),
        Number(data.remaining || state.remaining)
      );

      persistAuth();
      updateTopbarStatus();
      syncUsageApproachNotice();
      return { ok: true, staleCleared: false };
    } catch {
      updateTopbarStatus();
      return { ok: false, staleCleared: false };
    }
  }

  async function loadDashboardSummary() {
    try {
      const res = await fetch(`${API}/dashboard/summary`, { headers: headers(false) });
      if (!res.ok) throw new Error("dashboard failed");

      const data = await res.json().catch(() => ({}));

      if (typeof data.total_interactions !== "undefined") {
        state.totalInteractions = Number(data.total_interactions || 0);
      } else if (typeof data.total_tickets !== "undefined") {
        state.totalInteractions = Number(data.total_tickets || 0);
      }

      if (typeof data.avg_confidence !== "undefined") {
        state.avgConfidence = Number(data.avg_confidence || 0);
      }

      if (typeof data.avg_quality !== "undefined") {
        state.avgQuality = Number(data.avg_quality || 0);
      }

      if (typeof data.actions !== "undefined") {
        state.actionsCount = Number(data.actions || 0);
      }

      setText(els.statInteractions, formatMetric(state.totalInteractions, 0));
      setText(els.statQuality, formatMetric(state.avgQuality, 2));
      setText(els.statConfidence, formatMetric(state.avgConfidence, 2));
      setText(els.statActions, formatMetric(state.actionsCount, 0));

      if (typeof data.your_tier !== "undefined" || typeof data.your_usage !== "undefined") {
        updatePlanUI(
          data.your_tier || state.tier,
          Number(data.your_usage || state.usage),
          Number(data.your_limit || state.limit),
          Number(data.remaining || state.remaining)
        );
      }

      state.dashboardStats = data;
      refreshUpgradeValueSummary();
    } catch {
      setText(els.statInteractions, formatMetric(state.totalInteractions, 0));
      setText(els.statQuality, formatMetric(state.avgQuality, 2));
      setText(els.statConfidence, formatMetric(state.avgConfidence, 2));
      setText(els.statActions, formatMetric(state.actionsCount, 0));
    }
  }

  function resetWorkspaceThread() {
    if (!els.messages) return;
    els.messages.innerHTML = "";
    state.latestRun = null;
    addEmptyState();
    updateSystemNarrative(null);
    updateTopbarStatus();
    scrollMessagesToBottom(true);
  }

  function exportThread() {
    if (!els.messages) return;

    const lines = [];
    els.messages.querySelectorAll(".msg-card").forEach((card) => {
      const who = card.querySelector(".msg-who span:last-child")?.textContent || "Message";
      const text = card.querySelector(".js-reply-text")?.textContent || "";
      if (text.trim()) lines.push(`${who}: ${text.trim()}`);
    });

    if (!lines.length) {
      setNotice("warning", "Nothing to export", "Run at least one case before exporting the thread.");
      return;
    }

    const blob = new Blob([lines.join("\n\n")], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "xalvion-thread.txt";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);

    setNotice("success", "Thread exported", "The current workspace thread was downloaded as a text file.");
  }

  
  function escapeAttr(value) {
    return String(value ?? "").replaceAll('"', "&quot;");
  }

  function renderCrmSummary(summary = {}) {
    state.crmSummary = {
      new: Number(summary.new || 0),
      contacted: Number(summary.contacted || 0),
      replied: Number(summary.replied || 0),
      closed: Number(summary.closed || 0),
      due_followups: Number(summary.due_followups || 0)
    };

    if (els.crmSummary) {
      const total = state.crmSummary.new + state.crmSummary.contacted + state.crmSummary.replied + state.crmSummary.closed;
      const detail = [
        `${total} total`,
        `${state.crmSummary.contacted} contacted`,
        `${state.crmSummary.replied} replied`,
        `${state.crmSummary.closed} closed`
      ].join(" • ");
      setText(els.crmSummary, total ? detail : "Sign in to build a tracked outreach queue and keep follow-ups on time.");
    }

    setText(els.crmNewCount, state.crmSummary.new);
    setText(els.crmDueCount, state.crmSummary.due_followups);
  }

  function renderCrmDailySummary(summary = {}) {
    state.crmDailySummary = {
      due_followups: Number(summary.due_followups || 0),
      new_today: Number(summary.new_today || 0),
      closed_today: Number(summary.closed_today || 0),
      closed_revenue_today: Number(summary.closed_revenue_today || 0),
      best_source: String(summary.best_source || "manual"),
      hottest_open: Array.isArray(summary.hottest_open) ? summary.hottest_open : [],
      reminders: Array.isArray(summary.reminders) ? summary.reminders : []
    };

    const lines = [
      `${state.crmDailySummary.due_followups} due now`,
      `${state.crmDailySummary.new_today} new today`,
      `${state.crmDailySummary.closed_today} closed today`
    ];
    if (state.crmDailySummary.closed_revenue_today > 0) {
      lines.push(`$${state.crmDailySummary.closed_revenue_today.toFixed(2)} closed today`);
    }
    setText(els.crmTodaySummary, lines.join(" • ") || "No pipeline activity yet.");
    setText(els.crmTodayDueCount, state.crmDailySummary.due_followups);
    setText(els.crmTodayNewCount, state.crmDailySummary.new_today);
    setText(els.crmTodayClosedCount, state.crmDailySummary.closed_today);
    setText(els.crmTodayBestSource, state.crmDailySummary.best_source || "manual");

    if (els.crmHotList) {
      const items = state.crmDailySummary.hottest_open;
      els.crmHotList.innerHTML = items.length ? items.map((lead) => `
        <div class="crm-hot-item">
          <div class="crm-hot-copy">
            <div class="crm-hot-title">${escapeHtml(lead.username || "Lead")}</div>
            <div class="crm-hot-sub">${escapeHtml(String(lead.status || "new").toUpperCase())} • ${escapeHtml(lead.source || "manual")} • score ${Number(lead.score || 0)}</div>
          </div>
          <div class="crm-chip-row"><span class="crm-chip">Hot ${Number(lead.hotness || 0)}</span></div>
        </div>
      `).join("") : '<div class="refund-empty">No hot deals yet.</div>';
    }
  }

  function renderRevenueMetrics(metrics = {}) {
    const safeMetrics = metrics && typeof metrics === "object" ? metrics : {};
    const totals = safeMetrics.totals && typeof safeMetrics.totals === "object" ? safeMetrics.totals : {};
    const bySource = Array.isArray(safeMetrics.by_source) ? safeMetrics.by_source : [];
    state.revenueMetrics = {
      totals,
      by_source: bySource,
      best_source: String(safeMetrics.best_source || "manual"),
      forecast: safeMetrics.forecast && typeof safeMetrics.forecast === "object" ? safeMetrics.forecast : {}
    };

    const leads = Number(totals.leads || 0);
    const revenue = Number(totals.revenue || 0);
    const summaryBits = [
      `${leads} leads`,
      `${Number(totals.demo || 0)} demos`,
      `${Number(totals.closed || 0)} closed`
    ];
    if (revenue > 0) summaryBits.push(`$${revenue.toFixed(2)} revenue`);
    setText(els.revenueSummary, leads ? summaryBits.join(" • ") : "Track pipeline conversion, source quality, and closed revenue as you work the queue.");
    setText(els.revenueLeadsCount, leads);
    setText(els.revenueReplyRate, `${Number(totals.reply_rate || 0).toFixed(1)}%`);
    setText(els.revenueClosingRate, `${Number(totals.closing_rate || 0).toFixed(1)}%`);
    setText(els.revenueWinRate, `${Number(totals.win_rate || 0).toFixed(1)}%`);
    setText(els.revenueTotalValue, `$${revenue.toFixed(2)}`);
    setText(els.revenueBestSource, state.revenueMetrics.best_source || "manual");

    renderForecastMetrics(state.revenueMetrics.forecast || {});

    if (els.sourceList) {
      els.sourceList.innerHTML = bySource.length ? bySource.map((row) => `
        <div class="crm-hot-item">
          <div class="crm-hot-copy">
            <div class="crm-hot-title">${escapeHtml(row.source || "manual")}</div>
            <div class="crm-hot-sub">${Number(row.leads || 0)} leads • ${Number(row.closed || 0)} closed • ${Number(row.reply_rate || 0).toFixed(1)}% reply • ${Number(row.win_rate || 0).toFixed(1)}% win</div>
          </div>
          <div class="crm-chip-row"><span class="crm-chip">$${Number(row.revenue || 0).toFixed(2)}</span></div>
        </div>
      `).join("") : '<div class="refund-empty">No source performance data yet.</div>';
    }
  }

  function renderForecastMetrics(forecast = {}) {
    const safeForecast = forecast && typeof forecast === "object" ? forecast : {};
    const pipelineValue = Number(safeForecast.pipeline_value || 0);
    const weightedOpenRevenue = Number(safeForecast.weighted_open_revenue || 0);
    const projectedRevenue = Number(safeForecast.projected_total_revenue || 0);
    const coverage = Number(safeForecast.coverage_ratio || 0);
    const stageBreakdown = Array.isArray(safeForecast.stage_breakdown) ? safeForecast.stage_breakdown : [];
    const topDeals = Array.isArray(safeForecast.top_weighted_deals) ? safeForecast.top_weighted_deals : [];

    setText(els.forecastSummary, pipelineValue ? `${topDeals.length} weighted deals • ${coverage.toFixed(1)}% coverage` : "Track weighted pipeline value by stage and see the most important open deals.");
    setText(els.forecastPipelineValue, `$${pipelineValue.toFixed(2)}`);
    setText(els.forecastWeightedRevenue, `$${weightedOpenRevenue.toFixed(2)}`);
    setText(els.forecastProjectedRevenue, `$${projectedRevenue.toFixed(2)}`);
    setText(els.forecastCoverage, `${coverage.toFixed(1)}%`);

    if (els.forecastStageList) {
      els.forecastStageList.innerHTML = stageBreakdown.length ? stageBreakdown.map((row) => `
        <div class="crm-hot-item">
          <div class="crm-hot-copy">
            <div class="crm-hot-title">${escapeHtml(String(row.stage || "lead").toUpperCase())}</div>
            <div class="crm-hot-sub">${Number(row.count || 0)} deals • prob ${(Number(row.probability || 0) * 100).toFixed(0)}% • pipeline $${Number(row.pipeline_value || 0).toFixed(2)}</div>
          </div>
          <div class="crm-chip-row"><span class="crm-chip">$${Number(row.weighted_value || 0).toFixed(2)}</span></div>
        </div>
      `).join("") : '<div class="refund-empty">No pipeline forecast yet.</div>';
    }

    if (els.forecastDealList) {
      els.forecastDealList.innerHTML = topDeals.length ? topDeals.map((deal) => `
        <div class="crm-hot-item">
          <div class="crm-hot-copy">
            <div class="crm-hot-title">${escapeHtml(deal.username || "Lead")}</div>
            <div class="crm-hot-sub">${escapeHtml(String(deal.stage || "lead").toUpperCase())} • ${escapeHtml(deal.source || "manual")} • ${(Number(deal.probability || 0)).toFixed(1)}% confidence</div>
          </div>
          <div class="crm-chip-row"><span class="crm-chip">$${Number(deal.weighted_value || 0).toFixed(2)}</span></div>
        </div>
      `).join("") : '<div class="refund-empty">No weighted opportunities yet.</div>';
    }
  }

  async function loadRevenueMetrics() {
    if (!state.token || !state.username) {
      renderRevenueMetrics({ totals: {}, by_source: [], best_source: "manual" });
      return;
    }
    try {
      const data = await apiGet("/analytics/metrics");
      renderRevenueMetrics(data.metrics || {});
    } catch (error) {
      renderRevenueMetrics({ totals: {}, by_source: [], best_source: "manual" });
    }
  }

  function promptConvertLead(leadId) {
    const lead = state.crmLeads.find((item) => String(item.id) === String(leadId));
    if (!lead) return;
    const raw = window.prompt(`Enter closed deal value for ${lead.username}`, String(lead.value || lead.converted_value || "99"));
    if (raw === null) return;
    const parsed = Number(raw);
    if (!Number.isFinite(parsed) || parsed < 0) {
      setNotice("warning", "Invalid value", "Enter a valid number for the closed deal value.");
      return;
    }
    convertLead(leadId, parsed);
  }

  async function convertLead(leadId, value) {
    if (!leadId) return;
    try {
      const data = await apiPost(`/leads/${encodeURIComponent(leadId)}/convert`, { value, note: `Closed at $${Number(value).toFixed(2)}` });
      renderCrmLeads(Array.isArray(data.items) ? data.items : state.crmLeads, data.summary || {}, data.daily_summary || {}, data.metrics || null);
      renderRevenueMetrics(data.metrics || state.revenueMetrics || {});
      setNotice("success", "Lead converted", `Closed revenue updated by $${Number(value).toFixed(2)}.`);
    } catch (error) {
      setNotice("error", "Conversion failed", error.message || "Could not close this lead.");
    }
  }

  function stageOptionsMarkup(currentStage) {
    const options = ["lead", "contacted", "replied", "demo", "closed"];
    return options.map((stage) => `<option value="${stage}"${stage === currentStage ? " selected" : ""}>${stage.toUpperCase()}</option>`).join("");
  }

  async function updateLeadStage(leadId, stage) {
    if (!leadId || !stage) return;
    try {
      const data = await apiPost(`/leads/${encodeURIComponent(leadId)}/status`, { stage, status: stage === "lead" ? "new" : (stage === "closed" ? "closed" : (stage === "contacted" ? "contacted" : "replied")) });
      renderCrmLeads(Array.isArray(data.items) ? data.items : state.crmLeads, data.summary || {}, data.daily_summary || {}, data.metrics || null);
      renderRevenueMetrics(data.metrics || state.revenueMetrics || {});
      setNotice("success", "Stage updated", `Lead moved to ${stage}.`);
    } catch (error) {
      setNotice("error", "Stage update failed", error.message || "Could not update stage.");
    }
  }

  function leadMessageForStatus(lead) {
    if (!lead) return "";
    if (lead.status === "contacted" && lead.follow_up_message) return lead.follow_up_message;
    return lead.message || "";
  }

  function leadTimeLabel(lead) {
    if (!lead) return "";
    if (lead.status === "contacted" && lead.follow_up_due) return `Follow-up due ${lead.follow_up_due.replace("T", " ").slice(0, 16)}`;
    if (lead.last_contacted) return `Last contacted ${String(lead.last_contacted).replace("T", " ").slice(0, 16)}`;
    return `Added ${String(lead.created_at || "").replace("T", " ").slice(0, 16)}`;
  }

  function renderLeadItems(items = [], target = null, mode = "queue") {
    const el = target || els.leadList;
    if (!el) return;

    if (!items.length) {
      el.innerHTML = `<div class="refund-empty">${mode === "followup" ? "No follow-ups due yet." : "No leads yet. Add one to start building your outreach queue."}</div>`;
      return;
    }

    el.innerHTML = `<div class="crm-list">${items.map((lead) => `
      <div class="crm-item">
        <div class="crm-item-head">
          <div>
            <div class="crm-item-title">${escapeHtml(lead.username || "Lead")}</div>
            <div class="crm-item-sub">${escapeHtml(lead.text || "")}</div>
          </div>
          <div class="crm-chip-row">
            <span class="crm-chip">Score ${Number(lead.score || 0)}</span>
            <span class="crm-chip">${escapeHtml(lead.source || "manual")}</span>
            <span class="crm-chip status-${escapeHtml(lead.status || "new")}">${escapeHtml((lead.status || "new").toUpperCase())}</span>
            <span class="crm-chip">Stage ${escapeHtml(String(lead.stage || lead.status || "lead").toUpperCase())}</span>
          </div>
        </div>
        <div class="crm-message">${escapeHtml(leadMessageForStatus(lead))}</div>
        <div class="crm-item-sub">${escapeHtml(leadTimeLabel(lead))}${Number(lead.converted_value || 0) > 0 ? ` • Closed $${Number(lead.converted_value || 0).toFixed(2)}` : (Number(lead.value || 0) > 0 ? ` • Value $${Number(lead.value || 0).toFixed(2)}` : "")}</div>
        <div class="crm-actions" style="align-items:center; flex-wrap:wrap;">
          <button class="crm-btn" type="button" data-lead-copy="${escapeAttr(lead.id)}">Copy message</button>
          ${lead.status === "new" ? `<button class="crm-btn followup" type="button" data-lead-status="${escapeAttr(lead.id)}" data-status-value="contacted">Mark sent</button>` : ""}
          ${(lead.status === "contacted" || lead.status === "replied") ? `<button class="crm-btn reply" type="button" data-lead-status="${escapeAttr(lead.id)}" data-status-value="replied">Mark replied</button>` : ""}
          ${lead.stage !== "demo" && lead.status !== "closed" ? `<button class="crm-btn" type="button" data-lead-stage="${escapeAttr(lead.id)}" data-stage-value="demo">Mark demo</button>` : ""}
          ${mode === "followup" ? `<button class="crm-btn followup" type="button" data-reminder-done="${escapeAttr(lead.id)}">Mark done</button><button class="crm-btn" type="button" data-reminder-snooze="${escapeAttr(lead.id)}">Snooze 1d</button>` : ""}
          ${lead.status !== "closed" ? `<button class="crm-btn close" type="button" data-lead-convert="${escapeAttr(lead.id)}">Close deal</button>` : ""}
          <label class="refund-label" style="display:flex; align-items:center; gap:6px; margin-left:auto; font-size:10px; letter-spacing:.12em;">
            <span>Stage</span>
            <select class="refund-input" data-stage-select="${escapeAttr(lead.id)}" style="height:30px; min-width:116px; padding:0 10px; font-size:11px;">
              ${stageOptionsMarkup(String(lead.stage || lead.status || "lead"))}
            </select>
          </label>
        </div>
      </div>
    `).join("")}</div>`;
  }

  function renderCrmLeads(items = [], summary = null, dailySummary = null, metrics = null) {
    state.crmLeads = Array.isArray(items) ? items.slice() : [];
    const computedSummary = summary || {};
    renderCrmSummary(computedSummary);
    renderCrmDailySummary(dailySummary || {});
    const queueItems = state.crmLeads.filter((lead) => lead.status !== "closed");
    const followups = state.crmLeads.filter((lead) => (lead.status === "contacted" || lead.status === "replied") && lead.follow_up_due);
    renderLeadItems(queueItems, els.leadList, "queue");
    renderLeadItems(followups, els.followupList, "followup");
    if (metrics) renderRevenueMetrics(metrics);
  }

  async function loadCrmLeads() {
    if (!state.token || !state.username) {
      state.crmLeads = [];
      renderCrmLeads([], { new: 0, contacted: 0, replied: 0, closed: 0, due_followups: 0 }, {}, { totals: {}, by_source: [], best_source: "manual" });
      return;
    }

    try {
      const data = await apiGet("/leads");
      renderCrmLeads(Array.isArray(data.items) ? data.items : [], data.summary || {}, data.daily_summary || {}, data.metrics || null);
    } catch (error) {
      if (els.leadList) {
        els.leadList.innerHTML = '<div class="refund-empty">Could not load leads right now.</div>';
      }
      if (els.followupList) {
        els.followupList.innerHTML = '<div class="refund-empty">Could not load follow-ups right now.</div>';
      }
      renderCrmLeads([], { new: 0, contacted: 0, replied: 0, closed: 0, due_followups: 0 }, {}, { totals: {}, by_source: [], best_source: "manual" });
    }
  }

  async function addLeadFromWorkspace() {
    if (!state.token || !state.username) {
      setNotice("warning", "Login required", "Sign in before adding leads to the outreach queue.");
      return;
    }

    const username = (els.leadUsernameInput?.value || "").trim();
    const text = (els.leadTextInput?.value || "").trim();
    const source = (els.leadSourceInput?.value || "manual").trim();

    if (!username || !text) {
      setNotice("warning", "Lead details missing", "Add a username and the source context you want to work from.");
      return;
    }

    try {
      const data = await apiPost("/leads/add", { username, text, source });
      renderCrmLeads(Array.isArray(data.items) ? data.items : state.crmLeads, data.summary || {}, data.daily_summary || {}, data.metrics || null);
      if (els.leadUsernameInput) els.leadUsernameInput.value = "";
      if (els.leadTextInput) els.leadTextInput.value = "";
      if (els.leadSourceInput) els.leadSourceInput.value = "";
      setNotice("success", "Lead added", "The outreach queue was updated and a first-touch message is ready to copy.");
    } catch (error) {
      setNotice("error", "Lead add failed", error.message || "Could not add this lead.");
    }
  }

  async function updateLeadStatus(leadId, status) {
    if (!leadId || !status) return;

    try {
      const data = await apiPost(`/leads/${encodeURIComponent(leadId)}/status`, { status });
      renderCrmLeads(Array.isArray(data.items) ? data.items : state.crmLeads, data.summary || {}, data.daily_summary || {}, data.metrics || null);
      const notices = {
        contacted: ["success", "Lead marked sent", "A follow-up is now scheduled automatically inside your queue."],
        replied: ["success", "Lead replied", "Nice — this lead was moved forward in the CRM layer."],
        closed: ["success", "Lead closed", "The lead was moved out of the active queue."]
      };
      const [kind, title, detail] = notices[status] || ["info", "Lead updated", "Lead status updated."];
      setNotice(kind, title, detail);
    } catch (error) {
      setNotice("error", "Lead update failed", error.message || "Could not update lead status.");
    }
  }

  async function markReminderDone(leadId) {
    if (!leadId) return;
    try {
      const data = await apiPost(`/crm/reminders/${encodeURIComponent(leadId)}/done`, { days: 2 });
      renderCrmLeads(Array.isArray(data.items) ? data.items : state.crmLeads, data.summary || {}, data.daily_summary || {}, data.metrics || null);
      setNotice("success", "Reminder completed", "Follow-up was logged and the next reminder moved out." );
    } catch (error) {
      setNotice("error", "Reminder update failed", error.message || "Could not mark this reminder done.");
    }
  }

  async function snoozeReminder(leadId) {
    if (!leadId) return;
    try {
      const data = await apiPost(`/crm/reminders/${encodeURIComponent(leadId)}/snooze`, { days: 1 });
      renderCrmLeads(Array.isArray(data.items) ? data.items : state.crmLeads, data.summary || {}, data.daily_summary || {}, data.metrics || null);
      setNotice("info", "Reminder snoozed", "This follow-up was moved out by one day.");
    } catch (error) {
      setNotice("error", "Snooze failed", error.message || "Could not snooze this reminder.");
    }
  }

  async function copyLeadMessage(leadId) {
    const lead = state.crmLeads.find((item) => String(item.id) === String(leadId));
    if (!lead) return;

    try {
      await navigator.clipboard.writeText(leadMessageForStatus(lead));
      setNotice("success", "Message copied", `Outreach text for ${lead.username} is now on your clipboard.`);
    } catch (error) {
      setNotice("error", "Copy failed", "Could not copy the outreach message.");
    }
  }

function bindEvents() {
    els.sendBtn?.addEventListener("click", sendMessage);
    els.signupBtn?.addEventListener("click", signup);
    els.loginBtn?.addEventListener("click", login);
    els.logoutBtn?.addEventListener("click", logout);
    els.devBtn?.addEventListener("click", activatePreviewAccess);
    els.newChatBtn?.addEventListener("click", () => {
      resetWorkspaceThread();
      setNotice("info", "New workspace thread", "The thread was cleared. Run the next customer issue whenever you're ready.");
    });

    els.messageInput?.addEventListener("input", () => {
      autoResizeTextarea();
      saveDraft(els.messageInput.value || "");
    });


    els.usernameInput?.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        login();
      }
    });

    els.passwordInput?.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        login();
      }
    });

    els.upgradeButtons.forEach((button) => {
      button.addEventListener("mouseenter", refreshUpgradeValueSummary);
      button.addEventListener("focus", refreshUpgradeValueSummary);
      button.addEventListener("click", () => {
        upgradePlan(button.dataset.upgrade || "");
      });
    });

    els.stripeConnectBtn?.addEventListener("click", connectStripe);
    els.stripeDisconnectBtn?.addEventListener("click", disconnectStripe);
    els.openRefundModalBtn?.addEventListener("click", openRefundModal);
    els.refreshRefundHistoryBtn?.addEventListener("click", loadRefundHistory);
    els.refreshLeadsBtn?.addEventListener("click", loadCrmLeads);
    els.addLeadBtn?.addEventListener("click", addLeadFromWorkspace);
    els.leadList?.addEventListener("click", async (event) => {
      const copyBtn = event.target.closest("[data-lead-copy]");
      if (copyBtn) {
        await copyLeadMessage(copyBtn.getAttribute("data-lead-copy"));
        return;
      }

      const statusBtn = event.target.closest("[data-lead-status]");
      if (statusBtn) {
        await updateLeadStatus(
          statusBtn.getAttribute("data-lead-status"),
          statusBtn.getAttribute("data-status-value")
        );
        return;
      }

      const stageBtn = event.target.closest("[data-lead-stage]");
      if (stageBtn) {
        await updateLeadStage(stageBtn.getAttribute("data-lead-stage"), stageBtn.getAttribute("data-stage-value"));
        return;
      }

      const convertBtn = event.target.closest("[data-lead-convert]");
      if (convertBtn) {
        promptConvertLead(convertBtn.getAttribute("data-lead-convert"));
        return;
      }

      const stageSelect = event.target.closest("[data-stage-select]");
      if (stageSelect && event.target.matches("select")) {
        await updateLeadStage(stageSelect.getAttribute("data-stage-select"), event.target.value);
      }
    });
    els.followupList?.addEventListener("click", async (event) => {
      const copyBtn = event.target.closest("[data-lead-copy]");
      if (copyBtn) {
        await copyLeadMessage(copyBtn.getAttribute("data-lead-copy"));
        return;
      }

      const doneBtn = event.target.closest("[data-reminder-done]");
      if (doneBtn) {
        await markReminderDone(doneBtn.getAttribute("data-reminder-done"));
        return;
      }

      const snoozeBtn = event.target.closest("[data-reminder-snooze]");
      if (snoozeBtn) {
        await snoozeReminder(snoozeBtn.getAttribute("data-reminder-snooze"));
        return;
      }

      const statusBtn = event.target.closest("[data-lead-status]");
      if (statusBtn) {
        await updateLeadStatus(
          statusBtn.getAttribute("data-lead-status"),
          statusBtn.getAttribute("data-status-value")
        );
        return;
      }

      const stageBtn = event.target.closest("[data-lead-stage]");
      if (stageBtn) {
        await updateLeadStage(stageBtn.getAttribute("data-lead-stage"), stageBtn.getAttribute("data-stage-value"));
        return;
      }

      const convertBtn = event.target.closest("[data-lead-convert]");
      if (convertBtn) {
        promptConvertLead(convertBtn.getAttribute("data-lead-convert"));
        return;
      }

      const stageSelect = event.target.closest("[data-stage-select]");
      if (stageSelect && event.target.matches("select")) {
        await updateLeadStage(stageSelect.getAttribute("data-stage-select"), event.target.value);
      }
    });
    els.closeRefundModalBtn?.addEventListener("click", closeRefundModal);
    els.cancelRefundModalBtn?.addEventListener("click", closeRefundModal);
    els.executeRefundBtn?.addEventListener("click", executeRefundFromModal);
    els.refundModal?.addEventListener("click", (event) => {
      if (event.target === els.refundModal) closeRefundModal();
    });

    els.fillButtons.forEach((button) => {
      button.addEventListener("click", () => {
        const fill = button.dataset.fill || "";
        if (!fill || !els.messageInput) return;
        els.messageInput.value = fill;
        saveDraft(fill);
        autoResizeTextarea();
        els.messageInput.focus();
      });
    });

    els.fillButtons.forEach((btn) => {
      btn.addEventListener("dblclick", async () => {
        const label = String(btn.textContent || "").trim().toLowerCase();
        if (label === "duplicate charge") {
          await runWorkspaceRefundFromInput();
        }
      });
    });

    els.messages?.addEventListener("scroll", updateStickiness, { passive: true });

    document.addEventListener("keydown", (event) => {
      const activeTag = document.activeElement?.tagName?.toLowerCase() || "";
      const typingInField = activeTag === "textarea" || activeTag === "input";

      if (event.key === "?" && !typingInField) {
        event.preventDefault();
        toggleKeyboardOverlay(true);
        return;
      }

      if (event.key === "/" && !typingInField) {
        event.preventDefault();
        els.messageInput?.focus();
        return;
      }

      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        sendMessage();
        return;
      }

      if (!typingInField && (event.key === "n" || event.key === "N")) {
        event.preventDefault();
        resetWorkspaceThread();
        setNotice("info", "Fresh thread", "The workspace is ready for a new support run.");
        return;
      }

      if (!typingInField && (event.key === "d" || event.key === "D")) {
        event.preventDefault();
        activatePreviewAccess();
        return;
      }

      if (!typingInField && (event.key === "e" || event.key === "E")) {
        event.preventDefault();
        exportThread();
        return;
      }

      if (event.key === "Escape") {
        toggleKeyboardOverlay(false);
        closeRefundModal();
      }
    });
  }

  async function init() {
    ensureInjectedStyles();
    ensureCrmStyles();
    hydrateStripeCallbackState();
    buildKeyboardOverlay();
    ensureOpsCard();
    bindEvents();

    const draft = loadDraft();
    if (els.messageInput && draft) {
      els.messageInput.value = draft;
    }

    autoResizeTextarea();
    syncMobileViewport();
    window.addEventListener("resize", syncMobileViewport, { passive: true });
    window.visualViewport?.addEventListener("resize", syncMobileViewport, { passive: true });
    els.messageInput?.addEventListener("focus", scrollComposerIntoView);
    updateTopbarStatus();
    updatePlanUI(state.tier, state.usage, state.limit, state.remaining);
    updateSystemNarrative(null);
    updateStreamStatus("Response: ready");
    updateAuthStatus();
    updateStripeUI();
    updateRefundUI();
    renderRefundHistory([]);
    addEmptyState();
    scrollMessagesToBottom(true);
    setSending(false);

    await healthCheck();
    const meResult = await hydrateMe();
    await loadDashboardSummary();
    await loadIntegrations();
    await loadRefundHistory();
    await loadCrmLeads();
    await loadRevenueMetrics();

    if (meResult?.staleCleared) {
      setNotice(
        "warning",
        "Session reset",
        "Your saved login no longer matches an account on this server. Log in again to use billing and Stripe."
      );
    } else if (!state.username) {
      setNotice("info", "Quick demo", "Run a customer issue or create an account to keep using the workspace.");
    } else {
      setNotice("success", "Workspace synced", `Signed in as ${state.username}. The operator workspace is ready.`);
    }
  }

  function hardBindCoreComposer() {
    if (!els.sendBtn) return;

    const triggerSend = async (event) => {
      if (event) {
        event.preventDefault();
        event.stopPropagation();
      }
      try {
        await sendMessage();
      } catch (error) {
        console.error("Xalvion send failed", error);
        setNotice("error", "Send failed", error?.message || "Could not run the support request.");
      }
    };

    els.sendBtn.onclick = triggerSend;
    els.sendBtn.addEventListener("click", triggerSend, true);
    els.messageInput?.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        triggerSend(event);
      }
    }, true);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      hardBindCoreComposer();
      init();
    }, { once: true });
  } else {
    hardBindCoreComposer();
    init();
  }
})();