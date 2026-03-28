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
    latestAction: "",
    latestStatus: "",
    actionsCount: 0,
    totalInteractions: 0,
    avgConfidence: 0,
    avgQuality: 0
  };

  const ICONS = {
    copy: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <rect x="5" y="5" width="8" height="8" rx="1.5"></rect>
        <path d="M3 11V3a1 1 0 011-1h8"></path>
      </svg>
    `,
    send: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M13.5 2.5L7 9"></path>
        <path d="M13.5 2.5L9 13.5 7 9l-4.5-2 11-5z"></path>
      </svg>
    `,
    check: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M3 8l3.5 3.5L13 4"></path>
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
    spark: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M8 1.8l1.2 3 3 1.2-3 1.2-1.2 3-1.2-3-3-1.2 3-1.2 1.2-3Z"></path>
        <path d="M12.4 10.8l.6 1.6 1.6.6-1.6.6-.6 1.6-.6-1.6-1.6-.6 1.6-.6.6-1.6Z"></path>
      </svg>
    `,
    crown: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M2 12.5h12"></path>
        <path d="M3 12.5 2.2 5.5l3.4 2.4L8 3l2.4 4.9 3.4-2.4-.8 7"></path>
      </svg>
    `,
    bolt: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M8.8 1.5 3.5 8h3.2L6.1 14.5 12.5 7.2H9.2l-.4-5.7Z"></path>
      </svg>
    `,
    money: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <rect x="1.5" y="4" width="13" height="9" rx="2"></rect>
        <path d="M8 7.5a1.5 1.5 0 100 3 1.5 1.5 0 000-3z"></path>
        <path d="M4.5 9h-.5M12 9h-.5"></path>
      </svg>
    `,
    shield: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M8 2L3 4v4c0 3 2.5 5.5 5 6 2.5-.5 5-3 5-6V4L8 2z"></path>
      </svg>
    `,
    search: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="6.5" cy="6.5" r="4"></circle>
        <path d="M13 13l-3-3"></path>
      </svg>
    `,
    person: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="8" cy="5.5" r="2.5"></circle>
        <path d="M3 13c0-2.76 2.24-5 5-5s5 2.24 5 5"></path>
      </svg>
    `,
    pulse: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M1 8h2.5l2-4.5 2.5 9L10 6l1.5 2H15"></path>
      </svg>
    `,
    warn: `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M8 2L1.5 13h13L8 2z"></path>
        <path d="M8 6v3.5"></path>
        <path d="M8 11.5h.01"></path>
      </svg>
    `
  };

  function ensureInjectedStyles() {
    if (document.getElementById("xalvion-runtime-styles")) return;

    const style = document.createElement("style");
    style.id = "xalvion-runtime-styles";
    style.textContent = `
      .msg-group{
        display:flex;
        flex-direction:column;
        gap:10px;
        animation:xalvionIn .22s cubic-bezier(.22,1,.36,1) both;
      }
      .msg-group.user{align-items:flex-end;}
      .msg-group.assistant{align-items:flex-start;}

      @keyframes xalvionIn{
        from{opacity:0;transform:translateY(10px) scale(.99);}
        to{opacity:1;transform:translateY(0) scale(1);}
      }

      .msg-card{
        width:min(860px, 100%);
        max-width:min(860px, 100%);
        border-radius:18px;
        border:1px solid rgba(255,255,255,.07);
        overflow:hidden;
        box-shadow:0 16px 40px rgba(0,0,0,.16);
        position:relative;
      }

      .msg-card.user{
        background:
          linear-gradient(180deg, rgba(90,120,255,.18), rgba(90,120,255,.10)),
          rgba(255,255,255,.03);
        border-color:rgba(125,145,255,.22);
      }

      .msg-card.assistant{
        background:
          linear-gradient(180deg, rgba(255,255,255,.04), rgba(255,255,255,.022)),
          radial-gradient(circle at 84% 18%, rgba(139,111,255,.08), transparent 32%);
      }

      .msg-head{
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:10px;
        padding:12px 14px 10px;
        border-bottom:1px solid rgba(255,255,255,.05);
      }

      .msg-who{
        display:flex;
        align-items:center;
        gap:8px;
        min-width:0;
        font-size:11px;
        text-transform:uppercase;
        letter-spacing:.12em;
        color:rgba(188,202,240,.58);
        font-weight:700;
      }

      .msg-badge{
        width:20px;
        height:20px;
        border-radius:7px;
        display:flex;
        align-items:center;
        justify-content:center;
        background:rgba(255,255,255,.05);
        border:1px solid rgba(255,255,255,.07);
        flex:0 0 20px;
      }

      .msg-badge svg{
        width:11px;
        height:11px;
        opacity:.9;
      }

      .msg-time{
        white-space:nowrap;
        color:rgba(175,191,233,.44);
        font-size:11px;
        letter-spacing:.08em;
        text-transform:uppercase;
      }

      .msg-body{
        padding:14px 14px 12px;
        display:flex;
        flex-direction:column;
        gap:12px;
      }

      .reply-text{
        font-size:14px;
        line-height:1.74;
        color:rgba(239,244,255,.96);
        word-break:break-word;
      }

      .msg-actions{
        display:flex;
        flex-direction:column;
        gap:10px;
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
        max-width:660px;
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

      .assistant-tools{
        display:flex;
        align-items:center;
        gap:8px;
        flex-wrap:wrap;
        margin-top:2px;
      }

      .mini-btn{
        display:inline-flex;
        align-items:center;
        justify-content:center;
        gap:8px;
        min-height:34px;
        padding:0 12px;
        border-radius:11px;
        border:1px solid rgba(255,255,255,.08);
        background:rgba(255,255,255,.045);
        color:rgba(232,238,255,.92);
        box-shadow:0 8px 20px rgba(0,0,0,.14), inset 0 1px 0 rgba(255,255,255,.04);
        transition:transform .16s ease, background .16s ease, border-color .16s ease;
        cursor:pointer;
        font-size:12px;
        font-weight:700;
      }

      .mini-btn:hover{
        transform:translateY(-1px);
        background:rgba(255,255,255,.075);
        border-color:rgba(255,255,255,.14);
      }

      .mini-btn svg{
        width:14px;
        height:14px;
      }

      .copy-btn{
        width:36px;
        min-width:36px;
        padding:0;
      }

      .conf-badge{
        display:inline-flex;
        align-items:center;
        gap:6px;
        min-height:22px;
        padding:0 8px;
        border-radius:999px;
        border:1px solid rgba(255,255,255,.08);
        background:rgba(255,255,255,.04);
        font-size:10px;
        font-weight:800;
        letter-spacing:.08em;
        text-transform:uppercase;
      }

      .conf-badge svg{
        width:10px;
        height:10px;
      }

      .conf-badge.safe{
        border-color:rgba(52,211,153,.18);
        background:rgba(52,211,153,.08);
        color:rgba(199,255,226,.96);
      }

      .conf-badge.review{
        border-color:rgba(245,158,11,.18);
        background:rgba(245,158,11,.08);
        color:rgba(255,233,187,.96);
      }

      .conf-badge.risky{
        border-color:rgba(248,113,113,.18);
        background:rgba(248,113,113,.08);
        color:rgba(255,214,214,.96);
      }

      .stream-steps{
        display:grid;
        gap:8px;
        margin-bottom:4px;
      }

      .stream-step{
        display:flex;
        align-items:center;
        gap:9px;
        min-height:32px;
        padding:0 11px;
        border-radius:12px;
        border:1px solid rgba(255,255,255,.06);
        background:rgba(255,255,255,.028);
        color:rgba(206,219,250,.66);
        font-size:11px;
        letter-spacing:.08em;
        text-transform:uppercase;
        font-weight:700;
        transition:all .18s ease;
      }

      .stream-step-dot{
        width:8px;
        height:8px;
        border-radius:50%;
        background:rgba(255,255,255,.20);
        box-shadow:0 0 0 rgba(255,255,255,0);
        transition:all .18s ease;
      }

      .stream-step.active{
        border-color:rgba(79,158,255,.18);
        background:rgba(79,158,255,.08);
        color:rgba(224,236,255,.96);
      }

      .stream-step.active .stream-step-dot{
        background:#60a5fa;
        box-shadow:0 0 10px rgba(96,165,250,.55);
      }

      .stream-step.done{
        border-color:rgba(52,211,153,.16);
        background:rgba(52,211,153,.08);
        color:rgba(212,255,232,.94);
      }

      .stream-step.done .stream-step-dot{
        background:#34d399;
        box-shadow:0 0 10px rgba(52,211,153,.55);
      }

      .memory-card{
        display:grid;
        gap:10px;
        border-radius:16px;
        border:1px solid rgba(255,255,255,.07);
        background:
          linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.016)),
          radial-gradient(circle at 84% 16%, rgba(139,111,255,.08), transparent 28%);
        padding:12px;
      }

      .memory-card-head{
        display:flex;
        align-items:center;
        gap:8px;
      }

      .memory-card-head svg{
        width:14px;
        height:14px;
        color:rgba(196,211,248,.9);
      }

      .memory-card-title{
        font-size:11px;
        letter-spacing:.12em;
        text-transform:uppercase;
        font-weight:800;
        color:rgba(190,204,240,.56);
      }

      .memory-card-body{
        display:flex;
        flex-wrap:wrap;
        gap:8px;
      }

      .memory-pill{
        display:inline-flex;
        align-items:center;
        gap:6px;
        min-height:28px;
        padding:0 10px;
        border-radius:999px;
        border:1px solid rgba(255,255,255,.07);
        background:rgba(255,255,255,.04);
        color:rgba(225,233,252,.82);
        font-size:11px;
        line-height:1.3;
      }

      .action-visibility{
        display:grid;
        gap:10px;
        margin-top:2px;
        border-radius:18px;
        border:1px solid rgba(255,255,255,.07);
        background:
          linear-gradient(180deg, rgba(255,255,255,.032), rgba(255,255,255,.018)),
          radial-gradient(circle at 88% 18%, rgba(139,111,255,.08), transparent 28%);
        box-shadow:0 12px 34px rgba(0,0,0,.11), inset 0 1px 0 rgba(255,255,255,.03);
        padding:12px;
        position:relative;
        overflow:hidden;
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

      .action-visibility.success::before{
        background:linear-gradient(180deg, rgba(110,231,183,.92), rgba(110,231,183,.16));
      }

      .action-visibility.warning::before{
        background:linear-gradient(180deg, rgba(252,211,77,.92), rgba(252,211,77,.16));
      }

      .action-visibility.info::before{
        background:linear-gradient(180deg, rgba(96,165,250,.92), rgba(96,165,250,.16));
      }

      .action-visibility-head{
        display:flex;
        align-items:flex-start;
        justify-content:space-between;
        gap:10px;
      }

      .action-visibility-title{
        display:flex;
        align-items:flex-start;
        gap:9px;
        min-width:0;
      }

      .action-visibility-icon-wrap{
        width:24px;
        height:24px;
        border-radius:9px;
        flex:0 0 24px;
        display:flex;
        align-items:center;
        justify-content:center;
        background:rgba(255,255,255,.04);
        border:1px solid rgba(255,255,255,.07);
        color:rgba(228,234,252,.92);
      }

      .action-visibility.success .action-visibility-icon-wrap{
        background:rgba(52,211,153,.08);
        border-color:rgba(52,211,153,.18);
        color:rgba(110,231,183,.96);
      }

      .action-visibility.warning .action-visibility-icon-wrap{
        background:rgba(245,158,11,.08);
        border-color:rgba(245,158,11,.18);
        color:rgba(252,211,77,.98);
      }

      .action-visibility.info .action-visibility-icon-wrap{
        background:rgba(59,130,246,.08);
        border-color:rgba(59,130,246,.18);
        color:rgba(147,197,253,.98);
      }

      .action-visibility-icon-wrap svg{
        width:12px;
        height:12px;
      }

      .action-visibility-title-stack{
        min-width:0;
        display:flex;
        flex-direction:column;
        gap:2px;
      }

      .action-visibility-title-text{
        font-size:11px;
        letter-spacing:.14em;
        text-transform:uppercase;
        font-weight:800;
        color:rgba(188,201,238,.62);
        white-space:nowrap;
      }

      .action-visibility-kicker{
        font-size:12px;
        font-weight:700;
        color:rgba(234,240,255,.94);
      }

      .action-visibility-badge{
        font-size:10px;
        font-weight:700;
        letter-spacing:.10em;
        text-transform:uppercase;
        color:rgba(218,227,252,.78);
        border:1px solid rgba(255,255,255,.08);
        background:rgba(255,255,255,.04);
        border-radius:999px;
        padding:4px 8px;
        white-space:nowrap;
      }

      .action-visibility-body{
        display:grid;
        gap:9px;
      }

      .action-visibility-line{
        font-size:14px;
        line-height:1.65;
        color:rgba(236,242,255,.96);
      }

      .action-visibility-sub{
        font-size:12px;
        line-height:1.58;
        color:rgba(191,205,240,.72);
      }

      .action-visibility-meta{
        display:flex;
        flex-wrap:wrap;
        gap:8px;
      }

      .action-visibility-pill{
        display:inline-flex;
        align-items:center;
        gap:6px;
        min-height:28px;
        padding:0 10px;
        border-radius:999px;
        border:1px solid rgba(255,255,255,.07);
        background:rgba(255,255,255,.03);
        font-size:11px;
        color:rgba(205,218,250,.78);
      }

      .action-visibility-pill svg{
        width:11px;
        height:11px;
        opacity:.76;
      }

      .action-visibility-pill strong{
        font-size:10px;
        letter-spacing:.08em;
        text-transform:uppercase;
        color:rgba(160,180,228,.48);
      }

      .impact-grid{
        display:grid;
        grid-template-columns:repeat(2, minmax(0, 1fr));
        gap:8px;
      }

      .impact-box{
        display:grid;
        gap:4px;
        padding:10px;
        border-radius:14px;
        border:1px solid rgba(255,255,255,.06);
        background:rgba(255,255,255,.028);
      }

      .impact-label{
        font-size:10px;
        letter-spacing:.12em;
        text-transform:uppercase;
        font-weight:800;
        color:rgba(188,201,238,.48);
      }

      .impact-value{
        font-size:14px;
        font-weight:800;
        color:rgba(240,245,255,.96);
      }

      .next-actions{
        display:flex;
        flex-wrap:wrap;
        gap:8px;
      }

      .next-action-chip{
        display:inline-flex;
        align-items:center;
        gap:8px;
        min-height:30px;
        padding:0 11px;
        border-radius:999px;
        border:1px solid rgba(255,255,255,.08);
        background:rgba(255,255,255,.04);
        color:rgba(228,236,254,.88);
        font-size:11px;
        font-weight:700;
      }

      .next-action-chip svg{
        width:12px;
        height:12px;
      }

      .typing{
        display:inline-flex;
        align-items:center;
        gap:6px;
      }

      .typing-dot{
        width:6px;
        height:6px;
        border-radius:50%;
        background:rgba(220,232,255,.52);
        animation:xalvionTyping 1s infinite ease-in-out;
      }

      .typing-dot:nth-child(2){animation-delay:.12s;}
      .typing-dot:nth-child(3){animation-delay:.24s;}

      @keyframes xalvionTyping{
        0%,80%,100%{transform:translateY(0);opacity:.4;}
        40%{transform:translateY(-3px);opacity:1;}
      }

      .rev-card{
        border-radius:22px;
        padding:14px;
        background:rgba(255,255,255,.03);
        border:1px solid rgba(255,255,255,.06);
        display:grid;
        gap:12px;
        transition:border-color .16s ease, background .16s ease, transform .16s ease;
      }

      .rev-card:hover{
        border-color:rgba(139,111,255,.10);
        background:rgba(255,255,255,.035);
        transform:translateY(-1px);
      }

      .rev-grid{
        display:grid;
        grid-template-columns:1fr 1fr;
        gap:8px;
      }

      .rev-metric{
        border-radius:14px;
        border:1px solid rgba(255,255,255,.06);
        background:rgba(255,255,255,.028);
        padding:10px;
        display:grid;
        gap:4px;
      }

      .rev-metric-label{
        font-size:10px;
        letter-spacing:.12em;
        text-transform:uppercase;
        font-weight:800;
        color:rgba(188,201,238,.46);
      }

      .rev-metric-value{
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

      @media (max-width: 720px){
        .msg-card{width:100%;}
        .impact-grid,.rev-grid{grid-template-columns:1fr;}
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
    } catch {
      // ignore storage errors
    }
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
        return "Priority routing, larger history, and stronger support throughput for real ticket volume.";
      case "elite":
        return "Maximum capacity, premium routing, and the strongest Xalvion workspace controls.";
      default:
        return "Starter capacity with visible pressure so the product sells its own upgrade path.";
    }
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
    if (state.username) {
      setText(els.authStatus, `Session: ${state.username}`);
    } else {
      setText(els.authStatus, "Session: guest");
    }
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

    if (els.usagePanelCopy) {
      els.usagePanelCopy.textContent = planCopy(state.tier);
    }

    persistAuth();
  }

  function updateTopbarStatus() {
    if (els.workspaceHeadline) {
      els.workspaceHeadline.textContent = state.username
        ? `AI support operator for ${state.username}`
        : "AI support that decides, acts, and explains itself";
    }

    if (els.workspaceSubcopy) {
      els.workspaceSubcopy.textContent = state.username
        ? `${formatTier(state.tier)} plan · live response loop · action visibility · decision confidence.`
        : "Guest preview · response ready · action visibility and monetization pressure in one workspace.";
    }

    if (els.brandSubcopy) {
      els.brandSubcopy.textContent = state.username
        ? `Signed in as ${state.username}. The workspace is keeping plan state and support history persistent.`
        : "Fast, clear support responses with the right next step built in.";
    }

    updateAuthStatus();
  }

  function scrollMessagesToBottom(force = false) {
    if (!els.messages) return;
    const threshold = 180;
    const nearBottom = els.messages.scrollHeight - els.messages.scrollTop - els.messages.clientHeight < threshold;
    if (nearBottom || force) {
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
        ${role === "assistant" ? `<div class="msg-actions js-actions"></div>` : ""}
      </div>
    `;

    if (isPlaceholder) {
      card.dataset.placeholder = "true";
    }

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
      <span>Run a support issue through the composer below. Responses will stream into this thread with action state, confidence, and business context.</span>
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
    return row;
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
    node.innerHTML = escapeHtml(text || "").replace(/\n/g, "<br>");
  }

  function appendAssistantChunk(row, chunk) {
    const node = getAssistantCopyNode(row);
    if (!node) return;

    if (node.querySelector(".typing")) {
      node.innerHTML = "";
    }

    const current = node.textContent || "";
    node.innerHTML = escapeHtml(current + chunk).replace(/\n/g, "<br>");
    scrollMessagesToBottom();
  }

  function createConfidenceBadge(confidence) {
    const value = Number(confidence || 0);

    let cls = "safe";
    if (value < 0.5) cls = "risky";
    else if (value < 0.75) cls = "review";

    const el = document.createElement("span");
    el.className = `conf-badge ${cls}`;
    el.innerHTML = `
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="8" cy="8" r="4"></circle>
      </svg>
      ${value.toFixed(2)}
    `;
    return el;
  }

  function createStreamSteps() {
    const wrap = document.createElement("div");
    wrap.className = "stream-steps";
    wrap.innerHTML = `
      <div class="stream-step active"><div class="stream-step-dot"></div><span>Reviewing request</span></div>
      <div class="stream-step"><div class="stream-step-dot"></div><span>Choosing next step</span></div>
      <div class="stream-step"><div class="stream-step-dot"></div><span>Preparing response</span></div>
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
    if (!el) return;
    el.remove();
  }

  function actionIcon(action) {
    switch (String(action || "none").toLowerCase()) {
      case "refund":
        return ICONS.refund;
      case "credit":
        return ICONS.credit;
      case "review":
        return ICONS.review;
      default:
        return ICONS.status;
    }
  }

  function actionTone(data) {
    if (String(data?.action || "").toLowerCase() === "review") return "warning";
    if (String(data?.tool_status || "").toLowerCase().includes("error")) return "warning";
    if (String(data?.action || "").toLowerCase() === "none") return "info";
    return "success";
  }

  function actionLabel(data) {
    const action = String(data?.action || "none").toLowerCase();
    const amount = Number(data?.amount || 0);

    if (action === "refund") return amount > 0 ? `Refunded ${formatMoney(amount)}` : "Refund triggered";
    if (action === "credit") return amount > 0 ? `Credited ${formatMoney(amount)}` : "Credit applied";
    if (action === "review") return "Escalated to review";
    return "Response only";
  }

  function queueLabel(value) {
    const label = String(value || "new").replaceAll("_", " ");
    return label.charAt(0).toUpperCase() + label.slice(1);
  }

  function memorySummary(history = {}) {
    if (!history || typeof history !== "object") return null;

    const items = [];
    if (history.plan_tier) items.push({ key: "Plan", value: history.plan_tier });
    if (typeof history.sentiment_avg !== "undefined") items.push({ key: "Sentiment", value: `${Number(history.sentiment_avg).toFixed(1)}/10` });
    if (history.last_issue_type) items.push({ key: "Last issue", value: String(history.last_issue_type).replaceAll("_", " ") });
    if (Number(history.refund_count || 0) > 0) items.push({ key: "Refunds", value: history.refund_count });
    if (Number(history.credit_count || 0) > 0) items.push({ key: "Credits", value: history.credit_count });
    if (Number(history.complaint_count || 0) > 0) items.push({ key: "Complaints", value: history.complaint_count });
    if (Number(history.abuse_score || 0) > 0) items.push({ key: "Abuse", value: history.abuse_score });
    if (history.repeat_customer) items.push({ key: "Customer", value: "Repeat" });

    if (!items.length) return null;

    const card = document.createElement("div");
    card.className = "memory-card";
    card.innerHTML = `
      <div class="memory-card-head">
        ${ICONS.shield}
        <div class="memory-card-title">Customer context</div>
      </div>
      <div class="memory-card-body">
        ${items.map((item) => `<div class="memory-pill">${escapeHtml(item.key)}: ${escapeHtml(item.value)}</div>`).join("")}
      </div>
    `;
    return card;
  }

  function createImpactGrid(data = {}) {
    const impact = data.impact || {};
    const decision = data.decision || {};
    const triage = data.triage || {};

    const grid = document.createElement("div");
    grid.className = "impact-grid";
    grid.innerHTML = `
      <div class="impact-box">
        <div class="impact-label">Action</div>
        <div class="impact-value">${escapeHtml(actionLabel(data))}</div>
      </div>
      <div class="impact-box">
        <div class="impact-label">Queue</div>
        <div class="impact-value">${escapeHtml(queueLabel(decision.queue || "new"))}</div>
      </div>
      <div class="impact-box">
        <div class="impact-label">Risk</div>
        <div class="impact-value">${escapeHtml(String(decision.risk_level || triage.risk_level || "medium"))}</div>
      </div>
      <div class="impact-box">
        <div class="impact-label">Priority</div>
        <div class="impact-value">${escapeHtml(String(decision.priority || "medium"))}</div>
      </div>
      <div class="impact-box">
        <div class="impact-label">Confidence</div>
        <div class="impact-value">${formatMetric(data.confidence, 2)}</div>
      </div>
      <div class="impact-box">
        <div class="impact-label">Quality</div>
        <div class="impact-value">${formatMetric(data.quality, 2)}</div>
      </div>
      <div class="impact-box">
        <div class="impact-label">Saved</div>
        <div class="impact-value">${formatMoney(impact.money_saved || impact.amount || 0)}</div>
      </div>
      <div class="impact-box">
        <div class="impact-label">Tool status</div>
        <div class="impact-value">${escapeHtml(String(data.tool_status || "resolved"))}</div>
      </div>
    `;
    return grid;
  }

  function createActionVisibility(data = {}) {
    const wrap = document.createElement("div");
    const tone = actionTone(data);
    wrap.className = `action-visibility ${tone}`;

    const decision = data.decision || {};
    const output = data.output || {};
    const triage = data.triage || {};
    const impact = data.impact || {};

    const bodyLine = (() => {
      if (data.action === "refund") return `The AI approved a refund for ${formatMoney(data.amount || 0)} and drafted the customer-ready answer.`;
      if (data.action === "credit") return `The AI issued a credit for ${formatMoney(data.amount || 0)} and positioned it as a retention move.`;
      if (data.action === "review") return `The AI escalated this case for manual review instead of automating a risky action.`;
      return `The AI drafted a response without taking a direct monetary action.`;
    })();

    wrap.innerHTML = `
      <div class="action-visibility-head">
        <div class="action-visibility-title">
          <div class="action-visibility-icon-wrap">${actionIcon(data.action)}</div>
          <div class="action-visibility-title-stack">
            <div class="action-visibility-title-text">Decision engine</div>
            <div class="action-visibility-kicker">${escapeHtml(actionLabel(data))}</div>
          </div>
        </div>
        <div class="action-visibility-badge">${escapeHtml(queueLabel(decision.queue || "new"))}</div>
      </div>
      <div class="action-visibility-body">
        <div class="action-visibility-line">${escapeHtml(bodyLine)}</div>
        <div class="action-visibility-sub">${escapeHtml(String(data.reason || output.internal_note || "No internal reason supplied."))}</div>
        <div class="action-visibility-meta">
          <div class="action-visibility-pill">${ICONS.status}<span><strong>Issue</strong> ${escapeHtml(String(data.issue_type || "general_support").replaceAll("_", " "))}</span></div>
          <div class="action-visibility-pill">${ICONS.pulse}<span><strong>Risk</strong> ${escapeHtml(String(decision.risk_level || triage.risk_level || "medium"))}</span></div>
          <div class="action-visibility-pill">${ICONS.money}<span><strong>Value</strong> ${formatMoney(impact.money_saved || impact.amount || data.amount || 0)}</span></div>
          <div class="action-visibility-pill">${ICONS.shield}<span><strong>Approval</strong> ${decision.requires_approval ? "Required" : "Not needed"}</span></div>
        </div>
      </div>
    `;

    wrap.appendChild(createImpactGrid(data));
    return wrap;
  }

  function createNextActionChips(data = {}) {
    const chips = [];
    const decision = data.decision || {};
    const triage = data.triage || {};
    const action = String(data.action || "none").toLowerCase();
    const refundLikelihood = Number(triage.refund_likelihood || 0);
    const abuseLikelihood = Number(triage.abuse_likelihood || 0);

    if (action === "review") {
      chips.push({ icon: ICONS.review, text: "Manual approval next" });
    } else if (action === "refund") {
      chips.push({ icon: ICONS.refund, text: "Confirm refund notification" });
    } else if (action === "credit") {
      chips.push({ icon: ICONS.credit, text: "Watch retention response" });
    } else {
      chips.push({ icon: ICONS.spark, text: "Reply sent cleanly" });
    }

    if (decision.priority === "high") {
      chips.push({ icon: ICONS.warn, text: "High priority ticket" });
    }

    if (refundLikelihood >= 60) {
      chips.push({ icon: ICONS.money, text: "Refund pressure elevated" });
    }

    if (abuseLikelihood >= 50) {
      chips.push({ icon: ICONS.shield, text: "Fraud caution active" });
    }

    if (!chips.length) return null;

    const wrap = document.createElement("div");
    wrap.className = "next-actions";
    wrap.innerHTML = chips
      .map((chip) => `<div class="next-action-chip">${chip.icon}<span>${escapeHtml(chip.text)}</span></div>`)
      .join("");
    return wrap;
  }

  function addCopyControls(row, replyText) {
    const actionNode = getAssistantActionsNode(row);
    if (!actionNode) return;

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
      } catch {
        // ignore clipboard failures
      }
    });

    tools.appendChild(copyBtn);
    actionNode.appendChild(tools);
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
    els.messageInput.style.height = `${Math.min(220, Math.max(44, els.messageInput.scrollHeight))}px`;
  }

  function setSending(value) {
    state.sending = Boolean(value);

    if (els.sendBtn) {
      els.sendBtn.disabled = state.sending;
      els.sendBtn.classList.toggle("busy", state.sending);
      els.sendBtn.innerHTML = state.sending ? ICONS.status : ICONS.send;
    }

    if (els.messageInput) {
      els.messageInput.disabled = state.sending;
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
      } catch {
        // ignore malformed chunks
      }
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
            state.latestStatus = item.data.label || stage || "";
            if (stage === "reviewing") advanceStreamStep(stepsEl, 0);
            else if (stage === "routing") advanceStreamStep(stepsEl, 1);
            else if (stage === "acting" || stage === "responding") advanceStreamStep(stepsEl, 2);
            updateStreamStatus(`Response: ${state.latestStatus || "streaming"}`);
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
        if (item.event === "result") {
          finalData = item.data;
        }
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
            <div class="panel-copy">Make the business effect of every AI decision visible in the workspace.</div>
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

      if (els.usageCard?.parentElement) {
        els.usageCard.parentElement.appendChild(card);
      }
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
        : "The workspace is collecting action value as tickets are processed.";
    }
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

    const row = addAssistantMessage("Analyzing request…");
    const stepsEl = createStreamSteps();
    const replyNode = getAssistantCopyNode(row);
    if (replyNode) replyNode.parentElement.insertBefore(stepsEl, replyNode);

    setSending(true);
    setNotice("info", "Running support case", "Streaming action states from the support pipeline.");

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

      const replyText = data.reply || data.response || data.final || "No response returned.";
      setAssistantCopy(row, replyText);

      const whoEl = row.querySelector(".msg-who");
      if (whoEl && typeof data.confidence !== "undefined") {
        whoEl.appendChild(createConfidenceBadge(data.confidence));
      }

      addCopyControls(row, replyText);

      const actionNode = getAssistantActionsNode(row);
      if (actionNode) {
        const memCard = memorySummary(data.history || {});
        if (memCard) actionNode.appendChild(memCard);

        actionNode.appendChild(createActionVisibility(data));

        const nextActions = createNextActionChips(data);
        if (nextActions) actionNode.appendChild(nextActions);
      }

      updateStatsFromResult(data);
      updateRevenueCard(data);

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
        data.action === "review" ? "Manual review triggered" : "Ticket processed",
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

      setNotice("success", "Account created", "Now log in to keep usage and workspace state persistent.");
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
      if (data?.status === "ok") {
        updateBackendStatus(true);
      }
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
      // keep existing auth state if /me is not available
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
    addEmptyState();
    scrollMessagesToBottom(true);
  }

  function exportThread() {
    if (!els.messages) return;

    const lines = [];
    els.messages.querySelectorAll(".msg-card").forEach((card) => {
      const who = card.querySelector(".msg-who span:last-child")?.textContent || "Message";
      const text = card.querySelector(".js-reply-text")?.textContent || "";
      if (text.trim()) {
        lines.push(`${who}: ${text.trim()}`);
      }
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
      if (event.target === overlay) {
        overlay.style.display = "none";
      }
    });
  }

  function toggleKeyboardOverlay(show) {
    const overlay = document.getElementById("xalvionShortcutOverlay");
    if (!overlay) return;
    overlay.style.display = show ? "flex" : "none";
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
      }

      if (event.key === "Escape") {
        toggleKeyboardOverlay(false);
      }
    });
  }

  async function init() {
    ensureInjectedStyles();
    buildKeyboardOverlay();
    bindEvents();

    const draft = loadDraft();
    if (els.messageInput && draft) {
      els.messageInput.value = draft;
    }

    autoResizeTextarea();
    updateTopbarStatus();
    updatePlanUI(state.tier, state.usage, state.limit, state.remaining);
    updateStreamStatus("Response: ready");
    updateAuthStatus();
    addEmptyState();
    scrollMessagesToBottom(true);
    setSending(false);

    await healthCheck();
    await hydrateMe();
    await loadDashboardSummary();

    if (!state.username) {
      setNotice("info", "Preview access", "Preview · response ready · service checking completed. Run a customer issue or create an account.");
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