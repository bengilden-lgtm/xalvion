/* LIVE FRONTEND (workspace): loaded by `services/index.html` as `/app.js` (served by FastAPI in `app.py`). */
(() => {
  "use strict";

  const API = "";
  const TOKEN_KEY = "xalvion_token";
  const USER_KEY = "xalvion_user";
  const TIER_KEY = "xalvion_tier";
  const DRAFT_KEY = "xalvion_workspace_draft";
  const GUEST_USAGE_KEY = "xalvion_guest_usage";
  const GUEST_USAGE_RESET_KEY = "xalvion_guest_usage_reset_at";
  const PREVIEW_CLIENT_KEY = "xalvion_preview_client_id";
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
    accessStatePill: document.getElementById("accessStatePill"),
    accessStateTitle: document.getElementById("accessStateTitle"),
    accessStateCopy: document.getElementById("accessStateCopy"),
    accessTierValue: document.getElementById("accessTierValue"),
    accessRemainingValue: document.getElementById("accessRemainingValue"),
    accessPlansLink: document.getElementById("accessPlansLink"),
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
    workspaceSubcopy: document.getElementById("workspaceSubcopy"),
    workspaceSubcopyTier: document.getElementById("workspaceSubcopyTier"),
    dashboardCard: document.getElementById("dashboardCard"),
    usageCard: document.getElementById("usageCard"),
    accountCard: document.getElementById("accountCard"),
    paymentIntentInput: document.getElementById("paymentIntentInput"),
    chargeIdInput: document.getElementById("chargeIdInput"),
    railInner: document.getElementById("railInner") || document.querySelector(".rail-inner"),
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
    refundUpgradeTease: document.getElementById("refundUpgradeTease"),
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
    revenueCard: document.getElementById("revenueCard"),
    sourceList: document.getElementById("sourceList"),
    forecastSummary: document.getElementById("forecastSummary"),
    forecastPipelineValue: document.getElementById("forecastPipelineValue"),
    forecastWeightedRevenue: document.getElementById("forecastWeightedRevenue"),
    forecastProjectedRevenue: document.getElementById("forecastProjectedRevenue"),
    forecastCoverage: document.getElementById("forecastCoverage"),
    forecastStageList: document.getElementById("forecastStageList"),
    forecastDealList: document.getElementById("forecastDealList"),
    upgradeValueSummary: document.getElementById("upgradeValueSummary"),
    commandPlanCapacity: document.getElementById("commandPlanCapacity"),
    commandModeLine: document.getElementById("commandModeLine"),
    commandAuthChip: document.getElementById("commandAuthChip"),
    composerStatusLine: document.getElementById("composerStatusLine"),
    workspacePageTitle: document.getElementById("workspacePageTitle"),
    railRunSummary: document.getElementById("railRunSummary"),
    railValueMoney: document.getElementById("railValueMoney"),
    railValueTime: document.getElementById("railValueTime"),
    railValueActions: document.getElementById("railValueActions"),
    railSessionTier: document.getElementById("railSessionTier"),
    latestRunRailCard: document.getElementById("latestRunRailCard"),
    workspaceRoot: document.getElementById("workspaceRoot"),
    commandStrip: document.getElementById("commandStrip"),
    sidebarShell: document.getElementById("sidebarShell"),
    approvalRailWrap: document.getElementById("approvalRailWrap"),
    approvalRailSummary: document.getElementById("approvalRailSummary"),
    approvalRailMeta: document.getElementById("approvalRailMeta"),
    sidebarCrmNew: document.getElementById("sidebarCrmNew"),
    sidebarCrmDue: document.getElementById("sidebarCrmDue"),
    sidebarCrmTodayDue: document.getElementById("sidebarCrmTodayDue"),
    sidebarCrmTodayClosed: document.getElementById("sidebarCrmTodayClosed"),
    sidebarRevenueTotal: document.getElementById("sidebarRevenueTotal"),
    sidebarRevenueReply: document.getElementById("sidebarRevenueReply"),
    sidebarRevenueWin: document.getElementById("sidebarRevenueWin"),
    sidebarRevenueSource: document.getElementById("sidebarRevenueSource"),
    sidebarJumpCrmBtn: document.getElementById("sidebarJumpCrmBtn"),
    sidebarJumpRevenueBtn: document.getElementById("sidebarJumpRevenueBtn"),
    accessDrawer: document.getElementById("accessDrawer"),
    accessDrawerBody: document.getElementById("accessDrawerBody"),
    closeAccessDrawerBtn: document.getElementById("closeAccessDrawerBtn")
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
    dashboardStats: null,
    automationUpsellShown: false,
    recentTickets: [],
    lastSessionAt: Number(localStorage.getItem("xalvion-last-session-at") || 0) || 0,
    postApprovalNudgesShown: 0
  };

  function setLastSessionNow() {
    const now = Date.now();
    state.lastSessionAt = now;
    try {
      localStorage.setItem("xalvion-last-session-at", String(now));
    } catch {}
  }

  function effectiveTicketCount() {
    if (!isAuthenticated()) return Math.max(0, getGuestUsage());
    const vs = state.valueSignals;
    const fromSignals = vs && typeof vs.tickets_handled === "number" ? Number(vs.tickets_handled) : NaN;
    if (Number.isFinite(fromSignals) && fromSignals >= 0) return Math.floor(fromSignals);
    return Math.max(0, Number(state.usage || 0) || 0);
  }

  function momentumLine() {
    const n = effectiveTicketCount();
    if (n <= 0) return "";
    if (n === 1) return "You’ve resolved 1 issue with Xalvion.";
    if (n <= 3) return "You’re speeding up your workflow.";
    if (n <= 5) return "You’re saving time on support already.";
    return `You’ve handled ${n} tickets with Xalvion.`;
  }

  function estimateTimeSavedMinutes() {
    // Conservative heuristic. We also read real server metrics when available elsewhere.
    const n = effectiveTicketCount();
    return Math.max(0, Math.round(n * 3));
  }

  async function fetchRecentTickets(limit = 5) {
    try {
      const res = await fetch(`${API}/tickets/recent?limit=${encodeURIComponent(String(limit))}`, {
        method: "GET",
        headers: headers(),
      });
      if (!res.ok) return [];
      const data = await res.json().catch(() => ({}));
      const items = Array.isArray(data?.items) ? data.items : Array.isArray(data?.tickets) ? data.tickets : [];
      return items.filter((t) => t && typeof t === "object").slice(0, limit);
    } catch {
      return [];
    }
  }

  function setRecentTickets(items) {
    state.recentTickets = Array.isArray(items) ? items.slice(0, 5) : [];
    try {
      const slim = state.recentTickets.map((t) => ({
        id: t.id,
        updated_at: t.updated_at,
        issue_type: t.issue_type,
        queue: t.queue,
        status: t.status,
        subject: t.subject,
        customer_message: typeof t.customer_message === "string" ? t.customer_message.slice(0, 220) : "",
      }));
      localStorage.setItem("xalvion-recent-tickets", JSON.stringify(slim));
    } catch {}
  }

  function loadRecentTicketsFromCache() {
    try {
      const raw = localStorage.getItem("xalvion-recent-tickets");
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed.slice(0, 5) : [];
    } catch {
      return [];
    }
  }

  async function hydrateRecentTickets() {
    // Render immediately from cache, then refresh from server.
    const cached = loadRecentTicketsFromCache();
    if (cached.length) {
      state.recentTickets = cached;
      refreshEmptyStateContent();
    }
    const items = await fetchRecentTickets(5);
    if (items.length) {
      setRecentTickets(items);
      refreshEmptyStateContent();
    }
  }

  function getPhase2() {
    return typeof globalThis !== "undefined" ? globalThis.__XALVION_PHASE2__ : null;
  }

  function phase2WorkspaceReady() {
    const p2 = getPhase2();
    return Boolean(p2 && p2.sessionStore && p2.agentStore && p2.ready !== false);
  }

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
    xalvionX: `
      <svg viewBox="0 0 16 16" aria-hidden="true">
        <path d="M3.2 3.2h2.1L8 6.1l2.7-2.9h2.1L9.9 8l2.9 4.8h-2.1L8 9.9l-2.7 2.9H3.2L6.1 8 3.2 3.2Z" fill="currentColor"></path>
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
    // In Claude-mode we keep the bulk of styling in `styles.css`, but we still
    // allow a small, surgical runtime override for spacing/rail/composer rhythm.
    // This avoids architecture changes while letting us refine the merged UI.
    try {
      if (document?.body?.dataset?.ui === "claude") {
        if (!document.getElementById("xalvion-claude-tweaks")) {
          const claudeStyle = document.createElement("style");
          claudeStyle.id = "xalvion-claude-tweaks";
          claudeStyle.textContent = `
            /* Xalvion surgical merge: Claude-style rhythm refinements — keep sidebar metrics in styles.css */
            body[data-ui="claude"]{
              --cld-sidebar-expanded: 248px;
              --cld-sidebar-collapsed: 52px;
              --cld-thread-max: min(720px, 92vw);
              --cld-open-composer: min(720px, 92vw);
            }

            body[data-ui="claude"] #sidebarShell{
              background: var(--surface) !important;
              border-right-color: var(--border) !important;
            }
            body[data-ui="claude"] .sidebar-collapse-btn{
              width: 38px !important;
              height: 38px !important;
              border-radius: 12px !important;
              background: rgba(255,255,255,0.035) !important;
              border-color: rgba(255,255,255,0.075) !important;
            }
            body[data-ui="claude"] .sidebar-nav-icon{
              width: 18px !important;
              min-width: 18px !important;
              height: 18px !important;
              font-size: 15px !important;
            }

            /* Cleaner workspace shell: slightly more editorial center column */
            body[data-ui="claude"] .main-canvas-inner.main-stage{
              padding: clamp(10px, 2vh, 18px) clamp(12px, 2.5vw, 22px) 8px !important;
            }
            body[data-ui="claude"] #messages{
              padding: 6px 0 56px !important;
              gap: 12px !important;
            }

            /* Flatter conversation flow; reduce visual “card” energy */
            body[data-ui="claude"] .msg-group .reply-body{
              padding-left: 12px !important;
            }
            body[data-ui="claude"] .msg-group .reply-body::before{
              width: 2px !important;
              opacity: 0.9 !important;
            }
            body[data-ui="claude"] .assistant-footer{
              padding-top: 8px !important;
            }
            body[data-ui="claude"] .msg-actions{
              padding: 12px 0 0 14px !important;
              gap: 6px !important;
              opacity: 0.62 !important;
            }
            body[data-ui="claude"] .msg-group:hover .msg-actions,
            body[data-ui="claude"] .msg-group:focus-within .msg-actions,
            body[data-ui="claude"] .msg-group.assistant.show-actions .msg-actions{
              opacity: 0.92 !important;
            }
            body[data-ui="claude"] .act-btn{
              height: 28px !important;
              padding: 0 9px !important;
              border-radius: 9px !important;
            }

            /* Composer: do not re-box here. This tag is appended after styles.css and
               previously used !important to override the flattened chat-first composer. */
            body[data-ui="claude"] #workspaceRoot .composer-wrap.composer-dock{
              max-width: var(--cld-thread-max) !important;
              margin-left: auto !important;
              margin-right: auto !important;
              padding-left: 0 !important;
              padding-right: 0 !important;
            }
          `;
          document.head.appendChild(claudeStyle);
        }
        return;
      }
    } catch {}
    if (document.getElementById("xalvion-runtime-styles")) return;

    const style = document.createElement("style");
    style.id = "xalvion-runtime-styles";
    style.textContent = `
      :root {
        --xv-bg-0: #0c0f1c;
        --xv-bg-1: #12162a;
        --xv-bg-2: #181d35;
        --xv-surface: rgba(26, 30, 54, 0.34);
        --xv-surface-soft: rgba(22, 25, 44, 0.22);
        --xv-surface-strong: rgba(28, 32, 54, 0.60);
        --xv-line: rgba(144, 126, 255, 0.10);
        --xv-line-soft: rgba(255, 255, 255, 0.04);
        --xv-text: rgba(244, 246, 255, 0.96);
        --xv-text-soft: rgba(194, 201, 225, 0.78);
        --xv-text-dim: rgba(150, 160, 192, 0.58);
        --xv-purple: #8d6cff;
        --xv-purple-soft: rgba(141, 108, 255, 0.18);
        --xv-panel-radius: 18px;
        --xv-panel-shadow: 0 10px 28px rgba(4, 5, 12, 0.14);
        --xv-focus: rgba(141, 108, 255, 0.20);
      }

      html, body {
        background:
          radial-gradient(900px 520px at 50% -120px, rgba(141, 108, 255, 0.16), transparent 60%),
          radial-gradient(1200px 640px at 10% 0%, rgba(99, 102, 241, 0.10), transparent 62%),
          linear-gradient(180deg, #0b0e1a 0%, #0d1226 100%) !important;
        color: var(--xv-text);
      }

      body {
        -webkit-font-smoothing: antialiased;
        text-rendering: optimizeLegibility;
      }

      #workspaceRoot {
        background: transparent !important;
      }

      #sidebarShell {
        background: linear-gradient(180deg, rgba(14, 18, 38, 0.82), rgba(10, 13, 30, 0.72)) !important;
        border-right: 1px solid rgba(255,255,255,0.045) !important;
        box-shadow: inset -1px 0 0 rgba(255,255,255,0.018);
      }

      #sidebarShell [data-sidebar-tab] {
        min-height: 40px;
        border-radius: 14px;
        padding: 0 12px;
        font-size: 14px;
        font-weight: 600;
        letter-spacing: -0.01em;
      }

      #sidebarShell [data-sidebar-tab].is-active,
      #sidebarShell [data-sidebar-tab][aria-selected="true"] {
        background: linear-gradient(90deg, rgba(141,108,255,0.14), rgba(80, 92, 180, 0.07)) !important;
        border: 1px solid rgba(141,108,255,0.30) !important;
        color: rgba(249, 250, 255, 0.98) !important;
        box-shadow: inset 0 0 0 1px rgba(255,255,255,0.02);
      }

      #sidebarShell [data-sidebar-panel] {
        color: var(--xv-text-soft);
      }

      #sidebarShell .sidebar-section-eyebrow,
      #sidebarShell .sidebar-eyebrow,
      #sidebarShell h6,
      #sidebarShell .label,
      #sidebarShell .section-kicker {
        font-size: 11px !important;
        letter-spacing: 0.14em !important;
        text-transform: uppercase;
        color: rgba(144, 126, 255, 0.6) !important;
      }

      #sidebarShell .sidebar-card,
      #sidebarShell .sidebar-snapshot,
      #sidebarShell .sidebar-panel-card,
      #sidebarShell .sidebar-box,
      #sidebarShell .account-card,
      #sidebarShell .auth-card {
        background: rgba(255,255,255,0.030) !important;
        border: 1px solid rgba(255,255,255,0.042) !important;
        border-radius: 16px !important;
        box-shadow: none !important;
      }

      #sidebarShell .account-card,
      #sidebarShell .auth-card {
        padding: 16px !important;
      }

      #sidebarShell input,
      #sidebarShell .auth-input,
      #sidebarShell textarea {
        min-height: 44px;
        border-radius: 13px !important;
        background: rgba(255,255,255,0.042) !important;
        border: 1px solid rgba(255,255,255,0.072) !important;
        color: var(--xv-text) !important;
        font-size: 14.5px !important;
      }

      #sidebarShell input:focus,
      #sidebarShell textarea:focus {
        outline: none !important;
        border-color: rgba(141,108,255,0.34) !important;
        box-shadow: 0 0 0 4px rgba(141,108,255,0.12);
      }

      #sidebarShell .auth-helper,
      #sidebarShell small,
      #sidebarShell .muted,
      #sidebarShell .sidebar-copy {
        font-size: 12px !important;
        line-height: 1.55 !important;
        color: var(--xv-text-dim) !important;
      }

      #sidebarShell .sidebar-link-row,
      #sidebarShell .sidebar-meta-row {
        gap: 8px !important;
      }

      #sidebarShell #signupBtn,
      #sidebarShell #loginBtn,
      #sidebarShell #logoutBtn,
      #sidebarShell .btn,
      #sidebarShell button {
        border-radius: 14px;
      }

      #messagesShell,
      .messages-shell,
      .scroll-shell,
      .thread-shell,
      .conversation-shell,
      .messages-zone {
        background: linear-gradient(180deg, rgba(30, 34, 58, 0.20), rgba(14, 18, 34, 0.16)) !important;
        border: 1px solid rgba(255,255,255,0.038) !important;
        border-radius: 18px !important;
        box-shadow: none !important;
        backdrop-filter: none !important;
      }

      #messages {
        display: flex;
        flex-direction: column;
        gap: 16px;
        padding: 24px 24px 120px;
        max-width: 1120px;
        margin: 0 auto;
        background: transparent !important;
      }

      .msg-group {
        display: block;
      }

      .msg-card {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        border-radius: 0 !important;
        padding: 0 !important;
      }

      .msg-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        padding: 0 0 12px;
        margin-bottom: 10px;
        border-bottom: 1px solid rgba(255,255,255,0.045);
      }

      .msg-who {
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: rgba(176, 184, 208, 0.76);
      }

      .msg-time {
        font-size: 12px;
        color: rgba(138, 146, 173, 0.6);
      }

      .msg-body,
      .assistant-canvas,
      .assistant-result-stack,
      .assistant-decision-slot,
      .assistant-brief-slot,
      .stream-trace-host,
      .customer-message-block {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        backdrop-filter: none !important;
      }

      .reply-hero-label {
        display: none !important;
      }

      .reply-value-reinforcement {
        display: block;
        margin: 0 0 12px;
        font-size: 13px;
        font-weight: 600;
        color: rgba(190, 197, 222, 0.8);
      }

      .msg-group.user .reply-text {
        display: block;
        padding: 16px 18px;
        border-radius: 16px;
        background: rgba(255,255,255,0.042);
        border: 1px solid rgba(255,255,255,0.055);
        box-shadow: none;
      }

      .msg-group.assistant .reply-text {
        display: block;
        padding: 0;
        background: transparent !important;
        border: none !important;
        color: var(--xv-text);
      }

      .reply-text {
        font-size: 17px;
        line-height: 1.72;
        letter-spacing: -0.01em;
        color: var(--xv-text);
        max-width: 900px;
      }

      .assistant-context-line {
        margin: 0 0 10px;
        font-size: 13px;
        color: rgba(194, 201, 225, 0.72);
      }

      .assistant-footer {
        margin-top: 16px;
        padding: 12px 14px;
        border-radius: 14px;
        background: rgba(255,255,255,0.018);
        border: 1px solid rgba(255,255,255,0.045);
      }

      .assistant-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }

      .meta-chip {
        min-height: 30px;
        padding: 0 10px;
        border-radius: 999px;
        border: 1px solid rgba(255,255,255,0.062);
        background: rgba(255,255,255,0.028);
        color: rgba(222, 228, 246, 0.82);
        font-size: 12px;
        font-weight: 600;
      }

      .meta-chip.safe { background: rgba(52,211,153,0.08); border-color: rgba(52,211,153,0.18); }
      .meta-chip.review { background: rgba(250,204,21,0.08); border-color: rgba(250,204,21,0.18); }
      .meta-chip.risk, .meta-chip.error { background: rgba(248,113,113,0.08); border-color: rgba(248,113,113,0.18); }

      .empty-state {
        display: flex;
        justify-content: center;
        padding: 8px 0 24px;
      }

      .empty-card {
        width: min(100%, 700px);
        margin: 0 auto;
        padding: 20px 20px;
        border-radius: 18px;
        background: linear-gradient(180deg, rgba(18,22,44,0.46), rgba(10, 13, 28, 0.40));
        border: 1px solid rgba(255,255,255,0.048);
        box-shadow: 0 8px 18px rgba(3, 5, 12, 0.12);
      }

      .empty-card h2,
      .empty-launch-outcome {
        font-size: 30px;
        line-height: 1.12;
        font-weight: 700;
        letter-spacing: -0.03em;
        color: rgba(248, 249, 255, 0.98);
      }

      .empty-launch-directive,
      .empty-cap-eyebrow {
        margin-bottom: 10px;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: rgba(161, 144, 255, 0.82);
      }

      .empty-launch-review,
      .limit-moment-lead,
      .empty-card p {
        font-size: 16px;
        line-height: 1.7;
        color: rgba(210, 218, 242, 0.86);
      }

      .empty-flow-strip,
      .empty-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 18px;
      }

      .empty-flow-strip span,
      .empty-chip-hint,
      .empty-chip-hint-secondary {
        padding: 9px 12px;
        border-radius: 999px;
        background: rgba(255,255,255,0.028);
        border: 1px solid rgba(255,255,255,0.05);
        font-size: 13px;
        color: rgba(210, 218, 242, 0.78);
      }

      .limit-cta,
      #emptySignupCta {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 50px;
        padding: 0 20px;
        margin-top: 18px;
        border: none;
        border-radius: 14px;
        background: linear-gradient(135deg, #8d6cff, #6f58ff);
        color: #fff;
        font-size: 16px;
        font-weight: 700;
        cursor: pointer;
        box-shadow: 0 10px 22px rgba(111, 88, 255, 0.22);
      }

      .limit-secondary-link,
      #emptyLoginLink {
        display: inline-flex;
        margin-top: 14px;
        background: transparent;
        border: none;
        color: rgba(214, 220, 244, 0.84);
        text-decoration: underline;
        cursor: pointer;
        font-size: 14px;
      }

      .composer,
      .composer-chat,
      .input-wrap,
      .composer-shell {
        background: rgba(255,255,255,0.030) !important;
        border: 1px solid rgba(255,255,255,0.045) !important;
        border-radius: 18px !important;
        box-shadow: none !important;
      }

      .composer,
      .composer-chat,
      .composer-shell {
        padding: 10px !important;
      }

      textarea,
      #messageInput,
      .message-input {
        min-height: 56px;
        padding: 12px 12px !important;
        background: rgba(255,255,255,0.040) !important;
        border: 1px solid rgba(255,255,255,0.052) !important;
        border-radius: 15px !important;
        color: var(--xv-text) !important;
        font-size: 16px !important;
      }

      textarea::placeholder,
      #messageInput::placeholder,
      .message-input::placeholder {
        color: rgba(210, 218, 242, 0.62) !important;
      }

      .composer-input-row,
      .composer-input-wrap {
        gap: 10px !important;
        align-items: flex-end !important;
      }

      .composer .quick-actions {
        gap: 8px !important;
      }

      .composer .chip {
        padding: 8px 10px !important;
        border-radius: 999px !important;
        background: rgba(255,255,255,0.028) !important;
        border: 1px solid rgba(255,255,255,0.05) !important;
        color: rgba(222, 228, 246, 0.86) !important;
        font-size: 12.5px !important;
        font-weight: 650 !important;
      }

      .composer .chip:hover {
        background: rgba(141,108,255,0.10) !important;
        border-color: rgba(141,108,255,0.18) !important;
        transform: translateY(-1px);
      }

      textarea:focus,
      #messageInput:focus,
      .message-input:focus {
        outline: none !important;
        border-color: rgba(141,108,255,0.26) !important;
        box-shadow: 0 0 0 4px rgba(141,108,255,0.10);
      }

      #sendBtn,
      .send-btn {
        width: 44px;
        height: 44px;
        border-radius: 13px !important;
        background: linear-gradient(135deg, #8d6cff, #6f58ff) !important;
        border: none !important;
        box-shadow: 0 8px 18px rgba(111, 88, 255, 0.18) !important;
      }

      @media (max-width: 1200px) {
        #messages {
          padding: 24px 20px 120px;
        }
        .empty-card {
          width: 100%;
          padding: 20px;
        }
        .reply-text {
          font-size: 16px;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function ensureCrmStyles() {
    if (document.getElementById("xalvion-crm-styles")) return;
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

  function ensurePreviewClientId() {
    try {
      let id = localStorage.getItem(PREVIEW_CLIENT_KEY);
      if (id && id.length >= 8) return id;
      id =
        (globalThis.crypto && typeof globalThis.crypto.randomUUID === "function" && globalThis.crypto.randomUUID()) ||
        `pv_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 12)}`;
      localStorage.setItem(PREVIEW_CLIENT_KEY, id);
      return id;
    } catch {
      return "";
    }
  }

  function syncGuestEntitlementFromServerPayload(payload) {
    if (!payload || isAuthenticated()) return;
    const u = Number(payload.usage);
    if (Number.isFinite(u)) setGuestUsage(u);
    const lim = Number(payload.limit || payload.plan_limit || GUEST_USAGE_LIMIT);
    const safeLim = Number.isFinite(lim) && lim > 0 ? lim : GUEST_USAGE_LIMIT;
    const rem = Number.isFinite(Number(payload.remaining))
      ? Math.max(0, Number(payload.remaining))
      : Math.max(0, safeLim - getGuestUsage());
    updatePlanUI("free", getGuestUsage(), safeLim, rem);
    applyComposerInteractiveLock();
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
        title: "Preview limit reached — continue in operator mode",
        detail: `You can keep working. Create a free account for ${FREE_USAGE_LIMIT} included runs/month, saved threads, and a persistent operator workspace.`,
        body: `You’ve reached the preview run allowance.

You can continue using the workspace — additional usage is tracked. Create a free account for ${FREE_USAGE_LIMIT} included runs/month, saved threads, and a stable workflow for support teams.`
      };
    }

    const tier = String(state.tier || "free").toLowerCase();
    const vs = state.valueSignals;
    const d = state.dashboardStats || {};
    const vg = d.value_generated && typeof d.value_generated === "object" ? d.value_generated : null;
    const money = Number((vg && vg.money_saved) ?? d.money_saved ?? 0);
    const actions = Number((vg && vg.actions_taken) ?? d.actions ?? 0);
    const valuePrefix =
      tier === "free" && vs && typeof vs.tickets_handled === "number" && vs.tickets_handled > 0
        ? `${vs.tickets_handled} tickets on your plan this cycle${money > 0 ? ` · ${formatMoney(money)} surfaced in billing actions` : ""}${actions > 0 ? ` · ${actions} motions logged` : ""}. `
        : tier === "free" && money > 0
          ? `${formatMoney(money)} already moved through workspace billing actions. `
          : tier === "pro" && money > 0
            ? `${formatMoney(money)} through billing actions on this workspace — you’re clearly at operating depth. `
            : "";

    if (tier === "pro") {
      return {
        key: `pro-${getEffectiveUsage(state.usage)}`,
        title: "Plan limit reached — additional usage will be billed",
        detail: `${valuePrefix}Keep working. Upgrade to Elite for higher included capacity (5,000 runs/month) and more automation headroom.`,
        body: `${valuePrefix}You’ve reached your included Pro capacity.

You can continue running tickets — additional usage will be billed. Elite adds higher included runs, deeper analytics, and room to scale without another ceiling mid-shift.`
      };
    }

    return {
      key: `free-${getEffectiveUsage(state.usage)}`,
      title: "Plan limit reached — additional usage will be billed",
      detail: `${valuePrefix}Keep working. Upgrade to Pro for higher included capacity (500 runs/month) plus automation and integrations.`,
      body: `${valuePrefix}You’ve reached your included Free capacity.

You can continue running tickets — additional usage will be billed. Pro keeps the operator loop running with more included runs, live Stripe execution, and integration access for support teams.`
    };
  }

  function pushLimitMessage(force = false) {
    const { key, title, detail, body } = getLimitMessageConfig();
    if (!force && state.lastLimitNoticeKey === key) return;
    state.lastLimitNoticeKey = key;

    if (!isAuthenticated()) setNotice("info", title, detail, { continuation: true });
    else setNotice("warning", title, detail);

    const banner = document.getElementById("inlineLimitBanner");
    if (banner) {
      const used = getEffectiveUsage(state.usage);
      const lim = getEffectiveLimit(state.tier, state.limit);
      const billable = Math.max(0, Number(state.billableUsage || 0) || 0);
      const within = lim >= 1e9 ? used : Math.min(used, lim);
      const usageLine = billable > 0 ? `${within} / ${lim} included · ${billable} billable` : `${used} / ${lim} runs used`;
      const primaryLabel = isAuthenticated() ? "Upgrade" : "Create free account";
      const secondaryLabel = isAuthenticated() ? "See plans" : "Log in";
      const eyebrow = !isAuthenticated() ? "Preview" : "Capacity";
      banner.innerHTML = `
        <div class="inline-limit-eyebrow">${escapeHtml(eyebrow)}</div>
        <div class="inline-limit-title">${escapeHtml(title)}</div>
        <div class="inline-limit-detail">${escapeHtml(detail)}</div>
        <div class="inline-limit-actions">
          <button type="button" class="btn inline-limit-primary" id="inlineLimitPrimary">${escapeHtml(primaryLabel)}</button>
          <button type="button" class="ghost-btn inline-limit-secondary" id="inlineLimitSecondary">${escapeHtml(secondaryLabel)}</button>
          <span class="muted-copy inline-limit-usage">${escapeHtml(usageLine)}</span>
        </div>
      `;
      banner.hidden = false;

      const primary = document.getElementById("inlineLimitPrimary");
      const secondary = document.getElementById("inlineLimitSecondary");
      primary?.addEventListener(
        "click",
        () => {
          if (!isAuthenticated()) {
            focusAccessPanel();
            return;
          }
          const t = String(state.tier || "free").toLowerCase();
          if (t === "pro") upgradePlan("elite");
          else upgradePlan("pro");
        },
        { once: true }
      );
      secondary?.addEventListener(
        "click",
        () => {
          if (!isAuthenticated()) focusAccessPanel();
          else focusPlansPanel();
        },
        { once: true }
      );
    }
  }

  function enforceWorkspaceLimit() {
    const limit = getEffectiveLimit(state.tier, state.limit);
    const usage = getEffectiveUsage(state.usage);

    if (usage < limit) return true;

    // Soft limit: never hard-block. Keep operating, but surface billable overage.
    state.atLimit = true;
    updatePlanUI(state.tier, usage, limit, Math.max(0, limit - usage));
    pulseRail("usage");
    pushLimitMessage();
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
    else {
      const gid = ensurePreviewClientId();
      if (gid) out["X-Xalvion-Guest-Client"] = gid;
    }
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
    if (d && typeof d === "object" && !Array.isArray(d)) {
      if (typeof d.message === "string") return d.message;
    }
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
    const code = String(data.code || (data.tool_result && data.tool_result.code) || "").toLowerCase();
    return (
      mode === "error"
      || mode === "timeout"
      || mode === "preview_blocked"
      || reason === "stream_error"
      || reason === "stream_timeout"
      || reason === "preview_exhausted"
      || tool === "error"
      || tool === "timeout"
      || tool === "preview_blocked"
      || code === "preview_exhausted"
    );
  }

  function isPreviewExhaustedPayload(data) {
    if (!data || typeof data !== "object") return false;
    const code = String(data.code || "").toLowerCase();
    const tool = String(data.tool_status || "").toLowerCase();
    return code === "preview_exhausted" || tool === "preview_blocked";
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

    const p2 = getPhase2();
    let delegated = false;
    if (phase2WorkspaceReady() && p2?.stripeEngine?.renderRefundHistory) {
      try {
        p2.stripeEngine.renderRefundHistory(els, state.refundHistory, {
          formatMoney,
          escapeHtml,
          formatRefundTimestamp,
          refundStatusTone,
          setText,
        });
        delegated = true;
      } catch {
        delegated = false;
      }
    }

    if (!delegated) {
      if (els.refundHistoryCount) {
        setText(els.refundHistoryCount, String(state.refundHistory.length));
      }

      if (!els.refundHistoryList) {
        syncPhase2Stores();
        return;
      }

      if (!state.refundHistory.length) {
        els.refundHistoryList.innerHTML =
          '<div class="refund-empty">No refund activity yet. Refunds will appear here with status and timestamp.</div>';
        syncPhase2Stores();
        return;
      }

      els.refundHistoryList.innerHTML = state.refundHistory
        .map((log) => {
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
        })
        .join("");
    }

    syncPhase2Stores();
  }

  function updateRefundUI() {
    const p2 = getPhase2();
    let delegated = false;
    if (phase2WorkspaceReady() && p2?.stripeEngine?.updateRefundCenterPanel) {
      try {
        p2.stripeEngine.updateRefundCenterPanel(
          els,
          { tier: state.tier, dashboardStats: state.dashboardStats },
          { canUseRefundCenter, formatMoney, setText }
        );
        delegated = true;
      } catch {
        delegated = false;
      }
    }

    if (!delegated) {
      const allowed = canUseRefundCenter();

      if (els.refundTierAccess) {
        setText(els.refundTierAccess, allowed ? "Ready" : "");
      }

      if (els.refundCenterCard) {
        els.refundCenterCard.classList.toggle("refund-disabled", !allowed);
      }

      if (els.openRefundModalBtn) {
        els.openRefundModalBtn.disabled = !allowed;
        els.openRefundModalBtn.textContent = allowed ? "Open refund UI" : "Upgrade to unlock";
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
          : "You’re seeing decisions and approvals on Free — Pro unlocks one-click refund execution against Stripe without leaving this surface.";
      }
      if (els.refundUpgradeTease) {
        const d = state.dashboardStats || {};
        const vg = d.value_generated && typeof d.value_generated === "object" ? d.value_generated : null;
        const money = Number((vg && vg.money_saved) ?? d.money_saved ?? 0);
        const actions = Number((vg && vg.actions_taken) ?? d.actions ?? 0);
        els.refundUpgradeTease.textContent = allowed
          ? "Execute refunds from the workspace · Available on Pro and Elite"
          : money > 0 || actions > 0
            ? `Your workspace already logged ${formatMoney(money)} across ${actions} billing motions — Pro turns that into live Stripe execution here.`
            : "Close the loop on Free → Pro: run real refunds from the workspace with Stripe connected — no console, no context switch.";
      }
    }

    syncMonetizationChrome();
    syncPhase2Stores();
  }

  function openRefundModal() {
    updateRefundUI();
    if (!canUseRefundCenter()) {
      setNotice(
        "warning",
        "Refund center is a Pro unlock",
        "You’re already using the operator canvas on Free — upgrade to run refunds against Stripe without leaving the workspace."
      );
      return;
    }
    try {
      getPhase2()?.uiStore?.set?.({ modalOpen: "refund" });
    } catch {
      /* no-op */
    }
    if (els.refundModal) {
      els.refundModal.classList.add("open");
      els.refundModal.setAttribute("aria-hidden", "false");
    }
  }

  function closeRefundModal() {
    try {
      getPhase2()?.uiStore?.set?.({ modalOpen: null });
    } catch {
      /* no-op */
    }
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
      setNotice(
        "warning",
        "Refund center is a Pro unlock",
        "You’re already using the operator canvas on Free — upgrade to run refunds against Stripe without leaving the workspace."
      );
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
    const p2 = getPhase2();
    let delegated = false;
    if (phase2WorkspaceReady() && p2?.stripeEngine?.updateStripePanel) {
      try {
        p2.stripeEngine.updateStripePanel(els, {
          stripeConnected: state.stripeConnected,
          stripeAccountId: state.stripeAccountId,
          stripeMode: state.stripeMode,
        });
        delegated = true;
      } catch {
        delegated = false;
      }
    }

    if (!delegated) {
      const connected = Boolean(state.stripeConnected);
      const authed = Boolean(state.token && state.username);

      if (els.stripeStatus) {
        els.stripeStatus.textContent = connected ? "Connected" : "Not connected";
        els.stripeStatus.classList.toggle("is-connected", connected);
      }

      if (els.stripeConnectBtn) {
        const label = els.stripeConnectBtn.querySelector(".stripe-connect-label");
        let connectLabel = connected ? "Reconnect Stripe" : "Connect Stripe";
        if (!authed) connectLabel = "Sign in to connect Stripe";
        if (label) {
          label.textContent = connectLabel;
        } else {
          els.stripeConnectBtn.textContent = connectLabel;
        }
        els.stripeConnectBtn.disabled = false;
        els.stripeConnectBtn.classList.toggle("stripe-connect-btn--needs-auth", !authed && !connected);
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

    syncPhase2Stores();
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
      focusAccessPanel();
      setNotice(
        "warning",
        "Sign in to connect Stripe",
        "Open Access in the sidebar, create an account or log in, then return to Integrations to connect Stripe."
      );
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
    const p2 = getPhase2();
    if (phase2WorkspaceReady() && p2?.stripeEngine?.hydrateStripeCallbackState) {
      try {
        p2.stripeEngine.hydrateStripeCallbackState(window, { setNotice });
        return;
      } catch {
        /* fall through */
      }
    }
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

  function setNotice(kind, title, detail, opts) {
    if (!els.notice) return;
    els.notice.classList.remove("success", "warning", "error", "info", "notice-continuation");
    els.notice.classList.add(kind || "info");
    if (opts && opts.continuation) els.notice.classList.add("notice-continuation");
    setText(els.noticeTitle, title);
    setText(els.noticeDetail, detail);
  }

  function updateBackendStatus(ok) {
    setText(els.backendStatus, ok ? "Service: online" : "Service: offline");
  }

  function updateAuthStatus() {
    if (state.username) setText(els.authStatus, `Session: ${state.username}`);
    else setText(els.authStatus, "Session: guest");
    syncAccessOverview();
  }

  function syncAccessOverview() {
    const guest = !isAuthenticated();
    const tier = formatTier(state.tier || "free");
    const remaining = Number.isFinite(Number(state.remaining)) ? Number(state.remaining) : 0;

    if (els.accessTierValue) setText(els.accessTierValue, tier);
    if (els.accessRemainingValue) {
      const label = guest ? `${remaining} preview ${remaining === 1 ? "run" : "runs"}` : `${remaining} runs`;
      setText(els.accessRemainingValue, label);
    }

    if (els.accessStateTitle) {
      setText(els.accessStateTitle, guest ? "Guest session" : `Signed in as ${state.username}`);
    }
    if (els.accessStateCopy) {
      els.accessStateCopy.textContent = guest
        ? "Create a free account to keep threads, get monthly runs, and continue with the same approval-safe workflow."
        : "Your workspace keeps saved threads, usage, and gated actions under your plan.";
    }

    if (els.accessStatePill) {
      els.accessStatePill.classList.toggle("is-guest", guest);
      els.accessStatePill.classList.toggle("is-signed-in", !guest);
      setText(els.accessStatePill, guest ? "GUEST" : "SIGNED IN");
    }
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
    syncAccessOverview();
    updateRefundUI();
    persistAuth();
    syncUsageApproachNotice();
    syncCommandStripCapacity();
    refreshEmptyStateContent();
    if (!state.sending) refreshComposerIdleHint();
    applyComposerInteractiveLock();
    syncPlansPanelChrome();

    const banner = document.getElementById("inlineLimitBanner");
    if (banner) {
      const guest = !isAuthenticated();
      const atCap = guest ? state.remaining <= 0 : Boolean(state.atLimit);
      if (!atCap) {
        banner.hidden = true;
        banner.innerHTML = "";
      }
    }
  }

  function syncMonetizationChrome() {
    const root = els.workspaceRoot;
    const strip = els.commandStrip;
    const cap = els.commandPlanCapacity;
    const guest = !isAuthenticated();
    const pct = state.limit > 0 ? state.usage / state.limit : 0;
    const approaching =
      guest
        ? pct >= 0.75 && state.remaining > 0
        : (state.approachingLimit || pct >= 0.75) && !state.atLimit && state.remaining > 0;
    const atCap = guest ? state.remaining <= 0 : Boolean(state.atLimit);
    const tier = String(state.tier || "free").toLowerCase();
    let lockedPremium = false;
    try {
      lockedPremium = !canUseRefundCenter();
    } catch {
      lockedPremium = true;
    }

    const surfaces = [root, strip, cap, els.usageCard].filter(Boolean);
    surfaces.forEach((el) => {
      el.classList.toggle("mono-guest-preview", guest);
      el.classList.toggle("mono-approaching-limit", approaching && !atCap);
      el.classList.toggle("mono-at-limit", atCap);
      el.classList.toggle("mono-locked-premium-surface", lockedPremium && tier === "free");
    });
    if (root) {
      root.classList.toggle("mono-tier-pro", tier === "pro");
      root.classList.toggle("mono-tier-elite", tier === "elite" || tier === "dev");
    }
    els.commandAuthChip?.classList.toggle("is-guest-chip", guest);
  }

  function syncPlansPanelChrome() {
    const stack = document.getElementById("plansSurfaceGrid") || document.getElementById("plansStack");
    if (!stack) return;
    const authed = isAuthenticated();
    const tier = String(state.tier || "free").toLowerCase();
    const topTier = tier === "elite" || tier === "dev";

    stack.querySelectorAll(".plan-offer").forEach((el) => {
      const offerTier = String(el.dataset.planTier || "").toLowerCase();
      const onThisPlan = authed && offerTier === tier;
      el.classList.toggle("is-current", Boolean(onThisPlan));
      el.classList.toggle("is-locked-preview", !authed && offerTier !== "preview");
      const badge = el.querySelector("[data-plan-badge]");
      if (badge) badge.hidden = !onThisPlan;
    });

    stack.querySelectorAll("[data-upgrade]").forEach((btn) => {
      if (!(btn instanceof HTMLButtonElement)) return;
      const t = String(btn.dataset.upgrade || "").toLowerCase();
      let hide = false;
      if (topTier) {
        hide = true;
      } else if (tier === "pro") {
        hide = t === "pro";
      }
      btn.hidden = hide;
      btn.disabled = false;
    });
  }

  function syncCommandStripCapacity() {
    const el = els.commandPlanCapacity;
    if (el) {
      el.classList.remove("is-warning", "is-limit");
      const pct = state.limit > 0 ? state.usage / state.limit : 0;
      const tierLabel = isAuthenticated() ? formatTier(state.tier) : "Free";
      const used = Math.max(0, Number(state.usage || 0) || 0);
      const cap = Math.max(0, Number(state.limit || 0) || 0);
      const runWord = used === 1 ? "run" : "runs";
      const nextText = `${tierLabel}: ${used} / ${cap} ${runWord} used`;
      const prevText = el.textContent || "";
      if (prevText && prevText !== nextText) {
        el.classList.add("xv-swap");
        window.setTimeout(() => {
          el.textContent = nextText;
          window.setTimeout(() => el.classList.remove("xv-swap"), 140);
        }, 80);
      } else {
        el.textContent = nextText;
      }
      if (cap > 0 && used >= cap) el.classList.add("is-limit");
      else if (pct >= 0.75) el.classList.add("is-warning");
    }
    syncMonetizationChrome();
    syncComposerPreviewChrome();
  }

  function syncComposerPreviewChrome() {
    const composer = els.messageInput?.closest?.(".composer.composer-chat");
    if (!composer) return;
    const guest = !isAuthenticated();
    composer.classList.toggle("composer-preview-continue", guest && state.remaining <= 0);
  }

  function applyComposerInteractiveLock() {
    // Never hard-lock the composer after limits. Usage is tracked and billed as overage.
    const locked = false;
    const dock = document.getElementById("workspaceComposerDock");
    if (dock) dock.classList.toggle("composer-dock--locked-preview", locked);
    const input = els.messageInput;
    const send = els.sendBtn;
    if (input && !state.sending) {
      input.disabled = locked;
      input.readOnly = locked;
    }
    if (send && !state.sending) {
      send.disabled = locked;
    }
    document.querySelectorAll(".quick-actions .chip").forEach((chip) => {
      if (chip instanceof HTMLButtonElement) chip.disabled = locked;
    });
  }

  function syncCommandAuthChip() {
    if (!els.commandAuthChip) return;
    if (state.username && state.token) {
      els.commandAuthChip.textContent = state.username;
      els.commandAuthChip.title = "";
    } else {
      els.commandAuthChip.textContent = "Preview";
      els.commandAuthChip.title = "";
    }
  }

  function syncPhase2Stores() {
    const p2 = getPhase2();
    if (!p2 || !p2.sessionStore || !p2.agentStore) return;
    try {
      p2.sessionStore.set({
        token: state.token,
        username: state.username,
        tier: state.tier,
        usage: state.usage,
        limit: state.limit,
        remaining: state.remaining,
        usagePct: state.usagePct,
        approachingLimit: state.approachingLimit,
        atLimit: state.atLimit,
        valueSignals: state.valueSignals,
      });
    } catch {
      /* no-op */
    }
    try {
      const followups = state.crmLeads.filter(
        (lead) => (lead.status === "contacted" || lead.status === "replied") && lead.follow_up_due
      );
      p2.crmStore?.set?.({
        leads: state.crmLeads,
        followups,
        dailySummary: state.crmDailySummary,
        revenueMetrics: state.revenueMetrics,
        summary: state.crmSummary,
        loaded: Boolean(state.token && state.username),
      });
    } catch {
      /* no-op */
    }
    try {
      p2.refundStore?.set?.({
        stripeConnected: state.stripeConnected,
        stripeAccountId: state.stripeAccountId,
        stripeMode: state.stripeMode,
        history: state.refundHistory,
      });
    } catch {
      /* no-op */
    }
  }

  function syncAnalyticsRail() {
    const p2 = getPhase2();
    if (!phase2WorkspaceReady() || !p2?.analyticsEngine?.syncValueRail) return;
    try {
      p2.analyticsEngine.syncValueRail(
        {
          railValueMoney: els.railValueMoney,
          railValueTime: els.railValueTime,
          railValueActions: els.railValueActions,
          railSessionTier: els.railSessionTier,
        },
        state.dashboardStats || {}
      );
    } catch {
      /* no-op */
    }
  }

  function estimateAgentMinutesSavedFromDashboard(d = {}) {
    const p2 = getPhase2();
    if (phase2WorkspaceReady() && p2?.analyticsEngine?.estimateAgentMinutesSavedFromDashboard) {
      try {
        return p2.analyticsEngine.estimateAgentMinutesSavedFromDashboard(d, state.actionsCount);
      } catch {
        /* fall through */
      }
    }
    const actions = Number(d.actions || state.actionsCount || 0);
    const auto = Number(d.auto_resolved || 0);
    return Math.round(actions * 6 + auto * 2);
  }

  function refreshUpgradeValueSummary() {
    const el = els.upgradeValueSummary;
    if (!el) return;
    const p2 = getPhase2();
    if (phase2WorkspaceReady() && p2?.analyticsEngine?.refreshUpgradeValueSummary) {
      try {
        p2.analyticsEngine.refreshUpgradeValueSummary(
          el,
          state.dashboardStats,
          {
            actionsCount: state.actionsCount,
            totalInteractions: state.totalInteractions,
            tier: state.tier,
          },
          { formatMoney }
        );
        return;
      } catch {
        /* fall through */
      }
    }
    const d = state.dashboardStats || {};
    const vg = d.value_generated && typeof d.value_generated === "object" ? d.value_generated : null;
    const tickets = Number(d.total_tickets ?? d.total_interactions ?? state.totalInteractions ?? 0);
    const money = Number((vg && vg.money_saved) ?? d.money_saved ?? 0);
    const actions = Number((vg && vg.actions_taken) ?? d.actions ?? state.actionsCount ?? 0);
    const mins = Number((vg && vg.time_saved_minutes) ?? estimateAgentMinutesSavedFromDashboard(d));
    const tier = String(state.tier || "free").toLowerCase();
    const upgradeHint =
      tier === "free"
        ? " Pro adds 500 runs/month + live refunds."
        : tier === "pro"
          ? " Elite adds 5k runs/month + advanced analytics."
          : "";
    el.textContent =
      tickets > 0 || money > 0 || actions > 0 || mins > 0
        ? `Workspace value so far: ${tickets} tickets · ${formatMoney(money)} through billing actions (${actions} motions) · ~${mins} min saved.${upgradeHint}`
        : "";
    el.style.display = tickets > 0 || money > 0 || actions > 0 || mins > 0 ? "block" : "none";
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
    const capLine = String(vs.capacity_message || "").trim();
    const ctaTier = tier === "pro" ? "elite" : "pro";
    const ctaLabel = tier === "pro" ? "Add Elite headroom before the next ceiling →" : "Upgrade for continuous coverage →";
    const story =
      th > 0 || Number(vs.money_moved ?? 0) > 0
        ? `You’re using real capacity — ${th} tickets this cycle · ${money} in billing motions · ~${tm} min of operator time back.`
        : "You’re approaching this plan’s monthly ceiling — add headroom so approvals and routing don’t stall mid-shift.";
    el.style.display = "block";
    el.innerHTML = `<div>${escapeHtml(story)}</div>
${capLine ? `<div class="muted-copy" style="margin-top:4px">${escapeHtml(capLine)}</div>` : ""}
${unlock ? `<div style="margin-top:6px">${escapeHtml(unlock)}</div>` : ""}
<button type="button" class="ghost-btn" style="margin-top:6px;padding:6px 10px;font-size:12px">${escapeHtml(ctaLabel)}</button>`;
    const btn = el.querySelector("button");
    if (btn) {
      btn.onclick = () => upgradePlan(ctaTier);
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
    if (payload.at_limit === true) state.atLimit = true;
    if (typeof payload.usage_pct === "number" && Number.isFinite(payload.usage_pct)) {
      state.usagePct = payload.usage_pct;
    }
    if (payload.remaining !== undefined && payload.remaining !== null) {
      const r = Number(payload.remaining);
      if (Number.isFinite(r)) state.remaining = Math.max(0, r);
    }
    const unlock = String(payload.upgrade_unlocks || "").trim();
    const capMsg = String(payload.capacity_message || "").trim();
    const thRaw = payload.tickets_handled;
    const ticketsHandled =
      thRaw !== undefined && thRaw !== null ? Number(thRaw) : state.usage;
    state.valueSignals = {
      ...(state.valueSignals && typeof state.valueSignals === "object" ? state.valueSignals : {}),
      tickets_handled: Number.isFinite(ticketsHandled) ? ticketsHandled : state.usage,
      upgrade_unlocks: unlock || (state.valueSignals && state.valueSignals.upgrade_unlocks) || "",
      capacity_message:
        capMsg || (state.valueSignals && state.valueSignals.capacity_message) || "",
    };
    renderUsageIntelligence({
      approaching_limit: true,
      at_limit: state.atLimit,
      tier: state.tier,
      usage: state.usage,
      value_signals: state.valueSignals,
    });
    syncCommandStripCapacity();
    syncPhase2Stores();
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
    syncCommandAuthChip();
    if (els.commandModeLine) {
      els.commandModeLine.textContent = state.latestRun ? "Live run" : "Operator";
    }
    syncCommandStripCapacity();

    if (els.workspaceSubcopy) {
      if (state.latestRun) {
        const decision = state.latestRun.decision || {};
        const posture = operatorPostureLabel(state.latestRun);
        els.workspaceSubcopy.textContent = `${formatTier(state.tier)} · ${displayActionLabel(state.latestRun)} · ${displayQueueLabel({ decision })} · ${posture} · ${formatMetric(state.latestRun.confidence || 0, 2)} conf`;
        if (els.workspaceSubcopyTier) els.workspaceSubcopyTier.hidden = true;
      } else if (state.username) {
        els.workspaceSubcopy.textContent = "Get a customer-ready reply instantly";
        if (els.workspaceSubcopyTier) {
          els.workspaceSubcopyTier.hidden = false;
          els.workspaceSubcopyTier.textContent = `${state.username} · ${formatTier(state.tier)} · Sensitive actions stay gated for approval`;
        }
      } else {
        els.workspaceSubcopy.textContent = "Get a customer-ready reply instantly";
        if (els.workspaceSubcopyTier) {
          els.workspaceSubcopyTier.hidden = false;
          els.workspaceSubcopyTier.textContent = "Sensitive actions stay gated for approval";
        }
      }
    }

    updateAuthStatus();
    syncApprovalRail();
    syncPhase2Stores();
    if (!state.sending) refreshComposerIdleHint();
  }

  function updateSystemNarrative(data = null) {
    if (!els.systemPanelCopy) return;

    if (!data) {
      els.systemPanelCopy.textContent = "Paste a ticket or pick an example chip — your draft shows up here.";
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
    try {
      getPhase2()?.uiStore?.set?.({ stickToBottom: state.stickToBottom });
    } catch {
      /* no-op */
    }
  }

  function scrollMessagesToBottom(force = false) {
    if (!els.messages) return;
    if (force || state.stickToBottom) {
      els.messages.scrollTop = els.messages.scrollHeight;
    }
  }

  function applyFillFromButton(button) {
    const fill = button?.dataset?.fill || "";
    if (!fill || !els.messageInput) return;
    if (!isAuthenticated() && getGuestUsage() >= GUEST_USAGE_LIMIT) {
      focusAccessPanel();
      pushLimitMessage(true);
      applyComposerInteractiveLock();
      return;
    }
    els.messageInput.value = fill;
    saveDraft(fill);
    autoResizeTextarea();
    syncComposerDraftClass();
    els.messageInput.focus();
  }

  /** Subtle branded reveal on prepared reply (CSS: .xv-prepared-reveal) */
  function pulsePreparedReplyReveal(row) {
    const block = row?.querySelector(".customer-message-block");
    if (!block) return;
    block.classList.remove("xv-prepared-reveal");
    void block.offsetWidth;
    block.classList.add("xv-prepared-reveal");
    window.setTimeout(() => block.classList.remove("xv-prepared-reveal"), 1400);
  }

  function createTypingMarkup() {
    return `
      <div class="xv-thinking-card typing" role="status" aria-live="polite" aria-busy="true">
        <div class="xv-thinking-head">
          <span class="xv-thinking-icon" aria-hidden="true">${ICONS.xalvionX}</span>
          <span class="xv-thinking-label" translate="no">Xalvion</span>
        </div>
        <div class="xv-thinking-line">Thinking through the case…</div>
        <div class="xv-thinking-dots" aria-hidden="true">
          <span class="xv-thinking-dot"></span>
          <span class="xv-thinking-dot"></span>
          <span class="xv-thinking-dot"></span>
        </div>
      </div>
    `;
  }

  function getUserBadge() {
    return `
      <span class="msg-identity" aria-hidden="true">${ICONS.person}</span>
      <span>Customer</span>
    `;
  }

  function getAssistantBadge() {
    return `
      <span class="msg-identity" aria-hidden="true">${ICONS.xalvionX}</span>
      <span>Xalvion</span>
    `;
  }

  function swapThinkingToContent(node, nextHtml) {
    if (!node) return;
    const hasTyping = Boolean(node.querySelector(".typing, .xv-thinking-block"));
    if (!hasTyping) return;

    node.classList.add("xv-fade-out");
    window.setTimeout(() => {
      node.innerHTML = nextHtml;
      node.classList.remove("xv-fade-out");
      node.closest?.(".msg-card")?.classList.add("xv-soft-fade-in");
      window.setTimeout(() => node.closest?.(".msg-card")?.classList.remove("xv-soft-fade-in"), 260);
    }, 160);
  }

  function createMessageGroup(role, bodyHtml, isPlaceholder = false) {
    const wrapper = document.createElement("div");
    wrapper.className = `msg-group ${role === "user" ? "user" : "assistant"}`;

    const card = document.createElement("div");
    card.className = `msg-card ${role === "user" ? "user" : "assistant"}`;

    const when = relativeTime(new Date());
    const headLabel = role === "user" ? getUserBadge() : getAssistantBadge();

    const assistantBody =
      role === "assistant"
        ? `<div class="msg-body assistant-canvas">
        <div class="stream-trace-host"></div>
        <div class="assistant-result-stack">
          <div class="assistant-decision-slot" data-slot="decision"></div>
          <div class="assistant-brief-slot" data-slot="brief"></div>
          <div class="customer-message-block">
            <div class="reply-body">
              <div class="assistant-context-line js-assistant-context" hidden></div>
              <div class="reply-prep-meta"><span class="reply-prep-time js-prepared-time" hidden></span></div>
              <div class="customer-message-label reply-hero-label">Suggested reply</div>
              <div class="reply-value-reinforcement js-reply-reinforcement" hidden>AI prepared this based on context, policy, and past outcomes</div>
              <div class="reply-text js-reply-text">${bodyHtml}</div>
            </div>
          </div>
          <div class="assistant-footer js-assistant-footer"></div>
        </div>
      </div>`
        : `<div class="msg-body">
        <div class="reply-body">
          <div class="reply-text js-reply-text">${bodyHtml}</div>
        </div>
      </div>`;

    card.innerHTML = `
      <div class="msg-head">
        <div class="msg-who">${headLabel}</div>
        <div class="msg-time">${escapeHtml(when)}</div>
      </div>
      ${assistantBody}
    `;

    if (isPlaceholder) card.dataset.placeholder = "true";
    wrapper.appendChild(card);
    return wrapper;
  }

  function isClaudeShell() {
    return typeof document !== "undefined" && document.body?.dataset?.ui === "claude";
  }

  function openingTimeGreeting() {
    const h = new Date().getHours();
    if (h < 12) return "Good morning";
    if (h < 17) return "Good afternoon";
    return "Good evening";
  }

  function openingDisplayName() {
    const raw = String(state.username || "").trim();
    if (!raw) return "";
    const first = raw.split(/[._\-@]/)[0] || raw;
    return first.length ? first.charAt(0).toUpperCase() + first.slice(1) : "";
  }

  function buildEmptyStateHtml() {
    const guest = !isAuthenticated();
    const tierLc = String(state.tier || "free").toLowerCase();
    const atCap = guest ? getGuestUsage() >= GUEST_USAGE_LIMIT : state.atLimit;
    const previewLeft = guest ? Math.max(0, GUEST_USAGE_LIMIT - getGuestUsage()) : state.remaining;
    const previewRunsWord = previewLeft === 1 ? "run" : "runs";

    if (atCap) {
      if (isClaudeShell()) {
        return `
      <div class="empty-card limit-moment-card limit-moment-card--claude">
        <h2 class="limit-moment-card__title">You’ve used your free runs</h2>
        <p class="limit-moment-card__lead">Upgrade to keep resolving tickets with approval-safe AI.</p>
        <button type="button" class="limit-cta limit-cta--claude" id="emptyUpgradeCta">Upgrade now</button>
        <button type="button" class="limit-secondary-link limit-secondary-link--claude" id="emptyFreeAccountCta">Create free account</button>
      </div>`;
      }
      return `
      <div class="empty-card limit-moment-card empty-card-premium empty-card-conversion">
        <h2>You’ve used your free runs</h2>
        <p class="limit-moment-lead">Upgrade to keep resolving tickets with approval-safe AI.</p>
        <div class="empty-flow-strip empty-flow-strip-compact" aria-hidden="true">
          <span>Prepare</span>
          <span>Approve</span>
          <span>Execute</span>
        </div>
        <button type="button" class="limit-cta" id="emptyUpgradeCta">Upgrade now</button>
        <button type="button" class="limit-secondary-link" id="emptyFreeAccountCta">Create free account</button>
      </div>`;
    }

    if (isClaudeShell()) {
      const name = openingDisplayName();
      const greet = openingTimeGreeting();
      const recents = Array.isArray(state.recentTickets) ? state.recentTickets : [];
      const hasRecents = recents.length > 0;
      const momentum = momentumLine();
      const savedMin = estimateTimeSavedMinutes();
      const subMomentum =
        momentum
          ? `<div class="xv-momentum-line">${escapeHtml(momentum)}${savedMin > 0 ? ` <span class="xv-momentum-sub">Estimated time saved: ${savedMin} minutes</span>` : ""}</div>`
          : "";
      const recentList = hasRecents
        ? `<div class="xv-recent-block" aria-label="Recent tickets">
            <div class="xv-recent-head">
              <div class="xv-recent-title">Continue where you left off</div>
              <button type="button" class="xv-recent-cta" data-act="continue-last">Continue last case</button>
            </div>
            <div class="xv-recent-list">
              ${recents
                .slice(0, 5)
                .map((t) => {
                  const id = Number(t.id || 0) || 0;
                  const msg = String(t.customer_message || "").trim();
                  const preview = msg ? msg.replace(/\s+/g, " ").slice(0, 110) : String(t.subject || "").slice(0, 110);
                  const meta = [t.issue_type, t.queue].filter(Boolean).join(" · ");
                  return `
                    <button type="button" class="xv-recent-item" data-act="recent-open" data-ticket-id="${escapeHtml(String(id || ""))}">
                      <div class="xv-recent-item-top">
                        <span class="xv-recent-item-id">#${escapeHtml(String(id || "—"))}</span>
                        <span class="xv-recent-item-meta">${escapeHtml(meta || "Recent")}</span>
                      </div>
                      <div class="xv-recent-item-preview">${escapeHtml(preview || "Open ticket")}</div>
                    </button>
                  `;
                })
                .join("")}
            </div>
          </div>`
        : "";
      return `
      <div class="empty-card empty-card-launch empty-card-launch--claude empty-card-onboarding" role="status">
        <h2 class="cld-welcome-headline">${escapeHtml(`${greet}${name ? `, ${name}` : ""} — ready to handle tickets?`)}</h2>
        <p class="cld-welcome-prompt onboarding-subline">Paste a support ticket. Xalvion prepares the reply and suggested actions — you approve.</p>
        ${subMomentum}
        ${recentList}
        <div class="onboarding-example" aria-hidden="true">
          <div class="onboarding-example-label">Operator habit</div>
          <div class="onboarding-example-text">Use Xalvion before replying to any customer</div>
        </div>
      </div>`;
    }

    const chipHintGuest = guest
      ? `Preview mode · ${previewLeft} operator ${previewRunsWord} remaining`
      : `${formatTier(state.tier)} · ${state.remaining} operator runs this period`;

    return `
      <div class="empty-card empty-card-premium empty-card-launch">
        <p class="empty-launch-directive">Make a support decision</p>
        <p class="empty-launch-outcome">AI prepares the reply and the next action</p>
        <p class="empty-launch-review">Review, edit, or approve before anything executes</p>
        <div class="empty-flow-strip" aria-hidden="true">
          <span>Analyze ticket</span>
          <span>Prepare action</span>
          <span>Approve &amp; execute</span>
        </div>
        <div class="empty-actions empty-actions-intent" role="group" aria-label="Example ticket">
          <button type="button" class="chip empty-intent-chip" data-fill="A customer says: I was charged twice.">Duplicate charge</button>
          <button type="button" class="chip empty-intent-chip" data-fill="A customer says: my package is late and I need an update.">Late package</button>
          <button type="button" class="chip empty-intent-chip" data-fill="A customer says: my order arrived damaged and I want help.">Damaged order</button>
        </div>
        <div class="empty-actions empty-actions-launch">
          <span class="empty-chip-hint">${chipHintGuest}</span>
          <span class="empty-chip-hint empty-chip-hint-secondary">Approval-safe actions stay gated until you decide</span>
        </div>
      </div>`;
  }

  function openAccessDrawer(target = "account") {
    const drawer = els.accessDrawer;
    if (!drawer) return;
    if (drawer.dataset.accessState === "closing") return;

    drawer.classList.add("open");
    drawer.dataset.accessState = "opening";
    drawer.setAttribute("aria-hidden", "false");
    document.body.classList.add("access-open");

    // Ensure staged entrance (backdrop → panel → content) lands reliably.
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        if (!drawer.classList.contains("open")) return;
        if (drawer.dataset.accessState === "opening") drawer.dataset.accessState = "open";
      });
    });

    const id = "accessDrawerSectionAccount";
    window.setTimeout(() => {
      document.getElementById(id)?.scrollIntoView?.({ behavior: "smooth", block: "start" });
      if (target === "account") window.setTimeout(() => els.usernameInput?.focus?.(), 80);
    }, 60);
  }

  function closeAccessDrawer() {
    const drawer = els.accessDrawer;
    if (!drawer) return;
    if (drawer.dataset.accessState === "closing" || !drawer.classList.contains("open")) return;

    drawer.dataset.accessState = "closing";
    drawer.setAttribute("aria-hidden", "true");

    // Mirror the staged open in reverse: content → panel → backdrop.
    window.setTimeout(() => {
      drawer.classList.remove("open");
      delete drawer.dataset.accessState;
      document.body.classList.remove("access-open");
    }, 340);
  }

  function focusAccessPanel(target = "account") {
    openAccessDrawer(target);
  }

  function focusPlansPanel() {
    setSurface("plans");
  }

  function setSurface(key) {
    const surface = String(key || "workspace").toLowerCase();
    const main = document.getElementById("mainCanvas");
    if (main) main.dataset.surface = surface;
    document.querySelectorAll("[data-surface-panel]").forEach((panel) => {
      const on = String(panel.getAttribute("data-surface-panel") || "").toLowerCase() === surface;
      if (on) panel.removeAttribute("hidden");
      else panel.setAttribute("hidden", "");
    });
    const shell = els.sidebarShell;
    if (shell) shell.dataset.sidebarActive = surface;
    if (surface === "integrations") {
      refreshIntegrationsStatus().catch(() => {});
    }
    if (surface === "crm") {
      refreshLeads().catch(() => {});
      refreshFollowups().catch(() => {});
      refreshCrmDailySummary().catch(() => {});
    }
    if (surface === "revenue") {
      refreshRevenue().catch(() => {});
    }
    try {
      sessionStorage.setItem("xalvion-surface", surface);
    } catch {}
  }

  function bindEmptyStateActions(empty) {
    if (!empty) return;
    empty.querySelector("#emptyUpgradeCta")?.addEventListener("click", () => {
      if (!isAuthenticated()) {
        focusPlansPanel();
        return;
      }
      const t = String(state.tier || "free").toLowerCase();
      if (t === "pro") upgradePlan("elite");
      else upgradePlan("pro");
    });
    empty.querySelector("#emptyFreeAccountCta")?.addEventListener("click", () => {
      focusAccessPanel();
    });

    empty.querySelector("[data-act='continue-last']")?.addEventListener("click", async () => {
      const t = Array.isArray(state.recentTickets) ? state.recentTickets[0] : null;
      const id = Number(t?.id || 0) || 0;
      if (!id) return;
      try {
        const res = await fetch(`${API}/tickets/${id}`, { method: "GET", headers: headers(true) });
        const data = await parseApiResponse(res);
        if (!res.ok) return;
        const ticket = data?.ticket || data;
        const msg = String(ticket?.customer_message || "").trim();
        if (msg) {
          els.messageInput.value = msg;
          saveDraft(msg);
          autoResizeTextarea();
          syncComposerDraftClass();
          els.messageInput.focus();
        }
      } catch {}
    });

    empty.querySelectorAll("[data-act='recent-open']").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = Number(btn.getAttribute("data-ticket-id") || 0) || 0;
        if (!id) return;
        try {
          const res = await fetch(`${API}/tickets/${id}`, { method: "GET", headers: headers(true) });
          const data = await parseApiResponse(res);
          if (!res.ok) return;
          const ticket = data?.ticket || data;
          const msg = String(ticket?.customer_message || "").trim();
          if (msg) {
            els.messageInput.value = msg;
            saveDraft(msg);
            autoResizeTextarea();
            syncComposerDraftClass();
            els.messageInput.focus();
          }
        } catch {}
      });
    });
  }

  function refreshEmptyStateContent() {
    const empty = els.messages?.querySelector(".empty-state");
    if (!empty) return;
    empty.innerHTML = buildEmptyStateHtml();
    bindEmptyStateActions(empty);
    syncWorkspaceLayoutMode();
  }

  function addEmptyState() {
    if (!els.messages) return;
    if (els.messages.querySelector(".empty-state")) return;

    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = buildEmptyStateHtml();
    els.messages.appendChild(empty);
    syncWorkspaceLayoutMode();

    bindEmptyStateActions(empty);
  }

  function clearEmptyState() {
    els.messages?.querySelector(".empty-state")?.remove();
  }

  function syncComposerDockThreadClass() {
    const dock = document.getElementById("workspaceComposerDock");
    if (!dock || !els.messages) return;
    const hasThread = Boolean(els.messages.querySelector(".msg-group"));
    dock.classList.toggle("composer-dock--thread", hasThread);
  }

  function syncWorkspaceLayoutMode() {
    const root = els.workspaceRoot;
    if (!root || !els.messages) return;
    const hasConversation = Boolean(els.messages.querySelector(".msg-group"));
    const hasLimitCard = Boolean(els.messages.querySelector(".empty-state .limit-moment-card"));
    const active = hasConversation || hasLimitCard;
    root.classList.toggle("workspace-idle", !active);
    root.classList.toggle("workspace-active", active);
    root.style.setProperty("--xv-layout-active", active ? "1" : "0");
    syncComposerDockThreadClass();
  }

  function addUserMessage(text) {
    clearEmptyState();
    const row = createMessageGroup("user", escapeHtml(text).replace(/\n/g, "<br>"));
    els.messages?.appendChild(row);
    scrollMessagesToBottom(true);
    refreshMessageShellGlow();
    syncWorkspaceLayoutMode();
    return row;
  }

  function addAssistantMessage(initialText = "") {
    clearEmptyState();
    const initial = initialText ? escapeHtml(initialText).replace(/\n/g, "<br>") : createTypingMarkup();
    const row = createMessageGroup("assistant", initial, true);
    els.messages?.appendChild(row);
    scrollMessagesToBottom(true);
    refreshMessageShellGlow();
    syncWorkspaceLayoutMode();
    return row;
  }

  function getAssistantCopyNode(row) {
    return row?.querySelector(".js-reply-text") || null;
  }

  function syncReplyReinforcement(row) {
    const rein = row?.querySelector(".js-reply-reinforcement");
    if (!rein) return;
    if (row?.classList.contains("msg-group--limit-cta")) {
      rein.hidden = true;
      return;
    }
    const card = row?.querySelector(".msg-card");
    const node = getAssistantCopyNode(row);
    const txt = (node?.textContent || "").trim();
    const typing = node?.querySelector?.(".xalvion-typing-sovereign, .xv-thinking-block");
    const looksLikeError = /something went wrong|request failed|no response returned|plan limit reached/i.test(txt);
    rein.hidden = !txt || Boolean(typing) || card?.dataset.placeholder === "true" || looksLikeError;
  }

  function setPreparedMeta(row, seconds) {
    const el = row?.querySelector?.(".js-prepared-time");
    if (!el) return;
    const s = Number(seconds);
    if (!Number.isFinite(s) || s <= 0) {
      el.hidden = true;
      el.textContent = "";
      return;
    }
    const fixed = Math.max(0.1, Math.round(s * 10) / 10).toFixed(1);
    el.textContent = `Prepared in ${fixed}s`;
    el.hidden = false;
  }

  function maybeMountAutomationUpsell(row, replyText = "") {
    if (state.automationUpsellShown) return;
    const tier = String(state.tier || "free").toLowerCase();
    if (tier === "elite" || tier === "dev") return;
    const txt = String(replyText || "").trim();
    if (txt.length < 40) return;
    if (/something went wrong|request failed|no response returned|plan limit reached/i.test(txt)) return;

    const footer = getAssistantFooterNode(row);
    if (!footer) return;

    const upsell = document.createElement("div");
    upsell.className = "automation-upsell";
    upsell.innerHTML = `
      <div class="automation-upsell-copy">Want Xalvion to handle refunds, tracking, and actions automatically?</div>
      <button type="button" class="automation-upsell-cta">Unlock automation</button>
    `;
    const btn = upsell.querySelector("button");
    btn?.addEventListener("click", () => {
      state.automationUpsellShown = true;
      focusPlansPanel();
      window.setTimeout(() => {
        document.getElementById("planEliteCard")?.scrollIntoView?.({ behavior: "smooth", block: "center" });
      }, 120);
    });

    footer.appendChild(upsell);
    state.automationUpsellShown = true;
  }

  function getAssistantFooterNode(row) {
    return row?.querySelector(".js-assistant-footer") || null;
  }

  function setAssistantCopy(row, text) {
    const node = getAssistantCopyNode(row);
    if (!node) return;
    const html = escapeHtml(text || "").replace(/\n/g, "<br>");
    if (node.querySelector(".typing, .xv-thinking-block")) {
      swapThinkingToContent(node, html);
    } else {
      node.innerHTML = html;
      node.closest?.(".msg-card")?.classList.add("xv-soft-fade-in");
      window.setTimeout(() => node.closest?.(".msg-card")?.classList.remove("xv-soft-fade-in"), 260);
    }
    const card = row?.querySelector(".msg-card");
    if (card?.dataset.placeholder !== "true") syncReplyReinforcement(row);
  }

  function appendAssistantChunk(row, chunk) {
    const node = getAssistantCopyNode(row);
    if (!node) return;

    if (node.querySelector(".typing, .xv-thinking-block")) {
      // Fade out thinking, then begin streaming into the real node.
      swapThinkingToContent(node, "");
      window.setTimeout(() => {
        const current = node.textContent || "";
        node.innerHTML = escapeHtml(current + chunk).replace(/\n/g, "<br>");
        syncReplyReinforcement(row);
        scrollMessagesToBottom();
      }, 170);
      return;
    }

    const current = node.textContent || "";
    node.innerHTML = escapeHtml(current + chunk).replace(/\n/g, "<br>");
    syncReplyReinforcement(row);
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

    // Governor risk chip (only when governor fields are present).
    try {
      const fmt = globalThis.__XALVION_FORMAT__;
      const gov = fmt?.deriveGovernorPresentation ? fmt.deriveGovernorPresentation(data) : null;
      const riskChipText = String(gov?.riskScoreLabel || gov?.riskLabel || "").trim();
      if (gov && gov.mode && gov.mode !== "unknown" && riskChipText) {
        meta.appendChild(
          createMetaChip({
            icon: ICONS.warn,
            text: riskChipText,
            tone: "risk governor-risk-chip",
          })
        );
      }
    } catch {}

    return meta;
  }

  function wrapAssistantMetaFold(metaRow) {
    const fold = document.createElement("details");
    fold.className = "assistant-meta-fold";
    const sum = document.createElement("summary");
    sum.className = "assistant-meta-fold-summary";
    sum.textContent = "Details";
    const body = document.createElement("div");
    body.className = "assistant-meta-fold-body";
    body.appendChild(metaRow);
    fold.appendChild(sum);
    fold.appendChild(body);
    return fold;
  }

  function syncAssistantContextLine(row, data) {
    const el = row?.querySelector?.(".js-assistant-context");
    if (!el) return;
    const card = row.querySelector(".msg-card");
    if (!data || card?.dataset.placeholder === "true") {
      el.hidden = true;
      el.textContent = "";
      return;
    }
    const approval = getApprovalContext(data);
    if (approval.requiresApproval && !approval.approved) {
      el.hidden = false;
      el.textContent = "Sensitive actions await your approval before they run.";
    } else {
      el.hidden = true;
      el.textContent = "";
    }
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
    try {
      const fmt = globalThis.__XALVION_FORMAT__;
      const gov = fmt?.deriveGovernorPresentation ? fmt.deriveGovernorPresentation(data) : null;
      if (gov && gov.mode && gov.mode !== "unknown") {
        if (gov.mode === "blocked") return "Blocked by policy";
        if (gov.mode === "review") return "Approval required";
        if (gov.mode === "auto") return "Safe to automate";
      }
    } catch {}
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
    try {
      const fmt = globalThis.__XALVION_FORMAT__;
      const gov = fmt?.deriveGovernorPresentation ? fmt.deriveGovernorPresentation(data) : null;
      if (gov && gov.mode && gov.mode !== "unknown") {
        if (gov.mode === "blocked") return "Blocked by policy — do not execute as proposed.";
        if (gov.mode === "review") return "Approval required under policy — verify factors, then approve.";
        if (gov.mode === "auto") return "Governor indicates the action is safe to automate.";
      }
    } catch {}
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
    try {
      const fmt = globalThis.__XALVION_FORMAT__;
      const gov = fmt?.deriveGovernorPresentation ? fmt.deriveGovernorPresentation(data) : null;
      if (gov && gov.mode && gov.mode !== "unknown" && gov.nextStep) {
        return gov.nextStep;
      }
    } catch {}
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
    // File: app.js
    // Governor fields (when present) are the final authority trust signal.
    try {
      const fmt = globalThis.__XALVION_FORMAT__;
      const gov = fmt?.deriveGovernorPresentation ? fmt.deriveGovernorPresentation(data) : null;
      if (gov && gov.mode && gov.mode !== "unknown") {
        const text =
          gov.mode === "blocked"
            ? "⛔ Blocked by policy"
            : gov.mode === "review"
              ? "⚡ Approval required"
              : gov.mode === "auto"
                ? "✓ Safe to automate"
                : "○ Manual review";
        return {
          cls: gov.cls || "signal-review",
          text,
          title: String(gov.summary || gov.title || ""),
        };
      }
    } catch {}
    const govRisk = String(data.governor_risk_level || dec.governor_risk_level || "").toLowerCase();
    const risk = String(govRisk || dec.risk_level || data.triage?.risk_level || "").toLowerCase();
    const execMode = String(data.execution_mode || dec.execution_mode || "").toLowerCase();
    if (execMode === "blocked") {
      return {
        cls: "signal-high-risk signal-blocked",
        text: "⛔ Blocked by policy",
        title: String(data.governor_reason || dec.governor_reason || "Blocked by governor policy"),
      };
    }
    if (execMode === "review") {
      return {
        cls: "signal-approval",
        text: "⚡ Approval required",
        title: String(data.governor_reason || dec.governor_reason || "Review required under governor policy"),
      };
    }
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
        title: String(data.governor_reason || dec.governor_reason || "Awaiting operator approval")
      };
    }

    const action = String(data.action || dec.action || "none").toLowerCase();
    const actionRisk = String(dec.risk_level || data.triage?.risk_level || "medium").toLowerCase();
    const req = Boolean(
      data.requires_approval || dec.requires_approval || data.decision_state === "pending_decision"
    );
    const money = action === "refund" || action === "charge" || action === "credit";
    if (req && money) return { cls: "signal-approval", text: "⚡ Approval required", title: "" };
    if (action === "review" || actionRisk === "high" || actionRisk === "medium") {
      return { cls: "signal-review", text: "⚠ Review recommended", title: "" };
    }
    return { cls: "signal-safe", text: "✓ Safe to send", title: "" };
  }

  function mountOperatorDecisionPanel(row, data, initialReply) {
    row.querySelector(".decision-panel")?.remove();
    const msgBody = row.querySelector(".msg-body");
    if (!msgBody || !data) return;
    const decisionSlot = row.querySelector("[data-slot='decision']");
    const mountTarget = decisionSlot || msgBody;

    const ticket = data.ticket || {};
    const ticketId = Number(ticket.id || 0) || null;
    const approval = getApprovalContext(data);
    const pendingGate = Boolean(approval.requiresApproval && !approval.approved);
    const sig = deriveConsequenceSignal(data);
    const originalAi = String(
      initialReply || getAssistantCopyNode(row)?.innerText || getAssistantCopyNode(row)?.textContent || ""
    ).trim();

    const panel = document.createElement("div");
    panel.className = "decision-panel";
    panel.innerHTML = `
      <div class="decision-panel-top">
        <span class="consequence-signal ${sig.cls}" data-role="consequence">${escapeHtml(sig.text)}</span>
        <div class="decision-controls" data-role="controls"></div>
      </div>
      <div class="decision-panel-note" data-role="trust">Nothing is sent without your approval</div>
      <div class="decision-panel-note" data-role="note" style="display:none"></div>
      <div class="decision-panel-error" data-role="err" style="display:none"></div>
      <div class="edit-mode-container" data-role="edit" style="display:none"></div>
      <div class="xv-next-action" data-role="next" style="display:none"></div>
    `;
    mountTarget.appendChild(panel);

    const cons = panel.querySelector("[data-role='consequence']");
    if (cons && sig.title) cons.setAttribute("title", sig.title);

    const controls = panel.querySelector("[data-role='controls']");
    const trustEl = panel.querySelector("[data-role='trust']");
    const noteEl = panel.querySelector("[data-role='note']");
    const errEl = panel.querySelector("[data-role='err']");
    const editWrap = panel.querySelector("[data-role='edit']");
    const nextWrap = panel.querySelector("[data-role='next']");

    // File: app.js
    // Governor visibility pass (optional): surface reason/factors/violations/next-step without changing layout structure.
    try {
      const fmt = globalThis.__XALVION_FORMAT__;
      const gov = fmt?.deriveGovernorPresentation ? fmt.deriveGovernorPresentation(data) : null;
      if (gov && gov.mode && gov.mode !== "unknown") {
        if (trustEl && gov.summary) trustEl.textContent = gov.summary;
        const riskText = String(gov.riskScoreLabel || gov.riskLabel || "").trim();
        const factors = Array.isArray(gov.factors) ? gov.factors.slice(0, 3) : [];
        const violations = Array.isArray(gov.violations) ? gov.violations.slice(0, 3) : [];
        const next = String(gov.nextStep || "").trim();
        const blocks = [];
        if (riskText) {
          blocks.push(`<div class="governor-risk-row"><span class="governor-risk-chip">${escapeHtml(riskText)}</span></div>`);
        }
        if (next) {
          blocks.push(`<div class="governor-next-step">${escapeHtml(next)}</div>`);
        }
        if (factors.length) {
          blocks.push(
            `<div class="governor-factors"><div class="governor-factors-label">Governor factors</div>${factors
              .map((f) => `<div class="governor-factor">${escapeHtml(f)}</div>`)
              .join("")}</div>`
          );
        }
        if (violations.length) {
          blocks.push(
            `<div class="governor-violations"><div class="governor-violations-label">Policy checks</div>${violations
              .map((v) => `<div class="governor-violation">${escapeHtml(v)}</div>`)
              .join("")}</div>`
          );
        }
        if (noteEl && blocks.length) {
          noteEl.innerHTML = blocks.join("");
          noteEl.style.display = "block";
        }
      }
    } catch {}

    const showErr = (t) => {
      errEl.textContent = t || "";
      errEl.style.display = t ? "block" : "none";
    };

    const setTerminal = (pill, note) => {
      panel.classList.remove("decision-state-approved", "decision-state-rejected");
      if (pill === "Approved" || pill === "Sent as edited") {
        panel.classList.add("decision-state-approved");
      } else if (pill === "Rejected") {
        panel.classList.add("decision-state-rejected");
      }
      controls.innerHTML = `<span class="decision-state-pill">${escapeHtml(pill)}</span>`;
      if (note) {
        noteEl.textContent = note;
        noteEl.style.display = "block";
        noteEl.dataset.tone = /Sent to customer/i.test(note) ? "success" : "";
      } else {
        noteEl.textContent = "";
        noteEl.style.display = "none";
        noteEl.dataset.tone = "";
      }

      if (nextWrap) {
        const approved = pill === "Approved" || pill === "Sent as edited";
        nextWrap.style.display = approved ? "block" : "none";
        nextWrap.innerHTML = approved ? buildNextActionHtml() : "";
        if (approved) bindNextActionHandlers(nextWrap);
      }
    };

    function buildNextActionHtml() {
      const n = effectiveTicketCount();
      const mins = estimateTimeSavedMinutes();
      const momentum = momentumLine();
      const integrationHint = n >= 2 ? "Connect your system to auto-fill tracking, refunds, and orders" : "";
      const volumeHint = n >= 5 ? "Handling more tickets? Upgrade for higher limits" : "";
      const tierLc = String(state.tier || "free").toLowerCase();
      const canShowAutomation = !state.automationUpsellShown && tierLc !== "elite" && tierLc !== "dev";
      const automationBlock = canShowAutomation
        ? `<div class="xv-next-nudge">
            <div class="xv-next-nudge-copy">Want Xalvion to handle this automatically next time?</div>
            <button type="button" class="xv-next-nudge-cta" data-act="enable-automation">Enable automation</button>
          </div>`
        : "";
      const integrationBlock = integrationHint
        ? `<div class="xv-next-nudge">
            <div class="xv-next-nudge-copy">${escapeHtml(integrationHint)}.</div>
            <button type="button" class="xv-next-nudge-cta" data-act="connect-integrations">Connect Stripe / CRM</button>
          </div>`
        : "";
      const volumeBlock = volumeHint
        ? `<div class="xv-next-nudge xv-next-nudge--subtle">
            <div class="xv-next-nudge-copy">${escapeHtml(volumeHint)}.</div>
            <button type="button" class="xv-next-nudge-cta" data-act="upgrade">View plans</button>
          </div>`
        : "";

      return `
        <div class="xv-next-success" role="status" aria-live="polite">
          <div class="xv-next-success-title">Response approved <span aria-hidden="true">✓</span></div>
          <div class="xv-next-success-sub">Ready to send</div>
        </div>

        <div class="xv-next-prompt">
          <div class="xv-next-prompt-title">Handle another ticket?</div>
          <div class="xv-next-actions" role="group" aria-label="Next actions">
            <button type="button" class="xv-next-btn" data-act="paste-another">Paste another</button>
            <button type="button" class="xv-next-btn xv-next-btn--ghost" data-act="simulate">Simulate new case</button>
          </div>
          <div class="xv-next-meta">
            ${momentum ? `<span class="xv-next-meta-chip">${escapeHtml(momentum)}</span>` : ""}
            ${mins > 0 ? `<span class="xv-next-meta-chip">Estimated time saved: ${escapeHtml(String(mins))} min</span>` : ""}
            <span class="xv-next-meta-chip">For teams handling higher volume, Xalvion scales with your workflow</span>
          </div>
        </div>

        ${automationBlock}
        ${integrationBlock}
        ${volumeBlock}
      `;
    }

    function bindNextActionHandlers(host) {
      host.querySelector("[data-act='paste-another']")?.addEventListener("click", () => {
        els.messageInput?.focus?.();
      });
      host.querySelector("[data-act='simulate']")?.addEventListener("click", () => {
        const samples = [
          "A customer says: I was charged twice and I need a refund.",
          "A customer says: My order is late and I’m frustrated — can you check tracking?",
          "A customer says: The item arrived damaged. I want a replacement or refund.",
          "A customer says: Where is my order? I can’t find an update.",
        ];
        const fill = samples[Math.floor(Math.random() * samples.length)] || samples[0];
        if (fill && els.messageInput) {
          els.messageInput.value = fill;
          saveDraft(fill);
          autoResizeTextarea();
          syncComposerDraftClass();
          els.messageInput.focus();
        }
      });
      host.querySelector("[data-act='enable-automation']")?.addEventListener("click", () => {
        state.automationUpsellShown = true;
        focusPlansPanel();
        window.setTimeout(() => {
          document.getElementById("planEliteCard")?.scrollIntoView?.({ behavior: "smooth", block: "center" });
        }, 120);
      });
      host.querySelector("[data-act='connect-integrations']")?.addEventListener("click", () => {
        setSurface("integrations");
      });
      host.querySelector("[data-act='upgrade']")?.addEventListener("click", () => {
        focusPlansPanel();
      });
    }

    const postPill = row.dataset.opPostPill;
    if (postPill) {
      delete row.dataset.opPostPill;
      setTerminal(postPill, "Ready to send");
      return;
    }
    const tst = String(data.tool_status || "").toLowerCase();
    const st = String(data.status || ticket.status || "").toLowerCase();
    if (tst === "rejected" || st === "escalated") {
      setTerminal("Rejected", "Response held. Ticket escalated.");
      return;
    }
    if (approval.approved) {
      setTerminal("Approved", "Ready to send");
      return;
    }

    const wireActions = () => {
      controls.innerHTML = "";
      const rej = document.createElement("button");
      rej.type = "button";
      rej.className = "op-action op-action--ghost-danger";
      rej.innerHTML = `<span class="op-action__icon" aria-hidden="true">${ICONS.reject}</span><span class="op-action__label">Reject</span>`;
      const ed = document.createElement("button");
      ed.type = "button";
      ed.className = "op-action op-action--secondary";
      ed.innerHTML = `<span class="op-action__icon" aria-hidden="true">${ICONS.edit}</span><span class="op-action__label">Edit</span>`;
      const ap = document.createElement("button");
      ap.type = "button";
      const setApproveIdle = () => {
        ap.classList.remove("is-loading");
        ap.innerHTML = `<span class="op-action__icon" aria-hidden="true">${ICONS.approve}</span><span class="op-action__label">Approve</span>`;
      };
      ap.className = "op-action op-action--primary";
      setApproveIdle();
      controls.append(rej, ed, ap);

      ed.addEventListener("click", () => {
        showErr("");
        editWrap.style.display = "grid";
        const draftSeed = String(
          getCopyTextFromRow(row, initialReply) || originalAi || ""
        ).trim();
        editWrap.innerHTML = `
          <div class="edit-mode-sheet">
            <div class="edit-mode-header">
              <div class="edit-mode-title">Edit customer-facing reply</div>
              <p class="edit-mode-sub">Adjust tone or facts — the original stays visible for context.</p>
            </div>
            <div class="original-response-block">
              <div class="original-response-label">Original prepared reply</div>
              <div class="original-response" data-original-anchor="true">${escapeHtml(originalAi)}</div>
            </div>
            <label class="edit-compose-label">Your edited version
              <textarea class="decision-edit-textarea" aria-label="Edited reply">${escapeHtml(draftSeed)}</textarea>
            </label>
            <div class="edit-actions">
              <button type="button" class="btn-cancel-edit" data-act="cancel">Cancel edit</button>
              <button type="button" class="btn-send-edited" data-act="send">Send edited reply</button>
            </div>
          </div>
        `;
        const ta = editWrap.querySelector(".decision-edit-textarea");
        ta?.focus();
        ta?.setSelectionRange(ta.value.length, ta.value.length);
        editWrap.querySelector("[data-act='cancel']")?.addEventListener("click", () => {
          editWrap.style.display = "none";
          editWrap.innerHTML = "";
        });
        const sendEdited = editWrap.querySelector("[data-act='send']");
        sendEdited?.addEventListener("click", async () => {
          const next = String(ta?.value || "").trim();
          if (!next) {
            showErr("Edited reply cannot be empty.");
            return;
          }
          if (pendingGate && ticketId && approval.canApprove) {
            [rej, ed, ap].forEach((b) => {
              b.disabled = true;
            });
            sendEdited.disabled = true;
            sendEdited.textContent = "Sending…";
            ap.classList.add("is-loading");
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
              setApproveIdle();
              sendEdited.disabled = false;
              sendEdited.textContent = "Send edited reply";
            }
          } else {
            sendEdited.disabled = true;
            sendEdited.textContent = "Applying…";
            window.setTimeout(() => {
              setAssistantCopy(row, next);
              editWrap.style.display = "none";
              editWrap.innerHTML = "";
              setTerminal("Edited", "Copy the card text when you send to the customer.");
              setNotice("info", "Reply updated", "No server gate on this run — text updated on the card.");
            }, 120);
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
          ap.classList.add("is-loading");
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
            setApproveIdle();
          }
          return;
        }
        setTerminal("Approved", "Ready to send");
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
    const briefSlot = row.querySelector("[data-slot='brief']");
    if (footer) {
      footer.innerHTML = "";
      const toolsWrap = document.createElement("div");
      addCopyControl(toolsWrap, replyText, row);
      footer.appendChild(toolsWrap);
      footer.appendChild(wrapAssistantMetaFold(createMetaRow(normalized)));
    }
    const nextBrief = createDetailsPanel(normalized);
    const existingBrief = briefSlot?.querySelector(".details-wrap") || row.querySelector(".details-wrap");
    if (briefSlot) {
      briefSlot.querySelector(".approval-banner")?.remove();
      const approvalBanner = createApprovalBanner(normalized);
      if (existingBrief) {
        existingBrief.replaceWith(nextBrief);
        if (approvalBanner) briefSlot.insertBefore(approvalBanner, briefSlot.firstChild);
      } else {
        briefSlot.innerHTML = "";
        if (approvalBanner) briefSlot.appendChild(approvalBanner);
        briefSlot.appendChild(nextBrief);
      }
    } else if (existingBrief) {
      existingBrief.replaceWith(nextBrief);
    } else {
      const approvalBanner = createApprovalBanner(normalized);
      const host = footer?.parentElement;
      if (approvalBanner) host?.appendChild(approvalBanner);
      host?.appendChild(nextBrief);
    }
    mountOperatorDecisionPanel(row, normalized, replyText);
    syncAssistantContextLine(row, normalized);
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
    details.className = "details-wrap operator-brief-details";
    details.open = false;

    const decision = data.decision || {};
    const output = data.output || {};
    const impact = data.impact || {};
    const toolStatus = String(data.tool_status || data.execution?.status || "resolved");
    const internalNote = String(output.internal_note || "").trim();
    const policyNote = String(data.reason || decision.reason || "").trim();
    const trace = thinkingTraceSnippet(data, 5);
    const execDetail = String(data.execution?.detail || data.tool_result?.message || "").trim();

    let governorBlock = "";
    try {
      const fmt = globalThis.__XALVION_FORMAT__;
      const gov = fmt?.deriveGovernorPresentation ? fmt.deriveGovernorPresentation(data) : null;
      if (gov && gov.mode && gov.mode !== "unknown") {
        const factors = Array.isArray(gov.factors) ? gov.factors.slice(0, 3) : [];
        const violations = Array.isArray(gov.violations) ? gov.violations.slice(0, 3) : [];
        const riskText = String(gov.riskScoreLabel || gov.riskLabel || "").trim();
        const next = String(gov.nextStep || "").trim();
        const reason = String(gov.summary || "").trim();
        governorBlock = `
          <div class="governor-block">
            ${reason ? `<div class="governor-summary">${escapeHtml(reason)}</div>` : ""}
            ${riskText ? `<div class="governor-risk-row"><span class="governor-risk-chip">${escapeHtml(riskText)}</span></div>` : ""}
            ${next ? `<div class="governor-next-step">${escapeHtml(next)}</div>` : ""}
            ${
              factors.length
                ? `<div class="governor-factors"><div class="governor-factors-label">Governor factors</div>${factors
                    .map((f) => `<div class="governor-factor">${escapeHtml(f)}</div>`)
                    .join("")}</div>`
                : ""
            }
            ${
              violations.length
                ? `<div class="governor-violations"><div class="governor-violations-label">Policy checks</div>${violations
                    .map((v) => `<div class="governor-violation">${escapeHtml(v)}</div>`)
                    .join("")}</div>`
                : ""
            }
          </div>
        `;
      }
    } catch {}

    const explainabilityBrief = buildExplainabilityBriefHtml(data.decision_explainability);
    const explanationInsightsHtml = explainabilityBrief
      ? ""
      : buildDecisionExplanationInsightsHtml(data.decision_explanation);

    const insightBlock = `
      <div class="details-insight-stack">
        ${governorBlock}
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
        <span>Why this decision</span>
        <span class="chev">${ICONS.chevron}</span>
      </summary>
      <div class="details-panel">
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
    wrap.className = "stream-steps stream-steps--premium";
    wrap.innerHTML = `
      <div class="stream-trace-header">
        <span class="stream-trace-mark" aria-hidden="true"><span class="xalvion-sovereign-mark xalvion-sovereign-mark--sm xv-spark-mark"><span class="xv-signal-rays" aria-hidden="true"></span><span class="xv-spark-orbit" aria-hidden="true"></span></span></span>
        <span class="stream-trace-header-copy">
          <span class="stream-trace-kicker">Preparing</span>
          <span class="stream-trace-title">Decision trace</span>
        </span>
      </div>
      <div class="stream-step-row">
      <div class="stream-step active"><div class="stream-step-dot"></div><span>Reviewing</span></div>
      <div class="stream-step"><div class="stream-step-dot"></div><span>Routing</span></div>
      <div class="stream-step"><div class="stream-step-dot"></div><span>Responding</span></div>
      <div class="stream-step"><div class="stream-step-dot"></div><span>Finalizing</span></div>
      </div>
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
    const minH = isClaudeShell() ? 34 : 38;
    els.messageInput.style.height = `${Math.min(220, Math.max(minH, els.messageInput.scrollHeight))}px`;
  }

  function syncComposerDraftClass() {
    const input = els.messageInput;
    const composer = input?.closest(".composer.composer-chat");
    if (!composer || !input) return;
    const hasDraft = Boolean(String(input.value || "").trim());
    composer.classList.toggle("composer-has-draft", hasDraft);
    if (els.sendBtn) {
      // Premium feel: send reacts immediately when draft becomes valid.
      // sendMessage() already guards empty payload; this is purely interaction polish.
      if (!state.sending) els.sendBtn.disabled = !hasDraft;
      els.sendBtn.classList.toggle("xv-send-ready", hasDraft);
    }
  }

  function prefersReducedMotion() {
    try {
      return Boolean(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    } catch {
      return false;
    }
  }

  function getDetailsPanel(detailsEl) {
    if (!detailsEl) return null;
    // Prefer first non-summary direct child.
    for (const child of Array.from(detailsEl.children || [])) {
      if (child && child.tagName !== "SUMMARY") return child;
    }
    return detailsEl.querySelector(":scope > :not(summary)");
  }

  function animateDetailsToggle(detailsEl, willOpen) {
    const panel = getDetailsPanel(detailsEl);
    if (!panel) {
      detailsEl.open = Boolean(willOpen);
      return;
    }

    detailsEl.classList.add("xv-details-anim");
    panel.classList.add("xv-details-panel");

    if (prefersReducedMotion()) {
      detailsEl.open = Boolean(willOpen);
      return;
    }

    const ease = "cubic-bezier(.16,1,.3,1)";
    const duration = willOpen ? 170 : 150;

    // Cancel any in-flight animation.
    try {
      if (detailsEl._xvAnim) detailsEl._xvAnim.cancel();
    } catch {}

    if (willOpen) {
      // Measure expanded height.
      detailsEl.open = true;
      panel.style.overflow = "hidden";
      const target = panel.scrollHeight;
      panel.style.height = "0px";
      panel.style.opacity = "0.01";

      detailsEl._xvAnim = panel.animate(
        [{ height: "0px", opacity: 0.01, transform: "translateY(-1px)" }, { height: `${target}px`, opacity: 1, transform: "translateY(0px)" }],
        { duration, easing: ease, fill: "both" }
      );

      detailsEl._xvAnim.onfinish = () => {
        panel.style.height = "";
        panel.style.overflow = "";
        panel.style.opacity = "";
        detailsEl._xvAnim = null;
      };
      detailsEl._xvAnim.oncancel = () => {
        panel.style.height = "";
        panel.style.overflow = "";
        panel.style.opacity = "";
        detailsEl._xvAnim = null;
      };
      return;
    }

    // Closing: freeze current height, animate down, then remove open.
    panel.style.overflow = "hidden";
    const start = panel.getBoundingClientRect().height;
    panel.style.height = `${start}px`;
    panel.style.opacity = "1";

    detailsEl._xvAnim = panel.animate(
      [{ height: `${start}px`, opacity: 1, transform: "translateY(0px)" }, { height: "0px", opacity: 0.01, transform: "translateY(-1px)" }],
      { duration, easing: ease, fill: "both" }
    );

    detailsEl._xvAnim.onfinish = () => {
      detailsEl.open = false;
      panel.style.height = "";
      panel.style.overflow = "";
      panel.style.opacity = "";
      detailsEl._xvAnim = null;
    };
    detailsEl._xvAnim.oncancel = () => {
      panel.style.height = "";
      panel.style.overflow = "";
      panel.style.opacity = "";
      detailsEl._xvAnim = null;
    };
  }

  function bindPremiumDetailsInteractions() {
    if (document.documentElement.dataset.xvDetailsBound === "true") return;
    document.documentElement.dataset.xvDetailsBound = "true";

    document.addEventListener(
      "click",
      (event) => {
        const summary = event.target && event.target.closest ? event.target.closest("summary") : null;
        if (!summary) return;
        const detailsEl = summary.parentElement;
        if (!detailsEl || detailsEl.tagName !== "DETAILS") return;

        const cls = detailsEl.classList;
        const managed =
          cls.contains("details-wrap") ||
          cls.contains("assistant-meta-fold") ||
          cls.contains("auth-hints-fold") ||
          cls.contains("sidebar-more") ||
          cls.contains("stripe-more") ||
          cls.contains("composer-stripe-fold") ||
          cls.contains("notice-detail-fold");

        if (!managed) return;

        event.preventDefault();
        event.stopPropagation();
        animateDetailsToggle(detailsEl, !detailsEl.open);
      },
      true
    );
  }

  function syncComposerAriaDescribedBy() {
    const surface = document.getElementById("composerSurface");
    const line = els.composerStatusLine;
    if (!surface || !line) return;
    const hasDesc = Boolean(String(line.textContent || "").trim());
    if (hasDesc) surface.setAttribute("aria-describedby", "composerStatusLine");
    else surface.removeAttribute("aria-describedby");
  }

  function refreshComposerIdleHint() {
    if (!els.composerStatusLine || state.sending) return;
    const hasThread = Boolean(els.messages?.querySelector(".msg-group"));
    if (isClaudeShell() && hasThread) {
      const m = momentumLine();
      els.composerStatusLine.textContent = m ? m : "";
      syncComposerAriaDescribedBy();
      return;
    }
    if (isClaudeShell() && !hasThread) {
      els.composerStatusLine.textContent = "";
      syncComposerAriaDescribedBy();
      return;
    }
    if (!hasThread) {
      els.composerStatusLine.textContent = isAuthenticated()
        ? "Describe the case below."
        : "A few full runs available—no account needed.";
      syncComposerAriaDescribedBy();
      return;
    }
    if (!isAuthenticated()) {
      const left = Math.max(0, GUEST_USAGE_LIMIT - getGuestUsage());
      const rw = left === 1 ? "run" : "runs";
      const m = momentumLine();
      els.composerStatusLine.textContent =
        left > 0
          ? `${m ? `${m} ` : ""}Review the draft, then send another · ${left} preview ${rw} left`
          : "Preview finished — sign in under Access to continue.";
      syncComposerAriaDescribedBy();
      return;
    }
    {
      const m = momentumLine();
      els.composerStatusLine.textContent = m ? `${m} Next ticket?` : "Next ticket, or refine this thread.";
    }
    syncComposerAriaDescribedBy();
  }

  function setSending(value) {
    state.sending = Boolean(value);

    els.workspaceRoot?.classList.toggle("workspace-thinking", state.sending);
    els.workspaceRoot?.setAttribute("aria-busy", state.sending ? "true" : "false");

    if (els.composerStatusLine) {
      els.composerStatusLine.textContent = state.sending
        ? isClaudeShell()
          ? "Drafting…"
          : "Working on a reply…"
        : "";
      if (!state.sending) refreshComposerIdleHint();
      else syncComposerAriaDescribedBy();
      els.composerStatusLine.classList.toggle("composer-status-live", state.sending);
    }

    if (els.sendBtn) {
      els.sendBtn.disabled = state.sending;
      els.sendBtn.classList.toggle("send-btn--thinking", state.sending);
      els.sendBtn.innerHTML = state.sending
        ? '<span class="xalvion-sovereign-mark xv-spark-mark" aria-hidden="true"><span class="xv-signal-rays" aria-hidden="true"></span><span class="xv-spark-orbit" aria-hidden="true"></span></span>'
        : ICONS.send;
      els.sendBtn.setAttribute("aria-label", state.sending ? "Sending" : "Send message");
    }

    if (els.messageInput) {
      els.messageInput.disabled = state.sending;
      const composerSurface = els.messageInput.closest(".composer.composer-chat");
      composerSurface?.classList.toggle("composer-live", state.sending);
    }

    syncComposerDraftClass();

    updateStreamStatus(state.sending ? "Response: streaming" : "Response: ready");
    if (!state.sending) applyComposerInteractiveLock();
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
      const inner = data.detail && typeof data.detail === "object" && !Array.isArray(data.detail) ? data.detail : data;
      syncGuestEntitlementFromServerPayload(inner);
      pushLimitMessage(true);
      applyComposerInteractiveLock();
      throw new Error(detailFromApiBody(data) || "Plan limit reached. Upgrade to continue.");
    }

    if (res.status === 400) {
      const inner = data.detail && typeof data.detail === "object" && !Array.isArray(data.detail) ? data.detail : null;
      if (inner && inner.code === "preview_client_required") {
        ensurePreviewClientId();
        throw new Error(inner.message || "Reload the workspace and try again.");
      }
    }

    if (!res.ok) {
      throw new Error(detailFromApiBody(data) || `Support request failed (${res.status}).`);
    }
    return data;
  }

  async function handleStreamReply(payload, row) {
    const res = await fetch(`${API}/support/stream`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify(payload)
    });

    if (!res.ok || !res.body) {
      const data = await parseApiResponse(res);
      if (res.status === 402) {
        const inner = data.detail && typeof data.detail === "object" && !Array.isArray(data.detail) ? data.detail : data;
        syncGuestEntitlementFromServerPayload(inner);
        pushLimitMessage(true);
        applyComposerInteractiveLock();
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
          // Keep status generic. Do not expose internal pipeline stages/labels to the UI.
          updateStreamStatus("Response: working");
        }

        if (item.event === "result") {
          finalData = item.data;
          const p2 = getPhase2();
          if (p2?.agentStore) {
            try {
              p2.agentStore.set({
                currentState: "streaming",
                currentResult: item.data,
                currentDecision: item.data?.decision || item.data?.sovereign_decision || null,
              });
            } catch {
              /* no-op */
            }
          }
        }

        if (item.event === "usage_warning" && item.data) {
          applyUsageWarningFromStream(item.data);
        }

        if (item.event === "done") {
          const p2 = getPhase2();
          if (p2?.agentStore && finalData) {
            try {
              p2.agentStore.set({ currentState: "done", currentResult: finalData });
            } catch {
              /* no-op */
            }
          }
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

    if (finalData && !isAuthenticated() && isPreviewExhaustedPayload(finalData)) {
      syncGuestEntitlementFromServerPayload(finalData);
      applyComposerInteractiveLock();
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
    let card = els.latestRunRailCard || document.getElementById("latestRunRailCard");
    if (card) return card;

    card = document.getElementById("xalvionOpsCard");
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

  function ensureOutcomeIntelCard() {
    let card = document.getElementById("xalvionOutcomeIntelCard");
    if (card) return card;

    card = document.createElement("div");
    card.id = "xalvionOutcomeIntelCard";
    card.className = "outcome-intel-card";
    card.innerHTML = `
      <div class="outcome-intel-head">
        <div>
          <div class="panel-title">Outcome intelligence</div>
          <div class="panel-copy">What happened after actions — quality, value preserved, and stability signals.</div>
        </div>
      </div>

      <div class="outcome-intel-latest" id="outcomeIntelLatest">
        <div class="outcome-intel-latest-row">
          <div class="outcome-tier-badge tier-unknown" id="outcomeIntelTier">Outcome</div>
          <div class="outcome-intel-headline" id="outcomeIntelHeadline">No outcomes recorded yet.</div>
        </div>
        <div class="outcome-intel-badges" id="outcomeIntelBadges"></div>
        <div class="outcome-intel-money" id="outcomeIntelMoney"></div>
      </div>

      <div class="outcome-metric-grid" id="outcomeIntelGrid"></div>
      <div class="outcome-insights" id="outcomeIntelInsights"></div>
      <div class="outcome-pattern" id="outcomeIntelPattern"></div>
    `;

    if (els.railInner) els.railInner.appendChild(card);
    else if (els.usageCard?.parentElement) els.usageCard.parentElement.appendChild(card);

    return card;
  }

  function syncOutcomeIntelligenceRail(dashboardStats = null) {
    const d = dashboardStats && typeof dashboardStats === "object" ? dashboardStats : state.dashboardStats || {};
    const raw = d.outcome_intelligence && typeof d.outcome_intelligence === "object" ? d.outcome_intelligence : null;
    ensureOutcomeIntelCard();

    const tierEl = document.getElementById("outcomeIntelTier");
    const headlineEl = document.getElementById("outcomeIntelHeadline");
    const badgesEl = document.getElementById("outcomeIntelBadges");
    const moneyEl = document.getElementById("outcomeIntelMoney");
    const gridEl = document.getElementById("outcomeIntelGrid");
    const insightsEl = document.getElementById("outcomeIntelInsights");
    const patternEl = document.getElementById("outcomeIntelPattern");

    const fmt = globalThis.__XALVION_FORMAT__;
    const norm =
      fmt?.normalizeOutcomeIntelligence
        ? fmt.normalizeOutcomeIntelligence(raw)
        : { latest: null, summary: {}, insights: [], bestPattern: null };

    const latest = norm.latest;
    const tier = String(latest?.tier || "unknown").toLowerCase();
    const tierLabel = fmt?.formatOutcomeTier ? fmt.formatOutcomeTier(tier) : tier ? `${tier} outcome` : "Outcome unavailable";

    if (tierEl) {
      tierEl.textContent = tierLabel;
      tierEl.className = `outcome-tier-badge tier-${tier || "unknown"}`;
    }
    if (headlineEl) {
      const hl = String(latest?.headline || "").trim();
      headlineEl.textContent = hl || (raw ? "Outcome recorded." : "No outcomes recorded yet.");
    }

    if (badgesEl) {
      badgesEl.innerHTML = "";
      const badges = Array.isArray(latest?.badges) ? latest.badges : [];
      for (const b of badges.slice(0, 6)) {
        const t = String(b || "").trim();
        if (!t) continue;
        const chip = document.createElement("span");
        chip.className = "meta-chip";
        chip.textContent = t.replaceAll("_", " ");
        badgesEl.appendChild(chip);
      }
    }

    if (moneyEl) {
      const refund = Number(latest?.money?.refund || 0) || 0;
      const credit = Number(latest?.money?.credit || 0) || 0;
      const bits = [];
      if (refund > 0) bits.push(`Refund ${formatMoney(refund)}`);
      if (credit > 0) bits.push(`Credit ${formatMoney(credit)}`);
      moneyEl.textContent = bits.length ? bits.join(" · ") : "";
      moneyEl.classList.toggle("is-hidden", !bits.length);
    }

    if (gridEl) {
      gridEl.innerHTML = "";
      const s = norm.summary || {};
      const keys = ["excellent", "good", "neutral", "bad", "ticket_reopened", "refund_reversed", "dispute_filed"];
      for (const k of keys) {
        const v = Number(s[k] || 0) || 0;
        if (v <= 0 && (k === "refund_reversed" || k === "dispute_filed")) continue;
        const cell = document.createElement("div");
        cell.className = "outcome-metric";
        const label = fmt?.formatOutcomeMetricLabel ? fmt.formatOutcomeMetricLabel(k) : k;
        cell.innerHTML = `
          <div class="outcome-metric-label">${escapeHtml(label)}</div>
          <div class="outcome-metric-value">${escapeHtml(String(v))}</div>
        `;
        gridEl.appendChild(cell);
      }

      const hasAny = gridEl.children.length > 0;
      gridEl.classList.toggle("is-hidden", !hasAny);
    }

    if (insightsEl) {
      insightsEl.innerHTML = "";
      const lines = Array.isArray(norm.insights) ? norm.insights : [];
      for (const line of lines.slice(0, 3)) {
        const t = String(line || "").trim();
        if (!t) continue;
        const row = document.createElement("div");
        row.className = "outcome-insight";
        row.textContent = t;
        insightsEl.appendChild(row);
      }
      insightsEl.classList.toggle("is-hidden", insightsEl.children.length === 0);
    }

    if (patternEl) {
      const bp = norm.bestPattern;
      if (bp && bp.pattern_key) {
        const pk = fmt?.formatPatternKey ? fmt.formatPatternKey(bp.pattern_key) : String(bp.pattern_key);
        const exp = String(bp.expectation || "medium").toLowerCase();
        const expLabel = exp === "high" ? "high expectation" : exp === "low" ? "low expectation" : "medium expectation";
        patternEl.innerHTML = `<span class="outcome-pattern-label">Best pattern</span> ${escapeHtml(pk)} <span class="outcome-pattern-exp">${escapeHtml(expLabel)}</span>`;
        patternEl.classList.remove("is-hidden");
      } else {
        patternEl.textContent = "";
        patternEl.classList.add("is-hidden");
      }
    }
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
      const line = `Operator system · ${posture} · ${risk} risk · value surfaced ${value}. ${reason}`;
      const sub = latestNarrative.querySelector(".ops-narrative-text");
      if (sub) sub.textContent = line;
      else latestNarrative.innerHTML = `${ICONS.spark}<span class="ops-narrative-text">${escapeHtml(line)}</span>`;
    }

    if (els.railRunSummary) {
      const it = String(
        data.issue_type || data.meta?.issue_type || data.decision?.issue_type || "general_support"
      ).replace(/_/g, " ");
      els.railRunSummary.textContent = `${it} · ${displayActionLabel(data)} · conf ${formatMetric(data.confidence || 0, 2)}`;
    }
    syncApprovalRail(data);
  }

  function syncApprovalRail(override) {
    const wrap = els.approvalRailWrap;
    const sum = els.approvalRailSummary;
    const meta = els.approvalRailMeta;
    if (!wrap || !sum) return;
    if (override === null) {
      wrap.hidden = true;
      if (meta) meta.innerHTML = "";
      sum.textContent = "No approval gate on the latest run.";
      return;
    }
    const target = override !== undefined ? override : state.latestRun;
    if (!target || typeof target !== "object") {
      wrap.hidden = true;
      if (meta) meta.innerHTML = "";
      sum.textContent = "No approval gate on the latest run.";
      return;
    }
    const approval = getApprovalContext(target);
    const pending = Boolean(approval.requiresApproval && !approval.approved);
    if (!pending) {
      wrap.hidden = true;
      if (meta) meta.innerHTML = "";
      sum.textContent = "No approval gate on the latest run.";
      return;
    }
    wrap.hidden = false;
    const action = approval.action && approval.action !== "none" ? approval.action : "prepared action";
    const amt = approval.amount > 0 ? formatMoney(approval.amount) : "";
    sum.textContent = `Execution is held — ${action}${amt ? ` (${amt})` : ""} requires operator approval before it ships.`;
    if (meta) {
      meta.innerHTML = "";
      const chip = (text, ok) => {
        const s = document.createElement("span");
        s.className = `approval-rail-chip${ok ? " is-ok" : " is-muted"}`;
        s.textContent = text;
        meta.appendChild(s);
      };
      chip(approval.canApprove ? "You can approve from the canvas" : "Sign in as ticket owner to approve", approval.canApprove);
      chip(approval.ticketId ? `Ticket #${approval.ticketId}` : "No ticket id on this run", Boolean(approval.ticketId));

      // Governor visibility (additive): show reason, risk chip, and next step when present.
      try {
        const fmt = globalThis.__XALVION_FORMAT__;
        const gov = fmt?.deriveGovernorPresentation ? fmt.deriveGovernorPresentation(target) : null;
        if (gov && gov.mode && gov.mode !== "unknown") {
          const riskText = String(gov.riskScoreLabel || gov.riskLabel || "").trim();
          const reason = String(gov.summary || "").trim();
          const next = String(gov.nextStep || "").trim();
          if (riskText) chip(riskText, false);
          if (reason) chip(reason.length > 90 ? `${reason.slice(0, 90)}…` : reason, false);
          if (next) chip(next, false);
        }
      } catch {}
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

    if (!enforceWorkspaceLimit()) return;
    const startedAt =
      globalThis.performance && typeof globalThis.performance.now === "function" ? globalThis.performance.now() : Date.now();

    ensureInjectedStyles();
    clearEmptyState();

    addUserMessage(payload.message);

    if (els.messageInput) {
      els.messageInput.value = "";
      autoResizeTextarea();
      saveDraft("");
      syncComposerDraftClass();
    }

    const row = addAssistantMessage("");
    const replyNode = getAssistantCopyNode(row);
    if (replyNode) replyNode.innerHTML = createTypingMarkup();

    setSending(true);
    setNotice("info", "Running support case", "Xalvion is preparing a response.");

    try {
      let data = null;

      try {
        data = await handleStreamReply(payload, row);
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
        if (isPreviewExhaustedPayload(data)) {
          syncGuestEntitlementFromServerPayload(data);
          pushLimitMessage(true);
          applyComposerInteractiveLock();
          authDebugLog("support_preview_exhausted", data.code || data.tool_status);
        } else {
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
      }

      if (!data) throw new Error("No response returned.");

      data = normalizeWorkspaceResult(data);
      state.latestRun = data;
      setLastSessionNow();

      const replyText = data.reply || data.response || data.final || "No response returned.";
      setAssistantCopy(row, replyText);
      const elapsedMs =
        (globalThis.performance && typeof globalThis.performance.now === "function" ? globalThis.performance.now() : Date.now()) -
        startedAt;
      setPreparedMeta(row, elapsedMs / 1000);

      const footer = getAssistantFooterNode(row);
      const briefSlot = row.querySelector("[data-slot='brief']");
      if (footer) {
        footer.innerHTML = "";
        const toolsWrap = document.createElement("div");
        addCopyControl(toolsWrap, replyText, row);
        footer.appendChild(toolsWrap);
        footer.appendChild(wrapAssistantMetaFold(createMetaRow(data)));

        if (briefSlot) {
          briefSlot.innerHTML = "";
          const approvalBanner = createApprovalBanner(data);
          if (approvalBanner) briefSlot.appendChild(approvalBanner);
          briefSlot.appendChild(createDetailsPanel(data));
        } else {
          const approvalBanner = createApprovalBanner(data);
          const details = createDetailsPanel(data);
          const host = footer.parentElement;
          if (approvalBanner) host?.appendChild(approvalBanner);
          host?.appendChild(details);
        }
        mountOperatorDecisionPanel(row, data, replyText);
      }
      row.querySelector(".msg-card")?.removeAttribute("data-placeholder");
      syncReplyReinforcement(row);
      pulsePreparedReplyReveal(row);
      syncAssistantContextLine(row, data);

      updateStatsFromResult(data);
      updateRevenueCard(data);
      updateLatestRunCard(data);
      updateSystemNarrative(data);
      // Refresh recent tickets quietly (return trigger).
      // Prefer server truth when available, but keep working if offline.
      hydrateRecentTickets().catch(() => {});

      // Server can send limit/overage intelligence. Apply it before re-rendering usage surfaces.
      applyUsageWarningFromStream(data);
      if (data && typeof data === "object") {
        const b = Number(data.billable_usage);
        if (Number.isFinite(b)) state.billableUsage = Math.max(0, b);
        const w = Number(data.within_included);
        if (Number.isFinite(w)) state.withinIncluded = Math.max(0, w);
      }

      const hasServerUsage = Number.isFinite(Number(data.usage));
      const planTier = data.tier || state.tier;
      const planLimit = Number(data.plan_limit || data.limit || state.limit || GUEST_USAGE_LIMIT);
      const planRemaining = Number.isFinite(Number(data.remaining)) ? Number(data.remaining) : null;
      const responseUsername = String(data.username || "").trim().toLowerCase();
      const responseIsGuest = !responseUsername || responseUsername === "guest" || responseUsername === "dev_user";

      if (!isAuthenticated() && responseIsGuest) {
        const nextGuestUsage = hasServerUsage
          ? Math.max(0, Number(data.usage || 0))
          : getGuestUsage() + 1;
        const cap = Number(data.plan_limit || data.limit || GUEST_USAGE_LIMIT);
        const safeCap = Number.isFinite(cap) && cap > 0 ? cap : GUEST_USAGE_LIMIT;
        const rem = Number.isFinite(Number(data.remaining))
          ? Math.max(0, Number(data.remaining))
          : Math.max(0, safeCap - nextGuestUsage);

        updatePlanUI("free", nextGuestUsage, safeCap, rem);
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
      const limitReachedAfterRun = limitAfterRun > 0 && usageAfterRun >= limitAfterRun;

      updateTopbarStatus();
      setNotice(data.action === "review" ? "warning" : "success", noticeTitleForResult(data), replyText);

      if (limitReachedAfterRun) {
        pushLimitMessage(true);
      } else {
        state.lastLimitNoticeKey = "";
      }
    } catch (error) {
      const errText =
        (error && error.message) ||
        "Something went wrong while processing this support request.";
      setAssistantCopy(row, errText);
      pulsePreparedReplyReveal(row);
      syncAssistantContextLine(row, null);
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
    try {
      localStorage.removeItem(PREVIEW_CLIENT_KEY);
    } catch {
      /* no-op */
    }
    ensurePreviewClientId();
    updatePlanUI("free", getGuestUsage(), GUEST_USAGE_LIMIT, Math.max(0, GUEST_USAGE_LIMIT - getGuestUsage()));
    applyComposerInteractiveLock();
    const demoText = "A customer says: I was charged twice for one order and wants it fixed today.";
    if (els.messageInput) {
      els.messageInput.value = demoText;
      autoResizeTextarea();
      saveDraft(demoText);
      syncComposerDraftClass();
      els.messageInput.focus();
    }
    setNotice(
      "info",
      "Preview refreshed",
      "Guest counters and preview client id were reset — you get a fresh server-side preview quota for local testing."
    );
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

  function setCtaLoading(btn, loading, loadingLabel) {
    if (!(btn instanceof HTMLButtonElement)) return;
    const labelEl = btn.querySelector("span") || btn;
    if (loading) {
      if (!btn.dataset.ctaOriginalLabel) btn.dataset.ctaOriginalLabel = labelEl.textContent || "";
      btn.disabled = true;
      if (loadingLabel) labelEl.textContent = loadingLabel;
      btn.setAttribute("aria-busy", "true");
      return;
    }
    const original = btn.dataset.ctaOriginalLabel;
    if (typeof original === "string" && original.length) labelEl.textContent = original;
    btn.disabled = false;
    btn.removeAttribute("aria-busy");
    delete btn.dataset.ctaOriginalLabel;
  }

  function setAccessMode(mode) {
    const m = String(mode || "account").toLowerCase();
    const card = document.getElementById("authAccessCard");
    if (card) card.dataset.authMode = m;
    if (m === "signup") {
      setNotice("info", "Create your account", "Choose a username + password to save your workspace and continue on Free.");
    } else if (m === "login") {
      setNotice("info", "Log in", "Enter your existing account credentials to continue.");
    }
  }

  async function startUpgradeFromButton(btn, tier) {
    if (!(btn instanceof HTMLButtonElement)) return;
    const desired = String(tier || "").toLowerCase();
    if (!desired) return;
    if (btn.disabled || btn.hidden) return;

    setCtaLoading(btn, true, "Opening checkout…");
    try {
      await upgradePlan(desired);
    } catch (err) {
      setNotice("error", "Upgrade failed", err?.message || "Could not open checkout.");
    } finally {
      setCtaLoading(btn, false);
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
      syncCommandStripCapacity();
      syncPhase2Stores();
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
      syncCommandStripCapacity();
      syncPhase2Stores();
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
      updateRefundUI();
      syncAnalyticsRail();
      syncOutcomeIntelligenceRail(data);
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
    syncApprovalRail(null);
    if (els.railRunSummary) els.railRunSummary.textContent = "Issue type, action, confidence — updates after each support run.";
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

  const RAIL_BRIEF_KEY = "xalvion-rail-brief-v2";

  function syncSidebarCapabilityPanels() {
    const crmNew = Number(state.crmSummary?.new ?? 0);
    const crmDue = Number(state.crmSummary?.due_followups ?? 0);
    const crmDueToday = Number(state.crmDailySummary?.due_followups ?? 0);
    const crmClosedToday = Number(state.crmDailySummary?.closed_today ?? 0);
    if (els.sidebarCrmNew) setText(els.sidebarCrmNew, crmNew > 0 ? String(crmNew) : "—");
    if (els.sidebarCrmDue) setText(els.sidebarCrmDue, crmDue > 0 ? String(crmDue) : "—");
    if (els.sidebarCrmTodayDue) setText(els.sidebarCrmTodayDue, crmDueToday > 0 ? String(crmDueToday) : "—");
    if (els.sidebarCrmTodayClosed) setText(els.sidebarCrmTodayClosed, crmClosedToday > 0 ? String(crmClosedToday) : "—");
    const t = state.revenueMetrics?.totals || {};
    const revenue = Number(t.revenue || 0);
    const replyRate = Number(t.reply_rate || 0);
    const winRate = Number(t.win_rate || 0);
    if (els.sidebarRevenueTotal) setText(els.sidebarRevenueTotal, revenue > 0 ? `$${revenue.toFixed(2)}` : "Waiting for first run");
    if (els.sidebarRevenueReply) setText(els.sidebarRevenueReply, replyRate > 0 ? `${replyRate.toFixed(1)}%` : "Populates after runs");
    if (els.sidebarRevenueWin) setText(els.sidebarRevenueWin, winRate > 0 ? `${winRate.toFixed(1)}%` : "Outcome tracking idle");
    if (els.sidebarRevenueSource) setText(els.sidebarRevenueSource, revenue > 0 ? (state.revenueMetrics?.best_source || "manual") : "No activity yet");
  }

  function initWorkspaceChromeShell() {
    initSidebarCollapse();
    initSidebarNav();
    initRailBriefToggles();
    initAccessDrawer();
    els.commandAuthChip?.addEventListener("click", () => openAccessDrawer("account"));
    els.accessPlansLink?.addEventListener("click", () => {
      closeAccessDrawer();
      setSurface("plans");
      const tab = document.getElementById("sidebarTabPlans");
      tab?.click?.();
    });

    if (!document.documentElement.dataset.xvAccessButtonsBound) {
      document.documentElement.dataset.xvAccessButtonsBound = "1";
      document.addEventListener("click", (e) => {
        const t = e.target;
        if (!(t instanceof Element)) return;
        const btn = t.closest("[data-open-access]");
        if (!btn) return;
        e.preventDefault();
        e.stopImmediatePropagation();
        const mode = String(btn.getAttribute("data-open-access") || "account").toLowerCase();
        openAccessDrawer("account");
        setAccessMode(mode);
        window.setTimeout(() => {
          els.usernameInput?.focus?.();
        }, 90);
      }, true);
    }
  }

  function initAccessDrawer() {
    const drawer = els.accessDrawer;
    if (!drawer || drawer.dataset.accessDrawerBound) return;
    drawer.dataset.accessDrawerBound = "1";

    const onBackdrop = (e) => {
      if (e.target === drawer) closeAccessDrawer();
    };
    drawer.addEventListener("click", onBackdrop);
    drawer.addEventListener("mousedown", onBackdrop);

    els.closeAccessDrawerBtn?.addEventListener("click", closeAccessDrawer);

    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && drawer.classList.contains("open")) closeAccessDrawer();
    });
  }

  function initSidebarCollapse() {
    const shell = els.sidebarShell;
    if (!shell || shell.dataset.sidebarCollapseBound) return;
    shell.dataset.sidebarCollapseBound = "1";

    const btn = document.getElementById("sidebarCollapseBtn");
    const KEY = "xalvion-sidebar-collapsed";

    const apply = (collapsed) => {
      const on = Boolean(collapsed);
      shell.dataset.sidebarCollapsed = on ? "true" : "false";
      if (document.body?.dataset?.ui === "claude" && btn) {
        btn.setAttribute("data-cld-tip", on ? "Expand sidebar" : "Collapse sidebar");
      }
      try {
        localStorage.setItem(KEY, on ? "1" : "0");
      } catch {}
    };

    let initial = false;
    try {
      const raw = localStorage.getItem(KEY);
      if (document.body?.dataset?.ui === "claude") {
        initial = raw === null ? false : raw === "1";
      } else {
        initial = (raw || "0") === "1";
      }
    } catch {
      initial = false;
    }
    apply(initial);

    btn?.addEventListener("click", () => {
      const isCollapsed = shell.dataset.sidebarCollapsed === "true";
      apply(!isCollapsed);
    });
  }

  function initSidebarNav() {
    const shell = els.sidebarShell;
    const tabs = shell ? shell.querySelectorAll("[data-sidebar-tab]") : [];
    if (!shell || !tabs.length) return;
    if (shell.dataset.sidebarNavBound) return;
    shell.dataset.sidebarNavBound = "1";

    const expandIfClaudeRail = () => {
      if (!isClaudeShell()) return;
      if (shell.dataset.sidebarCollapsed !== "true") return;
      shell.dataset.sidebarCollapsed = "false";
      try {
        localStorage.setItem("xalvion-sidebar-collapsed", "0");
      } catch {}
      const btn = document.getElementById("sidebarCollapseBtn");
      if (btn && document.body?.dataset?.ui === "claude") {
        btn.setAttribute("data-cld-tip", "Collapse sidebar");
      }
    };

    const applyTab = (key) => {
      const normalized = String(key || "workspace").toLowerCase();
      tabs.forEach((btn) => {
        const on = String(btn.getAttribute("data-sidebar-tab") || "").toLowerCase() === normalized;
        btn.classList.toggle("is-active", on);
        btn.setAttribute("aria-selected", on ? "true" : "false");
      });
      shell.dataset.sidebarActive = normalized;
    };

    tabs.forEach((btn) => {
      btn.addEventListener("click", (e) => {
        expandIfClaudeRail();
        const key = btn.getAttribute("data-sidebar-tab") || "workspace";
        if (key === "account") {
          e.preventDefault();
          e.stopPropagation();
          openAccessDrawer("account");
          return;
        }
        e.preventDefault();
        e.stopPropagation();
        applyTab(key);
        setSurface(key);
      });
    });

    let initial = "workspace";
    try {
      const saved = sessionStorage.getItem("xalvion-surface");
      if (saved) initial = saved;
    } catch {}
    applyTab(initial);
    setSurface(initial);

    els.sidebarJumpCrmBtn?.addEventListener("click", () => {
      els.crmCard?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
    els.sidebarJumpRevenueBtn?.addEventListener("click", () => {
      els.revenueCard?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
  }

  function initRailBriefToggles() {
    const root = els.railInner;
    if (!root || root.dataset.railBriefBound) return;
    root.dataset.railBriefBound = "1";

    let saved = {};
    try {
      saved = JSON.parse(sessionStorage.getItem(RAIL_BRIEF_KEY) || "{}") || {};
    } catch {
      saved = {};
    }

    root.querySelectorAll(".rail-brief").forEach((brief) => {
      const key = brief.getAttribute("data-rail-brief") || brief.id || "rail";
      const btn = brief.querySelector(".rail-brief-toggle");
      if (!btn) return;

      const openDefault = brief.classList.contains("is-open");
      const wantOpen = typeof saved[key] === "boolean" ? saved[key] : openDefault;

      const setOpen = (open) => {
        brief.classList.toggle("is-open", open);
        btn.setAttribute("aria-expanded", open ? "true" : "false");
        saved[key] = open;
        try {
          sessionStorage.setItem(RAIL_BRIEF_KEY, JSON.stringify(saved));
        } catch {}
      };

      setOpen(wantOpen);
      btn.addEventListener("click", () => setOpen(!brief.classList.contains("is-open")));
    });
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
    syncSidebarCapabilityPanels();
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
    syncSidebarCapabilityPanels();
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
    syncPhase2Stores();
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
    els.accessPlansLink?.addEventListener("click", () => {
      focusPlansPanel();
    });
    els.newChatBtn?.addEventListener("click", () => {
      resetWorkspaceThread();
      setNotice("info", "New thread", "Cleared. Paste the next ticket whenever you’re ready.");
    });

    els.messageInput?.addEventListener("input", () => {
      autoResizeTextarea();
      saveDraft(els.messageInput.value || "");
      syncComposerDraftClass();
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

    els.sidebarShell?.addEventListener("focusin", (e) => {
      if (e.target && e.target.closest && e.target.closest("[data-upgrade]")) refreshUpgradeValueSummary();
    });
    els.sidebarShell?.addEventListener("click", (e) => {
      const btn = e.target && e.target.closest ? e.target.closest("[data-upgrade]") : null;
      if (!btn || !els.sidebarShell?.contains(btn)) return;
      if (btn.hidden || btn.disabled) return;
      e.preventDefault();
      refreshUpgradeValueSummary();
      upgradePlan(btn.dataset.upgrade || "");
    });

    // Plans surface CTAs live outside the sidebar; wire them globally.
    if (!document.documentElement.dataset.xvPlansUpgradeBound) {
      document.documentElement.dataset.xvPlansUpgradeBound = "1";
      document.addEventListener(
        "click",
        (e) => {
          const t = e.target;
          if (!(t instanceof Element)) return;
          const btn = t.closest("[data-upgrade]");
          if (!(btn instanceof HTMLButtonElement)) return;
          if (btn.hidden || btn.disabled) return;
          e.preventDefault();
          e.stopImmediatePropagation();
          refreshUpgradeValueSummary();
          startUpgradeFromButton(btn, btn.dataset.upgrade || "");
        },
        true
      );
    }

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

    els.workspaceRoot?.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-fill]");
      if (!btn || !els.workspaceRoot.contains(btn)) return;
      applyFillFromButton(btn);
    });

    els.workspaceRoot?.addEventListener("dblclick", async (e) => {
      const btn = e.target.closest("[data-fill]");
      if (!btn || !els.workspaceRoot.contains(btn)) return;
      const label = String(btn.textContent || "").trim().toLowerCase();
      if (label.includes("duplicate charge")) {
        await runWorkspaceRefundFromInput();
      }
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
    globalThis.addEventListener?.("xalvion:phase2-ready", () => {
      syncPhase2Stores();
      syncAnalyticsRail();
      syncOutcomeIntelligenceRail();
    });

    let phase2Core = null;
    try {
      if (typeof globalThis.createPhase2Core === "function") {
        phase2Core = globalThis.createPhase2Core({ fetchImpl: fetch.bind(globalThis) });
      }
    } catch {
      phase2Core = null;
    }
    if (phase2Core) {
      globalThis.__XALVION_FORMAT__ = phase2Core.format;
      globalThis.__XALVION_PHASE2_CORE__ = phase2Core;
    }

    ensureInjectedStyles();
    ensureCrmStyles();
    ensurePreviewClientId();
    hydrateStripeCallbackState();
    buildKeyboardOverlay();
    ensureOpsCard();
    ensureOutcomeIntelCard();
    bindEvents();
    bindPremiumDetailsInteractions();
    initWorkspaceChromeShell();
    try {
      const url = new URL(window.location.href);
      const surface = String(url.searchParams.get("surface") || "").toLowerCase();
      if (surface && ["workspace", "plans", "integrations", "crm", "revenue", "more"].includes(surface)) {
        setSurface(surface);
        document.getElementById(`sidebarTab${surface.charAt(0).toUpperCase()}${surface.slice(1)}`)?.click?.();
        url.searchParams.delete("surface");
        window.history.replaceState(
          {},
          document.title,
          url.pathname + (url.searchParams.toString() ? `?${url.searchParams.toString()}` : "") + url.hash
        );
      }
    } catch {}

    if (isClaudeShell()) {
      if (els.composerStatusLine) els.composerStatusLine.textContent = "";
      if (els.messageInput) els.messageInput.placeholder = "Paste a ticket or describe the issue…";
      syncComposerAriaDescribedBy();
    }

    const draft = loadDraft();
    if (els.messageInput && draft) {
      els.messageInput.value = draft;
    }

    autoResizeTextarea();
    syncComposerDraftClass();
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
    hydrateRecentTickets().catch(() => {});
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
      setNotice("info", "Ready when you are", "Paste a ticket below to see your first draft.");
    } else {
      setNotice("success", "Workspace synced", `Signed in as ${state.username}. The operator workspace is ready.`);
    }

    syncWorkspaceLayoutMode();
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
