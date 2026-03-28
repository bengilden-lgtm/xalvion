(() => {
  "use strict";

  const API = "";
  const TOKEN_KEY = "xalvion_token";
  const USER_KEY = "xalvion_user";
  const TIER_KEY = "xalvion_tier";
  const DRAFT_KEY = "xalvion_workspace_draft";

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
    railInner: document.querySelector(".rail-inner"),
    messagesShell: document.getElementById("messagesShell"),
    upgradeButtons: Array.from(document.querySelectorAll("[data-upgrade]")),
    fillButtons: Array.from(document.querySelectorAll("[data-fill]"))
  };

  const state = {
    token: localStorage.getItem(TOKEN_KEY) || "",
    username: localStorage.getItem(USER_KEY) || "",
    tier: localStorage.getItem(TIER_KEY) || "free",
    usage: 0,
    limit: 50,
    remaining: 50,
    sending: false,
    actionsCount: 0,
    totalInteractions: 0,
    avgConfidence: 0,
    avgQuality: 0,
    latestRun: null,
    stickToBottom: true
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
        width:24px;
        padding:0;
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
        border:1px dashed rgba(255,255,255,.09);
        background:rgba(255,255,255,.025);
        color:rgba(204,216,248,.58);
        border-radius:18px;
        padding:20px 18px;
        display:flex;
        flex-direction:column;
        gap:8px;
        align-items:flex-start;
        max-width:720px;
      }

      .empty-state strong{
        font-size:13px;
        letter-spacing:.02em;
        color:rgba(242,246,255,.94);
      }

      .empty-state span{
        font-size:13px;
        line-height:1.65;
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

  function headers(withJson = true) {
    const out = {};
    if (withJson) out["Content-Type"] = "application/json";
    if (state.token) out.Authorization = `Bearer ${state.token}`;
    return out;
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
    persistAuth();
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
    return Number.isFinite(num) ? num.toFixed(digits) : (digits ? (0).toFixed(digits) : "0");
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
    state.tier = tier || "free";
    state.usage = Number.isFinite(Number(usage)) ? Number(usage) : 0;
    state.limit = Number.isFinite(Number(limit)) && Number(limit) > 0 ? Number(limit) : 50;
    state.remaining = Number.isFinite(Number(remaining)) ? Number(remaining) : Math.max(0, state.limit - state.usage);

    setText(els.planTier, formatTier(state.tier));
    setText(els.planUsage, `${state.usage} / ${state.limit}`);
    setText(els.planUsed, `Used ${state.usage}`);
    setText(els.planRemaining, `Remaining ${state.remaining}`);

    if (els.planBar) {
      const width = Math.min(100, Math.max(0, (state.usage / Math.max(1, state.limit)) * 100));
      els.planBar.style.width = `${width}%`;
    }

    if (els.usagePanelCopy) els.usagePanelCopy.textContent = planCopy(state.tier);
    persistAuth();
  }

  function actionLabel(data) {
    const action = String(data?.action || "none").toLowerCase();
    const amount = Number(data?.amount || 0);

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
    const decision = data.decision || {};
    const triage = data.triage || {};
    return String(decision.risk_level || triage.risk_level || "medium");
  }

  function updateTopbarStatus() {
    if (els.workspaceHeadline) {
      els.workspaceHeadline.textContent = state.username
        ? `AI support operator for ${state.username}`
        : "AI support that resolves cases with visible reasoning and controlled action flow";
    }

    if (els.workspaceSubcopy) {
      if (state.latestRun) {
        const decision = state.latestRun.decision || {};
        els.workspaceSubcopy.textContent =
          `${formatTier(state.tier)} plan · ${actionLabel(state.latestRun)} · ${queueLabel(decision.queue || "new")} queue · ${formatMetric(state.latestRun.confidence || 0, 2)} confidence.`;
      } else {
        els.workspaceSubcopy.textContent = state.username
          ? `${formatTier(state.tier)} plan · live response loop · action visibility · premium support execution.`
          : "Guest preview · response ready · visible action handling and premium support presentation.";
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
      els.systemPanelCopy.textContent =
        "Use a common case type to prefill the composer and test response quality quickly.";
      return;
    }

    const decision = data.decision || {};
    const triage = data.triage || {};
    const parts = [
      `${actionLabel(data)} selected`,
      `${queueLabel(decision.queue || "new")} queue`,
      `${String(decision.risk_level || triage.risk_level || "medium")} risk`,
      `${decision.requires_approval ? "approval gate active" : "safe to continue"}`
    ];

    els.systemPanelCopy.textContent = parts.join(" · ");
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
      <strong>Workspace ready</strong>
      <span>Run a support case below and stream the response into this thread with readable action context and premium presentation.</span>
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
    const initial = initialText
      ? escapeHtml(initialText).replace(/\n/g, "<br>")
      : createTypingMarkup();
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
    const decision = data.decision || {};

    meta.appendChild(createMetaChip({
      icon: ICONS.pulse,
      text: `${formatMetric(confidence, 2)} conf`,
      tone: confidenceTone(confidence)
    }));

    meta.appendChild(createMetaChip({
      icon: ICONS.spark,
      text: actionLabel(data)
    }));

    meta.appendChild(createMetaChip({
      icon: ICONS.ticket,
      text: queueLabel(decision.queue || "new")
    }));

    meta.appendChild(createMetaChip({
      icon: ICONS.shield,
      text: `${riskLabel(data)} risk`
    }));

    return meta;
  }

  function addCopyControl(container, replyText) {
    const tools = document.createElement("div");
    tools.className = "assistant-tools";

    const copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.className = "mini-btn copy-btn";
    copyBtn.innerHTML = ICONS.copy;
    copyBtn.setAttribute("aria-label", "Copy response");

    copyBtn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(replyText || "");
        copyBtn.innerHTML = ICONS.check;
        window.setTimeout(() => { copyBtn.innerHTML = ICONS.copy; }, 1200);
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

  function createDetailsPanel(data = {}) {
    const details = document.createElement("details");
    details.className = "details-wrap";

    const decision = data.decision || {};
    const triage = data.triage || {};
    const output = data.output || {};
    const impact = data.impact || {};
    const toolStatus = String(data.tool_status || "resolved");
    const internalNote = data.reason || output.internal_note || "";

    details.innerHTML = `
      <summary class="details-toggle">
        <span>View details</span>
        <span class="chev">${ICONS.chevron}</span>
      </summary>
      <div class="details-panel">
        <div class="details-grid">
          ${createDetailBox("Action", actionLabel(data))}
          ${createDetailBox("Queue", queueLabel(decision.queue || "new"))}
          ${createDetailBox("Risk", riskLabel(data))}
          ${createDetailBox("Priority", String(decision.priority || "medium"))}
          ${createDetailBox("Tool status", toolStatus)}
          ${createDetailBox("Value", formatMoney(impact.money_saved || impact.amount || data.amount || 0))}
        </div>
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

  function buildSupportPayload() {
    return {
      message: (els.messageInput?.value || "").trim(),
      payment_intent_id: normalizeReference("pi_"),
      charge_id: normalizeReference("ch_")
    };
  }

  function normalizeReference(prefix) {
    const value = (els.paymentIntentInput?.value || "").trim();
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

    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "Request failed");
    return data;
  }

  async function handleStreamReply(payload, row, stepsEl) {
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
        const parsedEvents = parseSseEvents(`${part}\n\n`);
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
        }
      }
    }

    if (buffer.trim()) {
      const parsedEvents = parseSseEvents(buffer);
      for (const item of parsedEvents) {
        if (item.event === "result") finalData = item.data;
      }
    }

    return finalData;
  }

  function updateStatsFromResult(data = {}) {
    state.totalInteractions += 1;
    state.avgConfidence = state.totalInteractions === 1
      ? Number(data.confidence || 0)
      : ((state.avgConfidence * (state.totalInteractions - 1)) + Number(data.confidence || 0)) / state.totalInteractions;

    state.avgQuality = state.totalInteractions === 1
      ? Number(data.quality || 0)
      : ((state.avgQuality * (state.totalInteractions - 1)) + Number(data.quality || 0)) / state.totalInteractions;

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
          <div class="panel-title">Latest run</div>
          <div class="panel-copy">Visible operating output makes the product feel real, not hidden behind a reply.</div>
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
      </div>
      <div class="ops-run-line" id="opsRunNarrative">${ICONS.spark}<span>Waiting for the next support run.</span></div>
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
    const latestNarrative = document.getElementById("opsRunNarrative");

    const decision = data.decision || {};
    const triage = data.triage || {};
    const impact = data.impact || {};

    if (latestAction) latestAction.textContent = actionLabel(data);
    if (latestQueue) latestQueue.textContent = queueLabel(decision.queue || "new");
    if (latestConfidence) latestConfidence.textContent = formatMetric(data.confidence || 0, 2);
    if (latestValue) latestValue.textContent = formatMoney(impact.money_saved || impact.amount || data.amount || 0);

    if (latestNarrative) {
      const reason = data.reason || "No explicit reasoning returned.";
      const approval = decision.requires_approval ? "Approval gate active" : "Automated flow complete";
      const risk = String(decision.risk_level || triage.risk_level || "medium");
      latestNarrative.innerHTML = `${ICONS.spark}<span>${escapeHtml(`${reason} · ${approval} · ${risk} risk.`)}</span>`;
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
    const autoRate = state.totalInteractions > 0
      ? Math.round((state.actionsCount / state.totalInteractions) * 100)
      : 0;
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
          ].map(([key, desc]) => `
            <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 12px;border-radius:14px;border:1px solid rgba(255,255,255,.06);background:rgba(255,255,255,.025);">
              <div style="font-size:13px;color:rgba(224,234,255,.9);">${escapeHtml(desc)}</div>
              <div style="font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;color:rgba(196,211,248,.74);">${escapeHtml(key)}</div>
            </div>
          `).join("")}
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
      } catch {
        data = await handleStandardReply(payload);
        setAssistantCopy(row, data.reply || "No response returned.");
      }

      stepTimers.forEach((timer) => window.clearTimeout(timer));
      removeStreamSteps(stepsEl);

      if (!data) throw new Error("No response returned.");

      state.latestRun = data;

      const replyText = data.reply || data.response || data.final || "No response returned.";
      setAssistantCopy(row, replyText);

      const footer = getAssistantFooterNode(row);
      if (footer) {
        footer.innerHTML = "";
        footer.appendChild(createMetaRow(data));

        const toolsWrap = document.createElement("div");
        addCopyControl(toolsWrap, replyText);
        footer.appendChild(toolsWrap);

        const details = createDetailsPanel(data);
        footer.parentElement.appendChild(details);
      }

      updateStatsFromResult(data);
      updateRevenueCard(data);
      updateLatestRunCard(data);
      updateSystemNarrative(data);

      if (data.tier) {
        updatePlanUI(
          data.tier,
          Number(data.usage || state.usage || 0),
          Number(data.plan_limit || state.limit || 50),
          Number(data.remaining || state.remaining || 0)
        );
      }

      if (data.username && data.username !== "guest" && data.username !== "dev_user") {
        state.username = data.username;
        persistAuth();
      }

      updateTopbarStatus();
      setNotice(
        data.action === "review" ? "warning" : "success",
        data.action === "review" ? "Manual review triggered" : "Case processed",
        replyText
      );
    } catch (error) {
      stepTimers.forEach((timer) => window.clearTimeout(timer));
      removeStreamSteps(stepsEl);
      setAssistantCopy(row, "Something went wrong while processing this support request.");
      setNotice("error", "Request failed", error.message || "Support request failed.");
    } finally {
      setSending(false);
      scrollMessagesToBottom(true);
      refreshMessageShellGlow();
    }
  }

  async function signup() {
    const username = (els.usernameInput?.value || "").trim();
    const password = (els.passwordInput?.value || "").trim();

    if (!username || !password) {
      setNotice("warning", "Missing credentials", "Enter a username and password to create your workspace account.");
      return;
    }

    try {
      const res = await fetch(`${API}/signup`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ username, password })
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Signup failed.");

      setNotice("success", "Account created", "Log in to keep usage, plan status, and workspace state persistent.");
      state.tier = data.tier || "free";
      updatePlanUI(state.tier, 0, 50, 50);
      updateTopbarStatus();
    } catch (error) {
      setNotice("error", "Signup failed", error.message || "Could not create account.");
    }
  }

  async function login() {
    const username = (els.usernameInput?.value || "").trim();
    const password = (els.passwordInput?.value || "").trim();

    if (!username || !password) {
      setNotice("warning", "Missing credentials", "Enter your username and password to log in.");
      return;
    }

    try {
      const res = await fetch(`${API}/login`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ username, password })
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Invalid credentials.");

      state.token = data.token || "";
      state.username = username;
      updatePlanUI(
        data.tier || "free",
        Number(data.usage || 0),
        Number(data.limit || 50),
        Number(data.remaining || 0)
      );

      persistAuth();
      updateTopbarStatus();
      setNotice("success", "Logged in", `Welcome back, ${username}. Your workspace is synced.`);
      await hydrateMe();
      await loadDashboardSummary();
    } catch (error) {
      clearAuth();
      updateTopbarStatus();
      updatePlanUI("free", 0, 50, 50);
      setNotice("error", "Login failed", error.message || "Could not log in.");
    }
  }

  async function logout() {
    clearAuth();
    updatePlanUI("free", 0, 50, 50);
    updateTopbarStatus();
    setNotice("success", "Logged out", "Guest workspace restored.");
    await hydrateMe();
    await loadDashboardSummary();
  }

  function activatePreviewAccess() {
    const demoText = "A customer says: I was charged twice for one order and wants it fixed today.";
    if (els.messageInput) {
      els.messageInput.value = demoText;
      autoResizeTextarea();
      saveDraft(demoText);
      els.messageInput.focus();
    }
    setNotice("info", "Preview access loaded", "A high-intent billing case is ready to run through the workspace.");
  }

  async function upgradePlan(tier) {
    if (!tier) return;

    if (!state.token || !state.username) {
      setNotice("warning", "Authentication required", "Create an account or log in before upgrading the workspace plan.");
      return;
    }

    try {
      const res = await fetch(`${API}/billing/upgrade`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ tier })
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Upgrade failed.");

      if (data.checkout_url) {
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
        setNotice("warning", "Backend delayed", "The API is responding slowly or partially. The workspace will retry automatically.");
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
      updateAuthStatus();
      return;
    }

    try {
      const res = await fetch(`${API}/me`, { headers: headers(false) });
      if (!res.ok) throw new Error("me failed");

      const data = await res.json().catch(() => ({}));

      state.username = data.username || state.username;
      updatePlanUI(
        data.tier || state.tier,
        Number(data.usage || state.usage),
        Number(data.limit || state.limit),
        Number(data.remaining || state.remaining)
      );

      persistAuth();
      updateTopbarStatus();
    } catch {
      updateTopbarStatus();
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

    els.messageInput?.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey && !event.metaKey && !event.ctrlKey) {
        event.preventDefault();
        sendMessage();
      }
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
      button.addEventListener("click", () => {
        upgradePlan(button.dataset.upgrade || "");
      });
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
      }
    });
  }

  async function init() {
    ensureInjectedStyles();
    buildKeyboardOverlay();
    ensureOpsCard();
    bindEvents();

    const draft = loadDraft();
    if (els.messageInput && draft) {
      els.messageInput.value = draft;
    }

    autoResizeTextarea();
    updateTopbarStatus();
    updatePlanUI(state.tier, state.usage, state.limit, state.remaining);
    updateSystemNarrative(null);
    updateStreamStatus("Response: ready");
    updateAuthStatus();
    addEmptyState();
    scrollMessagesToBottom(true);
    setSending(false);

    await healthCheck();
    await hydrateMe();
    await loadDashboardSummary();

    if (!state.username) {
      setNotice("info", "Preview access", "Preview ready. Run a customer issue or create an account.");
    } else {
      setNotice("success", "Workspace synced", `Signed in as ${state.username}. The operator workspace is ready.`);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();