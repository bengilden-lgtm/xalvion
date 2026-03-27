(() => {
  "use strict";

  const API = "";
  const TOKEN_KEY = "xalvion_token";
  const USER_KEY = "xalvion_user";
  const TIER_KEY = "xalvion_tier";

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
    upgradeButtons: Array.from(document.querySelectorAll("[data-upgrade]")),
    chips: Array.from(document.querySelectorAll("[data-fill]")),
    paymentIntentInput: document.getElementById("paymentIntentInput")
  };

  const state = {
    token: localStorage.getItem(TOKEN_KEY) || "",
    username: localStorage.getItem(USER_KEY) || "",
    tier: localStorage.getItem(TIER_KEY) || "free",
    usage: 0,
    limit: Infinity,
    remaining: Infinity,
    actions: 0,
    sending: false,
    latestAction: "",
    latestStatus: ""
  };

  const ICONS = {
    copy: `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="5" width="8" height="8" rx="1.5"/><path d="M3 11V3a1 1 0 011-1h8"/></svg>`,
    send: `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M13.5 2.5L7 9M13.5 2.5L9 13.5 7 9l-4.5-2 11-5z"/></svg>`,
    check: `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 8l3.5 3.5L13 4"/></svg>`,
    refund: `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M13 5a5 5 0 10-1.4 3.46"/><path d="M13 1.5V5h-3.5"/><path d="M5.2 8h5.6"/><path d="M5.8 10.5h4.4"/></svg>`,
    credit: `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="12" height="10" rx="2"/><path d="M2 6.5h12"/><path d="M5 10h2.5"/></svg>`,
    review: `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="5.5"/><path d="M8 5.2v3.2"/><path d="M8 10.9h.01"/></svg>`,
    status: `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12.5h10"/><path d="M4.5 10V6.5"/><path d="M8 10V4.5"/><path d="M11.5 10V7.5"/></svg>`,
    sparkle: `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M8 1.8l1.2 3 3 1.2-3 1.2-1.2 3-1.2-3-3-1.2 3-1.2 1.2-3Z"/><path d="M12.4 10.8l.6 1.6 1.6.6-1.6.6-.6 1.6-.6-1.6-1.6-.6 1.6-.6.6-1.6Z"/></svg>`,
    crown: `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12.5h12"/><path d="M3 12.5 2.2 5.5l3.4 2.4L8 3l2.4 4.9 3.4-2.4-.8 7"/></svg>`,
    bolt: `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M8.8 1.5 3.5 8h3.2L6.1 14.5 12.5 7.2H9.2l-.4-5.7Z"/></svg>`,
    arrow: `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 8h10"/><path d="M9.5 4.5 13 8l-3.5 3.5"/></svg>`
  };

  function ensureInjectedStyles() {
    if (document.getElementById("xalvion-runtime-styles")) return;

    const style = document.createElement("style");
    style.id = "xalvion-runtime-styles";
    style.textContent = `
      .action-visibility{
        display:none;
        margin:16px 0 0 20px;
        border-radius:18px;
        border:1px solid rgba(255,255,255,.07);
        background:
          linear-gradient(180deg, rgba(255,255,255,.032), rgba(255,255,255,.018)),
          radial-gradient(circle at 88% 18%, rgba(139,111,255,.08), transparent 28%);
        box-shadow:0 12px 34px rgba(0,0,0,.11), inset 0 1px 0 rgba(255,255,255,.03);
        overflow:hidden;
        animation:xalvionReveal .26s cubic-bezier(.22,1,.36,1) both;
        position:relative;
      }

      .action-visibility::before{
        content:"";
        position:absolute;
        left:0;
        top:0;
        bottom:0;
        width:2px;
        background:linear-gradient(180deg, rgba(255,255,255,.08), rgba(255,255,255,0));
        opacity:.7;
      }

      .action-visibility.show{display:block;}
      .action-visibility.success::before{background:linear-gradient(180deg, rgba(110,231,183,.9), rgba(110,231,183,.14));}
      .action-visibility.warning::before{background:linear-gradient(180deg, rgba(252,211,77,.92), rgba(252,211,77,.16));}
      .action-visibility.info::before{background:linear-gradient(180deg, rgba(96,165,250,.92), rgba(96,165,250,.16));}

      .action-visibility-head{
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:12px;
        padding:11px 12px 10px;
        border-bottom:1px solid rgba(255,255,255,.05);
      }

      .action-visibility-title{display:flex;align-items:center;gap:9px;min-width:0;}
      .action-visibility-icon-wrap{
        width:24px;height:24px;border-radius:9px;flex:0 0 24px;display:flex;align-items:center;justify-content:center;
        background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.07);color:rgba(228,234,252,.92);
      }
      .action-visibility.success .action-visibility-icon-wrap{
        background:rgba(52,211,153,.08);border-color:rgba(52,211,153,.18);color:rgba(110,231,183,.96);
      }
      .action-visibility.warning .action-visibility-icon-wrap{
        background:rgba(245,158,11,.08);border-color:rgba(245,158,11,.18);color:rgba(252,211,77,.98);
      }
      .action-visibility.info .action-visibility-icon-wrap{
        background:rgba(59,130,246,.08);border-color:rgba(59,130,246,.18);color:rgba(147,197,253,.98);
      }
      .action-visibility-icon-wrap svg{width:12px;height:12px;}
      .action-visibility-title-stack{min-width:0;display:flex;flex-direction:column;gap:2px;}
      .action-visibility-title-text{
        font-size:11px;letter-spacing:.14em;text-transform:uppercase;font-weight:800;color:rgba(188,201,238,.62);white-space:nowrap;
      }
      .action-visibility-kicker{
        font-size:12px;font-weight:700;color:rgba(234,240,255,.94);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
      }
      .action-visibility-badge{
        font-size:10px;font-weight:700;letter-spacing:.10em;text-transform:uppercase;color:rgba(218,227,252,.78);
        border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.04);border-radius:999px;padding:4px 8px;white-space:nowrap;
      }
      .action-visibility-body{display:flex;flex-direction:column;gap:9px;padding:13px 12px 12px;}
      .action-visibility-line{font-size:14px;line-height:1.65;color:rgba(236,242,255,.96);}
      .action-visibility-sub{font-size:12px;line-height:1.58;color:rgba(191,205,240,.72);}
      .action-visibility-meta{display:flex;flex-wrap:wrap;gap:8px;margin-top:2px;}
      .action-visibility-pill{
        display:inline-flex;align-items:center;gap:6px;min-height:28px;padding:0 10px;border-radius:999px;
        border:1px solid rgba(255,255,255,.07);background:rgba(255,255,255,.03);font-size:11px;color:rgba(205,218,250,.78);
      }
      .action-visibility-pill svg{width:11px;height:11px;opacity:.76;}
      .action-visibility-pill strong{
        font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:rgba(160,180,228,.48);
      }
      .action-visibility-trail{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:2px;}
      .action-step{
        display:inline-flex;align-items:center;gap:6px;min-height:26px;padding:0 10px;border-radius:999px;
        background:rgba(255,255,255,.028);border:1px solid rgba(255,255,255,.06);font-size:11px;color:rgba(216,226,250,.78);
      }
      .action-step svg{width:10px;height:10px;opacity:.82;}
      .action-step.done{color:rgba(201,255,229,.90);border-color:rgba(52,211,153,.16);background:rgba(52,211,153,.08);}
      .action-step.live{color:rgba(219,233,255,.90);border-color:rgba(59,130,246,.16);background:rgba(59,130,246,.08);}

      .refund-assist{display:grid;gap:8px;margin-bottom:8px;}
      .refund-assist-label{
        font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:rgba(190,204,240,.48);font-weight:700;padding:0 2px;
      }
      .refund-assist-input{
        width:100%;min-width:0;height:40px;border-radius:14px;border:1px solid rgba(255,255,255,.08);background:rgba(9,12,24,.42);
        color:rgba(241,246,255,.96);padding:0 14px;font-size:13px;outline:none;
        transition:border-color .16s ease, background .16s ease, box-shadow .16s ease;
      }
      .refund-assist-input::placeholder{color:rgba(210,222,250,.34);}
      .refund-assist-input:hover{background:rgba(9,12,24,.50);border-color:rgba(255,255,255,.10);}
      .refund-assist-input:focus{
        border-color:rgba(139,111,255,.28);background:rgba(10,13,26,.54);box-shadow:0 0 0 3px rgba(139,111,255,.08);
      }

      .assistant-actions{display:flex;align-items:flex-start;gap:10px;flex-wrap:wrap;margin-top:14px;}

      .mini-btn.copy-btn{
        display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;padding:0;border-radius:10px;
        border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.045);color:rgba(232,238,255,.92);
        box-shadow:0 8px 20px rgba(0,0,0,.16), inset 0 1px 0 rgba(255,255,255,.04);
        transition:transform .16s ease, background .16s ease, border-color .16s ease;color .16s ease;flex:0 0 auto;
      }
      .mini-btn.copy-btn:hover{
        transform:translateY(-1px);background:rgba(255,255,255,.075);border-color:rgba(255,255,255,.14);
      }
      .mini-btn.copy-btn svg{width:15px;height:15px;display:block;}
      .mini-btn.copy-btn span{
        position:absolute !important;width:1px !important;height:1px !important;padding:0 !important;margin:-1px !important;
        overflow:hidden !important;clip:rect(0, 0, 0, 0) !important;white-space:nowrap !important;border:0 !important;
      }

      .x-upgrade-stack{display:grid;gap:12px;margin-top:10px;}
      .x-upgrade-card{
        position:relative;overflow:hidden;border-radius:18px;border:1px solid rgba(255,255,255,.08);
        background:
          linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.016)),
          radial-gradient(circle at 88% 14%, rgba(139,111,255,.12), transparent 34%);
        box-shadow:0 14px 36px rgba(0,0,0,.18), inset 0 1px 0 rgba(255,255,255,.03);
        padding:14px 14px 13px;
        transition:transform .18s ease, border-color .18s ease, box-shadow .18s ease;
      }
      .x-upgrade-card:hover{
        transform:translateY(-1px);border-color:rgba(255,255,255,.13);box-shadow:0 18px 42px rgba(0,0,0,.22), inset 0 1px 0 rgba(255,255,255,.04);
      }
      .x-upgrade-card.popular{
        border-color:rgba(139,111,255,.24);
        background:
          linear-gradient(180deg, rgba(255,255,255,.04), rgba(255,255,255,.018)),
          radial-gradient(circle at 88% 12%, rgba(139,111,255,.18), transparent 32%);
      }
      .x-upgrade-badge{
        display:inline-flex;align-items:center;gap:6px;min-height:24px;padding:0 9px;border-radius:999px;
        border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.045);color:rgba(232,239,255,.86);
        font-size:10px;font-weight:800;letter-spacing:.10em;text-transform:uppercase;margin-bottom:10px;
      }
      .x-upgrade-badge svg{width:10px;height:10px;}
      .x-upgrade-badge.popular{
        border-color:rgba(139,111,255,.26);background:rgba(139,111,255,.14);color:rgba(239,234,255,.98);
      }
      .x-upgrade-row{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;}
      .x-upgrade-title{font-size:16px;font-weight:800;color:rgba(242,246,255,.97);letter-spacing:-.01em;}
      .x-upgrade-price{font-size:13px;font-weight:700;color:rgba(205,218,250,.82);white-space:nowrap;}
      .x-upgrade-copy{margin-top:6px;font-size:12.5px;line-height:1.62;color:rgba(205,218,250,.76);}
      .x-upgrade-copy strong{color:rgba(244,247,255,.96);font-weight:800;}
      .x-upgrade-points{display:grid;gap:6px;margin-top:11px;}
      .x-upgrade-point{
        display:flex;align-items:flex-start;gap:8px;font-size:11.5px;line-height:1.45;color:rgba(225,233,252,.84);
      }
      .x-upgrade-point svg{width:11px;height:11px;margin-top:2px;flex:0 0 auto;color:rgba(147,197,253,.92);}
      .x-upgrade-cta{
        display:inline-flex;align-items:center;justify-content:space-between;gap:10px;width:100%;min-height:46px;margin-top:12px;
        padding:0 14px;border-radius:14px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.05);
        color:rgba(246,248,255,.98);font-size:13px;font-weight:800;letter-spacing:.01em;cursor:pointer;
        transition:transform .16s ease, background .16s ease, border-color .16s ease, box-shadow .16s ease, opacity .16s ease;
      }
      .x-upgrade-cta:hover{
        transform:translateY(-1px);background:rgba(255,255,255,.082);border-color:rgba(255,255,255,.14);box-shadow:0 10px 24px rgba(0,0,0,.14);
      }
      .x-upgrade-cta.primary{
        border-color:rgba(139,111,255,.28);
        background:linear-gradient(135deg, rgba(139,111,255,.24), rgba(104,140,255,.20));
        box-shadow:0 14px 28px rgba(80,52,196,.20);
      }
      .x-upgrade-cta.primary:hover{
        background:linear-gradient(135deg, rgba(139,111,255,.30), rgba(104,140,255,.25));
      }
      .x-upgrade-cta svg{width:14px;height:14px;flex:0 0 auto;}
      .x-upgrade-cta[disabled]{opacity:.56;pointer-events:none;cursor:default;}
      .x-upgrade-foot{margin-top:10px;font-size:11px;line-height:1.55;color:rgba(186,201,238,.62);}
      .x-upgrade-context{
        margin-top:12px;border-top:1px solid rgba(255,255,255,.06);padding-top:12px;
      }
      .x-upgrade-context-title{
        font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:rgba(185,201,238,.48);font-weight:800;margin-bottom:8px;
      }
      .x-upgrade-context-copy{
        font-size:12px;line-height:1.62;color:rgba(212,223,248,.75);
      }
      .x-upgrade-alert{
        display:none;margin-top:10px;padding:10px 12px;border-radius:14px;border:1px solid rgba(255,255,255,.08);font-size:12px;line-height:1.55;
      }
      .x-upgrade-alert.show{display:block;}
      .x-upgrade-alert.warning{
        border-color:rgba(245,158,11,.18);background:rgba(245,158,11,.08);color:rgba(255,241,194,.94);
      }
      .x-upgrade-alert.info{
        border-color:rgba(59,130,246,.18);background:rgba(59,130,246,.08);color:rgba(219,233,255,.94);
      }
      .x-upgrade-current{
        border-color:rgba(52,211,153,.18);
        background:
          linear-gradient(180deg, rgba(255,255,255,.038), rgba(255,255,255,.016)),
          radial-gradient(circle at 88% 12%, rgba(52,211,153,.15), transparent 34%);
      }
      .x-upgrade-current-copy{
        margin-top:8px;font-size:12.5px;line-height:1.62;color:rgba(212,223,248,.76);
      }

      @keyframes xalvionReveal{
        from{opacity:0;transform:translateY(6px) scale(.995)}
        to{opacity:1;transform:translateY(0) scale(1)}
      }
    `;
    document.head.appendChild(style);
  }

  function ensurePaymentIntentField() {
    if (els.paymentIntentInput) return;

    const composerWrap = document.querySelector(".composer-wrap");
    const composer = document.querySelector(".composer");
    if (!composerWrap || !composer) return;

    const wrap = document.createElement("div");
    wrap.className = "refund-assist";

    const label = document.createElement("div");
    label.className = "refund-assist-label";
    label.textContent = "Payment reference";

    const input = document.createElement("input");
    input.type = "text";
    input.id = "paymentIntentInput";
    input.className = "refund-assist-input";
    input.placeholder = "Paste payment_intent_id (pi_...) or charge_id (ch_...) when needed";

    wrap.appendChild(label);
    wrap.appendChild(input);
    composerWrap.insertBefore(wrap, composer);

    els.paymentIntentInput = input;
  }

  function headers(json = true) {
    const h = {};
    if (json) h["Content-Type"] = "application/json";
    if (state.token) h["Authorization"] = `Bearer ${state.token}`;
    return h;
  }

  function setText(el, value) {
    if (el) el.textContent = value;
  }

  function setNotice(kind, title, detail) {
    if (!els.notice) return;
    els.notice.className = `notice ${kind}`;
    setText(els.noticeTitle, title);

    const detailEl = els.noticeDetail;
    if (!detailEl) return;

    detailEl.classList.remove("ticker");
    detailEl.style.animation = "";
    detailEl.textContent = detail;

    requestAnimationFrame(() => {
      const wrap = detailEl.parentElement;
      if (!wrap) return;
      const wrapWidth = wrap.offsetWidth;
      const textWidth = detailEl.scrollWidth;

      if (textWidth > wrapWidth) {
        const gap = "     •     ";
        detailEl.textContent = detail + gap + detail + gap;
        const duration = (textWidth + gap.length * 6) / 38;
        detailEl.style.animation = `noticeTicker ${duration}s linear infinite`;
        detailEl.classList.add("ticker");
      }
    });
  }

  function formatMetric(value, digits = 2) {
    if (value === null || value === undefined) return "0";
    if (typeof value === "number" && !Number.isInteger(value)) {
      return value.toFixed(digits).replace(/\.00$/, "");
    }
    return String(value);
  }

  function formatLimit(value) {
    if (!Number.isFinite(value)) return "∞";
    return String(value);
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
    state.limit = Infinity;
    state.remaining = Infinity;
    persistAuth();
  }

  function autoResizeTextarea() {
    const ta = els.messageInput;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 110)}px`;
  }

  function scrollMessagesToBottom(force = false) {
    if (!els.messages) return;
    if (force) {
      els.messages.scrollTop = els.messages.scrollHeight;
      return;
    }

    const nearBottom =
      els.messages.scrollHeight - els.messages.scrollTop - els.messages.clientHeight < 140;

    if (nearBottom) {
      els.messages.scrollTop = els.messages.scrollHeight;
    }
  }

  function escapeHtml(text) {
    return String(text ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function getVisibleTierLabel() {
    const tier = (state.tier || "free").toLowerCase();
    if (tier === "dev") return "starter";
    return tier;
  }

  function getPlanCopy() {
    const tier = (state.tier || "free").toLowerCase();

    if (tier === "free") {
      return {
        usage:
          "You are on the Free plan. As usage grows, upgrading unlocks more monthly capacity, faster response handling, and a stronger support workflow.",
        teaser:
          "Pro unlocks higher limits and faster handling. Elite unlocks maximum capacity, top-priority routing, and the full Xalvion experience."
      };
    }

    if (tier === "pro") {
      return {
        usage:
          "You are on the Pro plan with expanded monthly capacity and priority routing for higher support volume.",
        teaser:
          "Elite removes pressure at scale with maximum capacity, top-priority routing, and the most advanced workspace access."
      };
    }

    if (tier === "elite") {
      return {
        usage:
          "You are on the Elite plan with the highest monthly capacity and advanced access across the workspace.",
        teaser:
          "You’re already on the highest Xalvion tier with full access to the premium support workflow."
      };
    }

    return {
      usage:
        "You are on the Starter plan with access to the core support workspace.",
      teaser:
        "Unlock higher usage limits and stronger support throughput with a paid plan."
    };
  }

  function getUsagePressureMessage() {
    if (!Number.isFinite(state.limit) || state.limit <= 0) return "";
    const ratio = state.usage / state.limit;

    if (ratio >= 0.9) {
      return "Workspace capacity is almost reached. Upgrade now to avoid interruptions during active support demand.";
    }
    if (ratio >= 0.7) {
      return "You’re approaching your monthly limit. Upgrading now keeps support flow smooth as demand rises.";
    }
    if ((state.tier || "free") === "free") {
      return "Free is great for proving value. Paid plans are built for reliability, speed, and customer continuity.";
    }
    if ((state.tier || "free") === "pro") {
      return "Elite is built for heavier support volume when faster routing and more headroom directly impact customer experience.";
    }
    return "";
  }

  function updateTopbarStatus() {
    const tier = getVisibleTierLabel();
    const usage = Number.isFinite(state.usage) ? state.usage : 0;
    const limit = Number.isFinite(state.limit) ? state.limit : null;
    const user = state.username || "";
    const usageStr = limit ? `${usage}/${limit} used` : "active";
    const userStr = user ? `${user} · ` : "";
    setText(els.workspaceSubcopy, `${userStr}${tier} · ${usageStr}`);
  }

  function pulseRail(target = "account") {
    [els.dashboardCard, els.usageCard, els.accountCard].forEach((card) => {
      if (card) card.classList.remove("active");
    });

    const map = {
      dashboard: els.dashboardCard,
      usage: els.usageCard,
      account: els.accountCard
    };

    const card = map[target] || els.accountCard;
    if (!card) return;
    card.classList.add("active");
    window.clearTimeout(card._pulseTimer);
    card._pulseTimer = window.setTimeout(() => card.classList.remove("active"), 1800);
  }

  function updateCustomerFacingCopy() {
    const planCopy = getPlanCopy();

    setText(
      els.brandSubcopy,
      "Fast, clear support responses with the right next step built in."
    );
    setText(
      els.workspaceHeadline,
      "Customer support workspace"
    );
    setText(
      els.systemPanelCopy,
      "Response-ready workspace with clean output, visible progress, and clear action flow."
    );
    setText(els.usagePanelCopy, planCopy.usage);

    updateTopbarStatus();
    renderUpgradePanel();

    if (els.devBtn) {
      els.devBtn.textContent = "Quick demo";
      els.devBtn.setAttribute("aria-label", "Quick demo access");
      els.devBtn.title = "Quick demo access";
    }
  }

  function renderEmptyState() {
    if (!els.messages) return;

    els.messages.innerHTML = `
      <div class="empty-state">
        <div class="empty-card">
          <div class="empty-eyebrow">
            <span class="empty-eyebrow-dot"></span>
            Live operator workspace
          </div>
          <h1>Resolve support cases with visible decisions and polished output.</h1>
          <p>
            Drop in a customer message to generate a structured reply, clear action visibility,
            and the next best move inside the workspace.
          </p>
          <div class="empty-grid">
            <button class="chip" data-fill="Customer says they were charged twice for the same order and wants a refund.">Duplicate charge</button>
            <button class="chip" data-fill="Customer wants to cancel and receive a refund because the package never arrived.">Missing order</button>
            <button class="chip" data-fill="Customer is angry that their shipment is delayed and is asking for store credit.">Delay compensation</button>
          </div>
        </div>
      </div>
    `;

    els.chips = Array.from(document.querySelectorAll("[data-fill]"));
    bindChips();
  }

  function bindChips() {
    if (!els.chips || !els.chips.length) return;
    els.chips.forEach((chip) => {
      chip.addEventListener("click", () => {
        if (!els.messageInput) return;
        els.messageInput.value = chip.getAttribute("data-fill") || "";
        autoResizeTextarea();
        els.messageInput.focus();
      });
    });
  }

  // ── PATCH 1: CSS classes now match index.html stylesheet ──────────────────
  // Old code used .msg-row / .msg-bubble / .assistant-copy — zero CSS rules
  // for those in index.html, so every message rendered completely invisible.
  // Correct classes: .msg-group / .reply-body / .reply-text / .msg-who

  function addUserMessage(text) {
    if (!els.messages) return;
    const group = document.createElement("div");
    group.className = "msg-group user new-msg";
    group.innerHTML = `
      <div class="msg-group-header"><div class="msg-who">You</div></div>
      <div class="reply-body"><div class="reply-text">${escapeHtml(text)}</div></div>
    `;
    els.messages.appendChild(group);
    scrollMessagesToBottom(true);
  }

  function addAssistantMessage(shell = "Thinking…") {
    if (!els.messages) return null;
    const group = document.createElement("div");
    group.className = "msg-group assistant new-msg";
    group.innerHTML = `
      <div class="msg-group-header"><div class="msg-who">Xalvion</div></div>
      <div class="reply-body">
        <div class="reply-text js-reply-text">
          <span class="typing"><span></span><span></span><span></span></span>
        </div>
      </div>
      <div class="assistant-actions js-actions"></div>
    `;
    els.messages.appendChild(group);
    scrollMessagesToBottom(true);
    return group;
  }

  function getAssistantCopyNode(row) {
    return row?.querySelector(".js-reply-text") || null;
  }

  function getAssistantActionsNode(row) {
    return row?.querySelector(".js-actions") || null;
  }

  function setAssistantCopy(row, text) {
    const node = getAssistantCopyNode(row);
    if (!node) return;
    node.innerHTML = escapeHtml(text).replace(/\n/g, "<br>");
  }

  function appendAssistantChunk(row, chunk) {
    const node = getAssistantCopyNode(row);
    if (!node) return;
    // Clear typing indicator on first chunk
    if (node.querySelector(".typing")) node.innerHTML = "";
    const current = node.textContent || "";
    node.innerHTML = escapeHtml(current + chunk).replace(/\n/g, "<br>");
  }

  function normalizeActionTone(action) {
    const value = String(action || "").trim().toLowerCase();
    if (value.includes("refund")) return "success";
    if (value.includes("review")) return "warning";
    return "info";
  }

  function normalizeActionLabel(action) {
    const raw = String(action || "").trim();
    if (!raw) return "Action";
    return raw
      .replaceAll("_", " ")
      .replace(/\b\w/g, (m) => m.toUpperCase());
  }

  function actionIcon(action) {
    const key = String(action || "").toLowerCase();
    if (key.includes("refund")) return ICONS.refund;
    if (key.includes("credit")) return ICONS.credit;
    if (key.includes("review")) return ICONS.review;
    return ICONS.status;
  }

  function createActionVisibility(result = {}) {
    const tone = normalizeActionTone(result.action);
    const box = document.createElement("div");
    box.className = `action-visibility ${tone} show`;

    const label = normalizeActionLabel(result.action || result.status || "Action");
    const badge = (result.status || "Completed").toString().replaceAll("_", " ");
    const summary = result.action_summary || result.explanation || "Action completed.";
    const detail = result.detail || result.reason || "";
    const issueType = result.issue_type || "general_support";
    const confidence = Number(result.confidence || 0);
    const quality = Number(result.quality || 0);

    box.innerHTML = `
      <div class="action-visibility-head">
        <div class="action-visibility-title">
          <div class="action-visibility-icon-wrap">${actionIcon(result.action)}</div>
          <div class="action-visibility-title-stack">
            <div class="action-visibility-title-text">Action visibility</div>
            <div class="action-visibility-kicker">${escapeHtml(label)}</div>
          </div>
        </div>
        <div class="action-visibility-badge">${escapeHtml(badge)}</div>
      </div>

      <div class="action-visibility-body">
        <div class="action-visibility-line">${escapeHtml(summary)}</div>
        ${detail ? `<div class="action-visibility-sub">${escapeHtml(detail)}</div>` : ""}
        <div class="action-visibility-meta">
          <div class="action-visibility-pill">
            ${ICONS.sparkle}
            <span><strong>Issue</strong> ${escapeHtml(issueType.replaceAll("_", " "))}</span>
          </div>
          <div class="action-visibility-pill">
            ${ICONS.status}
            <span><strong>Confidence</strong> ${formatMetric(confidence)}</span>
          </div>
          <div class="action-visibility-pill">
            ${ICONS.check}
            <span><strong>Quality</strong> ${formatMetric(quality)}</span>
          </div>
        </div>
        <div class="action-visibility-trail">
          <div class="action-step done">${ICONS.check}<span>Analyzed</span></div>
          <div class="action-step done">${ICONS.check}<span>Prepared</span></div>
          <div class="action-step live">${ICONS.status}<span>Applied</span></div>
        </div>
      </div>
    `;

    return box;
  }

  function addCopyControls(row, text) {
    const actions = getAssistantActionsNode(row);
    if (!actions) return;

    actions.innerHTML = `
      <button class="mini-btn copy-btn" type="button" aria-label="Copy reply" title="Copy reply">
        ${ICONS.copy}
        <span>Copy reply</span>
      </button>
    `;

    const btn = actions.querySelector(".copy-btn");
    if (!btn) return;

    btn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(text || "");
        const old = btn.innerHTML;
        const oldTitle = btn.title;
        const oldLabel = btn.getAttribute("aria-label") || "Copy reply";

        btn.innerHTML = `${ICONS.check}<span>Copied</span>`;
        btn.title = "Copied";
        btn.setAttribute("aria-label", "Copied");

        window.setTimeout(() => {
          btn.innerHTML = old;
          btn.title = oldTitle;
          btn.setAttribute("aria-label", oldLabel);
        }, 1200);
      } catch {
        setNotice("warning", "Copy unavailable", "Could not copy the response from this browser.");
      }
    });
  }

  function getUpgradeConfig() {
    return {
      free: {
        pro: {
          title: "Pro",
          price: "$29/mo",
          badge: "Most popular",
          badgeClass: "popular",
          headline: "Scale your support without friction.",
          body: "More capacity, faster responses, and priority handling to keep every customer interaction smooth and reliable.",
          points: [
            "Higher monthly capacity for growing demand",
            "Faster response handling during busy periods",
            "Priority routing for stronger customer continuity"
          ],
          cta: "Unlock Pro — Scale Your Support",
          ctaClass: "primary",
          foot: "Built for growth-stage usage and stronger day-to-day operational flow."
        },
        elite: {
          title: "Elite",
          price: "$99/mo",
          badge: "Full power",
          badgeClass: "",
          headline: "The full Xalvion experience.",
          body: "Maximum capacity, highest priority processing, and unrestricted access to advanced support capabilities.",
          points: [
            "Maximum throughput for serious support volume",
            "Highest priority routing across the workspace",
            "Built for mission-critical support operations"
          ],
          cta: "Go Elite — Full Power Access",
          ctaClass: "",
          foot: "Best for heavier volume, higher urgency, and premium support performance."
        }
      },
      pro: {
        elite: {
          title: "Elite",
          price: "$99/mo",
          badge: "Next level",
          badgeClass: "",
          headline: "Run support at full power.",
          body: "Maximum capacity and top-tier priority deliver the fastest, most reliable customer resolutions possible.",
          points: [
            "More headroom when volume spikes",
            "Top-priority handling for critical workflows",
            "Full access to the strongest Xalvion setup"
          ],
          cta: "Go Elite — Full Power Access",
          ctaClass: "primary",
          foot: "Upgrade when support demand, urgency, or complexity starts outgrowing Pro."
        }
      },
      elite: {}
    };
  }

  function findPlansMount() {
    if (document.querySelector(".x-upgrade-stack")) {
      return document.querySelector(".x-upgrade-stack").parentElement;
    }

    if (els.upgradeButtons.length) {
      const first = els.upgradeButtons[0];
      return (
        first.closest(".plans") ||
        first.closest("[data-plans]") ||
        first.parentElement?.parentElement ||
        first.parentElement
      );
    }

    return (
      document.querySelector(".plans") ||
      document.querySelector("[data-plans]") ||
      null
    );
  }

  function renderUpgradePanel() {
    const mount = findPlansMount();
    if (!mount) return;

    const oldButtons = Array.from(mount.querySelectorAll("[data-upgrade]"));
    oldButtons.forEach((btn) => {
      const wrap =
        btn.closest(".x-upgrade-stack") ||
        btn.closest(".plan-btn-wrap") ||
        btn.closest(".plan-row") ||
        btn.closest(".upgrade-row") ||
        btn.closest(".plan-item") ||
        btn;
      if (!wrap.classList?.contains("x-upgrade-stack")) {
        wrap.remove();
      }
    });

    let stack = mount.querySelector(".x-upgrade-stack");
    if (!stack) {
      stack = document.createElement("div");
      stack.className = "x-upgrade-stack";
      mount.appendChild(stack);
    }

    const tier = (state.tier || "free").toLowerCase();
    const configs = getUpgradeConfig();
    const options = configs[tier] || {};
    const pressure = getUsagePressureMessage();
    const teaser = getPlanCopy().teaser || "";

    if (tier === "elite") {
      stack.innerHTML = `
        <div class="x-upgrade-card x-upgrade-current">
          <div class="x-upgrade-badge popular">${ICONS.crown}<span>Highest tier active</span></div>
          <div class="x-upgrade-row">
            <div class="x-upgrade-title">Elite active</div>
            <div class="x-upgrade-price">Full access</div>
          </div>
          <div class="x-upgrade-current-copy">
            You’re already on the highest Xalvion plan with maximum capacity, top-priority routing, and the strongest workspace access.
          </div>
          <div class="x-upgrade-context">
            <div class="x-upgrade-context-title">Current advantage</div>
            <div class="x-upgrade-context-copy">${escapeHtml(teaser)}</div>
          </div>
        </div>
      `;
      els.upgradeButtons = [];
      return;
    }

    let html = "";
    Object.entries(options).forEach(([planKey, cfg]) => {
      html += `
        <div class="x-upgrade-card ${cfg.badgeClass === "popular" ? "popular" : ""}">
          ${cfg.badge ? `<div class="x-upgrade-badge ${cfg.badgeClass}">${cfg.badgeClass === "popular" ? ICONS.crown : ICONS.bolt}<span>${escapeHtml(cfg.badge)}</span></div>` : ""}
          <div class="x-upgrade-row">
            <div class="x-upgrade-title">${escapeHtml(cfg.title)}</div>
            <div class="x-upgrade-price">${escapeHtml(cfg.price)}</div>
          </div>
          <div class="x-upgrade-copy">
            <strong>${escapeHtml(cfg.headline)}</strong><br>
            ${escapeHtml(cfg.body)}
          </div>
          <div class="x-upgrade-points">
            ${cfg.points.map((point) => `
              <div class="x-upgrade-point">
                ${ICONS.check}
                <span>${escapeHtml(point)}</span>
              </div>
            `).join("")}
          </div>
          <button class="x-upgrade-cta ${cfg.ctaClass}" type="button" data-upgrade="${escapeHtml(planKey)}">
            <span>${escapeHtml(cfg.cta)}</span>
            ${ICONS.arrow}
          </button>
          <div class="x-upgrade-foot">${escapeHtml(cfg.foot)}</div>
        </div>
      `;
    });

    html += `
      <div class="x-upgrade-context">
        <div class="x-upgrade-context-title">Why upgrade now</div>
        <div class="x-upgrade-context-copy">${escapeHtml(teaser)}</div>
        ${pressure ? `<div class="x-upgrade-alert ${tier === "free" && state.usage / Math.max(state.limit || 1, 1) < 0.7 ? "info" : "warning"} show">${escapeHtml(pressure)}</div>` : ""}
      </div>
    `;

    stack.innerHTML = html;
    els.upgradeButtons = Array.from(stack.querySelectorAll("[data-upgrade]"));
    bindUpgrades();
  }

  function updatePlanUI(tier, usage, limit, remaining) {
    state.tier = (tier || "free").toLowerCase();
    state.usage = Number(usage || 0);
    state.limit = Number.isFinite(limit) ? Number(limit) : Infinity;
    state.remaining = Number.isFinite(remaining) ? Number(remaining) : Infinity;

    setText(els.planTier, getVisibleTierLabel().toUpperCase());
    setText(els.planUsage, `${state.usage}/${formatLimit(state.limit)}`);
    setText(els.planUsed, String(state.usage));
    setText(els.planRemaining, formatLimit(state.remaining));

    if (els.planBar) {
      const ratio = Number.isFinite(state.limit) && state.limit > 0
        ? Math.max(0, Math.min(1, state.usage / state.limit))
        : 0;
      // PATCH 2b: index.html uses style.width on #planBar, not CSS --fill
      els.planBar.style.width = `${ratio * 100}%`;
    }

    updateCustomerFacingCopy();
  }

  function updateDashboardUI(data = {}) {
    // PATCH 2: API returns total_interactions/avg_quality/avg_confidence
    // not interactions/quality/confidence — all four stats were stuck at 0
    setText(els.statInteractions, formatMetric(data.total_interactions || data.interactions || 0, 0));
    setText(els.statQuality,      formatMetric(data.avg_quality        || data.quality       || 0));
    setText(els.statConfidence,   formatMetric(data.avg_confidence     || data.confidence    || 0));
    setText(els.statActions,      formatMetric(data.actions            || 0, 0));
  }

  async function healthCheck() {
    try {
      const res = await fetch(`${API}/health`);
      if (!res.ok) throw new Error("Offline");
      const data = await res.json().catch(() => ({}));

      setText(els.backendStatus, "Status: online");
      setText(els.streamStatus, data.streaming ? "Streaming: live" : "Streaming: standard");
      setNotice("success", "System online", "Workspace connected and ready for requests");
    } catch {
      setText(els.backendStatus, "Status: offline");
      setNotice("error", "Offline", "Backend not responding");
    }
  }

  async function hydrateMe() {
    try {
      const res = await fetch(`${API}/me`, {
        headers: headers(false)
      });

      if (!res.ok) throw new Error("Session unavailable");

      const data = await res.json();

      state.username = data.username || state.username || "";
      state.tier = data.tier || state.tier || "free";
      persistAuth();

      updatePlanUI(
        data.tier || "free",
        Number(data.usage || 0),
        Number(data.limit || 1000000000),
        Number(data.remaining || 1000000000)
      );

      setText(
        els.authStatus,
        data.username ? `Account: ${data.username}` : "Account: guest workspace"
      );
    } catch {
      clearAuth();
      updatePlanUI("free", 0, 50, 50);
      setText(els.authStatus, "Account: guest workspace");
    }
  }

  async function loadDashboard() {
    try {
      const res = await fetch(`${API}/dashboard/summary`, {
        headers: headers(false)
      });
      if (!res.ok) throw new Error("Dashboard unavailable");
      const data = await res.json();
      updateDashboardUI(data);
    } catch {
      // keep stable
    }
  }

  async function signUp() {
    const username = (els.usernameInput?.value || "").trim();
    const password = (els.passwordInput?.value || "").trim();

    if (!username || !password) {
      setNotice("warning", "Missing details", "Enter a username and password before signing up.");
      return;
    }

    try {
      if (els.signupBtn) els.signupBtn.disabled = true;

      const res = await fetch(`${API}/signup`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ username, password })
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Signup failed");

      setNotice("success", "Account created", `${username} is ready. Log in to start using your workspace.`);
    } catch (err) {
      setNotice("error", "Signup failed", err.message || "Could not create the account.");
    } finally {
      if (els.signupBtn) els.signupBtn.disabled = false;
    }
  }

  async function logIn() {
    const username = (els.usernameInput?.value || "").trim();
    const password = (els.passwordInput?.value || "").trim();

    if (!username || !password) {
      setNotice("warning", "Missing details", "Enter a username and password before logging in.");
      return;
    }

    try {
      if (els.loginBtn) els.loginBtn.disabled = true;

      const res = await fetch(`${API}/login`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ username, password })
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Login failed");

      state.token = data.token || "";
      state.username = username;
      state.tier = data.tier || "free";
      persistAuth();

      updatePlanUI(
        data.tier || "free",
        Number(data.usage || 0),
        Number(data.limit || 0),
        Number(data.remaining || 0)
      );

      setText(els.authStatus, `Account: ${username}`);
      setNotice("success", "Logged in", `${username} is active. Your plan and monthly usage are now tied to this account.`);
      pulseRail("account");
      await loadDashboard();
      if (data.is_admin) await renderAdminPanel();
    } catch (err) {
      setNotice("error", "Login failed", err.message || "Could not log in.");
    } finally {
      if (els.loginBtn) els.loginBtn.disabled = false;
    }
  }

  function useDevMode() {
    clearAuth();
    updatePlanUI("free", 0, 50, 50);
    setText(els.authStatus, "Account: guest workspace");
    setNotice("info", "Quick demo", "Starter workspace active");
    pulseRail("account");
  }

  function logout() {
    clearAuth();
    updatePlanUI("free", 0, 50, 50);
    setText(els.authStatus, "Account: guest workspace");
    setNotice("info", "Logged out", "Session cleared");
    pulseRail("account");
  }

  async function upgradePlan(tier) {
    const desired = String(tier || "").trim().toLowerCase();

    if (!desired) {
      setNotice("error", "Upgrade failed", "No plan was selected.");
      return;
    }

    if (!state.token || !state.username) {
      setNotice(
        "warning",
        "Log in required",
        "Create an account or log in before upgrading so the plan can attach to your workspace."
      );
      pulseRail("account");
      return;
    }

    try {
      setNotice(
        "info",
        "Securing your upgrade",
        `Preparing ${desired.toUpperCase()} — you’ll be redirected to complete payment securely.`
      );
      pulseRail("usage");

      const res = await fetch(`${API}/billing/upgrade`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ tier: desired })
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || `Upgrade failed (${res.status})`);
      }

      if (data.checkout_url) {
        window.location.href = data.checkout_url;
        return;
      }

      if (data.tier) {
        state.tier = data.tier;
        persistAuth();
        updatePlanUI(
          data.tier,
          Number(data.usage || state.usage || 0),
          Number(data.limit || state.limit || 0),
          Number(data.remaining || state.remaining || 0)
        );
      }

      setNotice("success", "Plan updated", `${desired.toUpperCase()} is now active.`);
    } catch (err) {
      setNotice("error", "Upgrade failed", err.message || "Could not prepare the upgrade.");
    }
  }

  function buildSupportPayload() {
    const paymentField = els.paymentIntentInput || document.getElementById("paymentIntentInput");
    return {
      message: (els.messageInput?.value || "").trim(),
      payment_intent_id: (paymentField?.value || "").trim()
    };
  }

  function setSending(value) {
    state.sending = Boolean(value);

    if (els.sendBtn) {
      els.sendBtn.disabled = state.sending;
      els.sendBtn.classList.toggle("busy", state.sending);
      els.sendBtn.innerHTML = state.sending
        ? `${ICONS.status}<span>Sending…</span>`
        : `${ICONS.send}<span>Send</span>`;
    }
  }

  async function handleStandardReply(payload) {
    const res = await fetch(`${API}/support`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify(payload)
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "Request failed");
    return data;
  }

  async function handleStreamReply(payload, row) {
    const res = await fetch(`${API}/support/stream`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify(payload)
    });

    if (!res.ok || !res.body) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || "Streaming failed");
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalData = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";

      for (const part of parts) {
        const lines = part.split("\n");
        let eventName = "message";
        let dataValue = "";

        for (const line of lines) {
          if (line.startsWith("event:")) eventName = line.slice(6).trim();
          if (line.startsWith("data:")) dataValue += line.slice(5).trim();
        }

        if (!dataValue) continue;
        const parsed = JSON.parse(dataValue);

        if (eventName === "chunk") {
          appendAssistantChunk(row, parsed.text || "");
          scrollMessagesToBottom();
        }

        if (eventName === "status") {
          state.latestStatus = parsed.status || "";
        }

        if (eventName === "result") {
          finalData = parsed;
        }
      }
    }

    return finalData;
  }

  async function sendMessage() {
    const payload = buildSupportPayload();
    if (!payload.message || state.sending) return;

    ensureInjectedStyles();
    ensurePaymentIntentField();

    if (els.messages?.querySelector(".empty-state")) {
      els.messages.innerHTML = "";
    }

    addUserMessage(payload.message);
    if (els.messageInput) {
      els.messageInput.value = "";
      autoResizeTextarea();
    }

    const row = addAssistantMessage("Analyzing request…");
    setSending(true);

    try {
      let data = null;

      try {
        data = await handleStreamReply(payload, row);
      } catch {
        data = await handleStandardReply(payload);
        setAssistantCopy(row, data.reply || "No response returned.");
      }

      if (!data) throw new Error("No response returned.");

      const replyText = data.reply || "No response returned.";
      setAssistantCopy(row, replyText);
      addCopyControls(row, replyText);

      const actionNode = getAssistantActionsNode(row);
      if (actionNode && data.action && data.action !== "none") {
        actionNode.appendChild(createActionVisibility(data));
      }

      // PATCH 3: API returns tier/usage/plan_limit/remaining at top level,
      // not nested under usage_summary — plan bar was never updating after sends
      if (data.tier) {
        updatePlanUI(
          data.tier,
          Number(data.usage        || state.usage     || 0),
          Number(data.plan_limit   || state.limit     || 0),
          Number(data.remaining    || state.remaining || 0)
        );
      } else {
        updateTopbarStatus();
      }

      // Only update username for real logged-in accounts
      if (data.username && data.username !== "dev_user" && data.username !== "guest") {
        state.username = data.username;
        persistAuth();
        setText(els.authStatus, `Account: ${data.username}`);
      }

      if (data.action) {
        state.latestAction = data.action;
        pulseRail(data.action.includes("refund") ? "usage" : "dashboard");
      }

      await loadDashboard();
      scrollMessagesToBottom(true);
    } catch (err) {
      setAssistantCopy(row, err.message || "Something went wrong while processing the request.");
      setNotice("error", "Request failed", err.message || "Could not process the request.");
    } finally {
      setSending(false);
    }
  }

  function bindComposer() {
    if (els.sendBtn) els.sendBtn.addEventListener("click", sendMessage);

    if (els.messageInput) {
      els.messageInput.addEventListener("input", autoResizeTextarea);
      els.messageInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          sendMessage();
        }
      });
    }
  }

  function bindAuth() {
    if (els.signupBtn) els.signupBtn.addEventListener("click", signUp);
    if (els.loginBtn) els.loginBtn.addEventListener("click", logIn);
    if (els.devBtn) els.devBtn.addEventListener("click", useDevMode);
    if (els.logoutBtn) els.logoutBtn.addEventListener("click", logout);
  }

  function bindUpgrades() {
    els.upgradeButtons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const tier = btn.getAttribute("data-upgrade");
        if (tier) upgradePlan(tier);
      });
    });
  }

  function bindTopActions() {
    if (els.newChatBtn) {
      els.newChatBtn.addEventListener("click", () => {
        renderEmptyState();
        setNotice("info", "New workspace", "Ready for a fresh support case.");
      });
    }
  }

  async function renderAdminPanel() {
    return;
  }

  function bootCheckoutNotice() {
    const url = new URL(window.location.href);
    const checkout = url.searchParams.get("checkout");
    if (!checkout) return;

    if (checkout === "success") {
      setNotice("success", "Upgrade complete", "Billing confirmed. Your plan is now active.");
    } else if (checkout === "cancel") {
      setNotice("warning", "Upgrade canceled", "No changes were made to your plan.");
    }

    url.searchParams.delete("checkout");
    window.history.replaceState({}, "", url.toString());
  }

  async function init() {
    ensureInjectedStyles();
    ensurePaymentIntentField();
    renderEmptyState();
    bindChips();
    bindComposer();
    bindAuth();
    bindTopActions();
    autoResizeTextarea();
    bootCheckoutNotice();
    await healthCheck();
    await hydrateMe();
    await loadDashboard();
    renderUpgradePanel();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();