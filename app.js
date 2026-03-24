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
    tier: localStorage.getItem(TIER_KEY) || "dev",
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
    sparkle: `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M8 1.8l1.2 3 3 1.2-3 1.2-1.2 3-1.2-3-3-1.2 3-1.2 1.2-3Z"/><path d="M12.4 10.8l.6 1.6 1.6.6-1.6.6-.6 1.6-.6-1.6-1.6-.6 1.6-.6.6-1.6Z"/></svg>`
  };

  function ensureActionVisibilityStyles() {
    if (document.getElementById("xalvion-action-visibility-styles")) return;

    const style = document.createElement("style");
    style.id = "xalvion-action-visibility-styles";
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
        animation:xalvionActionReveal .26s cubic-bezier(.22,1,.36,1) both;
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

      .action-visibility.show{
        display:block;
      }

      .action-visibility.success::before{
        background:linear-gradient(180deg, rgba(110,231,183,.9), rgba(110,231,183,.14));
      }

      .action-visibility.warning::before{
        background:linear-gradient(180deg, rgba(252,211,77,.92), rgba(252,211,77,.16));
      }

      .action-visibility.info::before{
        background:linear-gradient(180deg, rgba(96,165,250,.92), rgba(96,165,250,.16));
      }

      .action-visibility-head{
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:12px;
        padding:11px 12px 10px;
        border-bottom:1px solid rgba(255,255,255,.05);
        background:linear-gradient(180deg, rgba(255,255,255,.02), rgba(255,255,255,.005));
      }

      .action-visibility-title{
        display:flex;
        align-items:center;
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
        box-shadow:0 0 18px rgba(52,211,153,.10);
      }

      .action-visibility.warning .action-visibility-icon-wrap{
        background:rgba(245,158,11,.08);
        border-color:rgba(245,158,11,.18);
        color:rgba(252,211,77,.98);
        box-shadow:0 0 18px rgba(245,158,11,.10);
      }

      .action-visibility.info .action-visibility-icon-wrap{
        background:rgba(59,130,246,.08);
        border-color:rgba(59,130,246,.18);
        color:rgba(147,197,253,.98);
        box-shadow:0 0 18px rgba(59,130,246,.10);
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
        white-space:nowrap;
        overflow:hidden;
        text-overflow:ellipsis;
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

      .action-visibility.success .action-visibility-badge{
        color:rgba(201,255,229,.92);
        border-color:rgba(52,211,153,.16);
        background:rgba(52,211,153,.08);
      }

      .action-visibility.warning .action-visibility-badge{
        color:rgba(255,241,194,.92);
        border-color:rgba(245,158,11,.18);
        background:rgba(245,158,11,.08);
      }

      .action-visibility.info .action-visibility-badge{
        color:rgba(219,233,255,.92);
        border-color:rgba(59,130,246,.18);
        background:rgba(59,130,246,.08);
      }

      .action-visibility-body{
        display:flex;
        flex-direction:column;
        gap:9px;
        padding:13px 12px 12px;
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
        margin-top:2px;
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

      .action-visibility-trail{
        display:flex;
        align-items:center;
        gap:8px;
        flex-wrap:wrap;
        margin-top:2px;
      }

      .action-step{
        display:inline-flex;
        align-items:center;
        gap:6px;
        min-height:26px;
        padding:0 10px;
        border-radius:999px;
        background:rgba(255,255,255,.028);
        border:1px solid rgba(255,255,255,.06);
        font-size:11px;
        color:rgba(216,226,250,.78);
      }

      .action-step svg{
        width:10px;
        height:10px;
        opacity:.82;
      }

      .action-step.done{
        color:rgba(201,255,229,.90);
        border-color:rgba(52,211,153,.16);
        background:rgba(52,211,153,.08);
      }

      .action-step.live{
        color:rgba(219,233,255,.90);
        border-color:rgba(59,130,246,.16);
        background:rgba(59,130,246,.08);
      }

      .refund-assist{
        display:grid;
        gap:8px;
        margin-bottom:8px;
      }

      .refund-assist-label{
        font-size:11px;
        letter-spacing:.14em;
        text-transform:uppercase;
        color:rgba(190,204,240,.48);
        font-weight:700;
        padding:0 2px;
      }

      .refund-assist-input{
        width:100%;
        min-width:0;
        height:40px;
        border-radius:14px;
        border:1px solid rgba(255,255,255,.08);
        background:rgba(9,12,24,.42);
        color:rgba(241,246,255,.96);
        padding:0 14px;
        font-size:13px;
        outline:none;
        transition:border-color .16s ease, background .16s ease, box-shadow .16s ease, transform .16s ease;
      }

      .refund-assist-input::placeholder{
        color:rgba(210,222,250,.34);
      }

      .refund-assist-input:hover{
        background:rgba(9,12,24,.50);
        border-color:rgba(255,255,255,.10);
      }

      .refund-assist-input:focus{
        border-color:rgba(139,111,255,.28);
        background:rgba(10,13,26,.54);
        box-shadow:0 0 0 3px rgba(139,111,255,.08);
      }

      @keyframes xalvionActionReveal{
        from{opacity:0;transform:translateY(6px) scale(.995)}
        to{opacity:1;transform:translateY(0) scale(1)}
      }

      @media (max-width:900px){
        .action-visibility{
          margin-left:15px;
        }
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
    label.textContent = "Refund testing";

    const input = document.createElement("input");
    input.type = "text";
    input.id = "paymentIntentInput";
    input.className = "refund-assist-input";
    input.placeholder = "Paste Stripe payment_intent_id (pi_...) or charge_id (ch_...)";

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
    state.tier = "dev";
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
    if (tier === "dev") return "preview";
    return tier;
  }

  function getPlanCopy() {
    const tier = (state.tier || "free").toLowerCase();

    if (tier === "free") {
      return {
        usage:
          "You are on the Free plan. As usage grows, you can upgrade for more monthly capacity and a larger support workspace."
      };
    }

    if (tier === "pro") {
      return {
        usage:
          "You are on the Pro plan with expanded monthly capacity and priority routing for higher support volume."
      };
    }

    if (tier === "elite") {
      return {
        usage:
          "You are on the Elite plan with the highest monthly capacity and advanced access across the workspace."
      };
    }

    return {
      usage:
        "You are in preview access with full workspace availability while you test the support experience."
    };
  }

  function updateTopbarStatus() {
    const tier = getVisibleTierLabel();
    const usage = Number.isFinite(state.usage) ? state.usage : 0;
    const limit = Number.isFinite(state.limit) ? state.limit : null;
    const user = state.username || "";
    const tierLabel = tier === "preview" ? "preview access" : tier;
    const usageStr = limit ? `${usage}/${limit} used` : "unlimited access";
    const userStr = user ? `${user} · ` : "";
    setText(els.workspaceSubcopy, `${userStr}${tierLabel} · ${usageStr}`);
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
      "Send a support case — get a polished reply and a visible next step."
    );
    setText(
      els.systemPanelCopy,
      "Response-ready workspace with clean output, visible progress, and clear action flow."
    );

    setText(els.usagePanelCopy, planCopy.usage);
    updateTopbarStatus();

    if (els.devBtn) {
      els.devBtn.textContent = "Preview";
      els.devBtn.setAttribute("aria-label", "Preview access");
      els.devBtn.title = "Preview access";
    }
  }

  function renderEmptyState() {
    if (!els.messages) return;

    els.messages.innerHTML = `
      <div class="empty-state">
        <div class="empty-card">
          <div class="empty-eyebrow">
            <span class="empty-eyebrow-dot"></span>
            <span>Support workspace ready</span>
          </div>
          <h1>Resolve tickets with a cleaner next step.</h1>
          <p>
            Xalvion turns support cases into a clear reply, a visible operating decision, and a usable action flow.
            Start with a billing, shipping, refund, or damaged-order case to see the workspace in motion.
          </p>

          <div class="empty-grid">
            <div class="empty-panel">
              <div class="empty-panel-label">What happens here</div>
              <div class="empty-panel-copy">
                Messages stream into a calm operator view. Decisions stay visible, actions stay usable,
                and account usage stays tied to the active workspace.
              </div>
            </div>
            <div class="empty-panel">
              <div class="empty-panel-label">Best test prompts</div>
              <div class="empty-panel-copy">
                Duplicate charge, late package, damaged order, or “where is my order” will show the clearest response flow.
              </div>
            </div>
          </div>

          <div class="empty-actions">
            <button class="chip" data-fill-inline="A customer says: I was charged twice." type="button">Try duplicate charge</button>
            <button class="chip" data-fill-inline="A customer says: My package is late and I am annoyed." type="button">Try late package</button>
            <button class="chip" data-fill-inline="A customer says: Order arrived damaged and I want this fixed now." type="button">Try damaged order</button>
            <button class="chip" data-fill-inline="A customer says: Where is my order?" type="button">Try where is my order</button>
          </div>
        </div>
      </div>
    `;

    els.messages.querySelectorAll("[data-fill-inline]").forEach((btn) => {
      btn.addEventListener("click", () => {
        fillComposer(btn.getAttribute("data-fill-inline") || "");
      });
    });

    scrollMessagesToBottom(true);
  }

  function fillComposer(text) {
    if (!els.messageInput) return;
    els.messageInput.value = text;
    autoResizeTextarea();
    els.messageInput.focus();

    const composer = els.messageInput.closest(".composer");
    if (composer) {
      composer.classList.add("highlight");
      setTimeout(() => composer.classList.remove("highlight"), 700);
    }
  }

  function buildMessage(role, initialText = "", appendNow = true) {
    const group = document.createElement("div");
    group.className = `msg-group ${role}`;

    const header = document.createElement("div");
    header.className = "msg-group-header";

    const who = document.createElement("div");
    who.className = "msg-who";
    who.textContent = role === "user" ? (state.username || "You") : "Xalvion";

    header.appendChild(who);

    const replyBody = document.createElement("div");
    replyBody.className = "reply-body";

    const replyText = document.createElement("div");
    replyText.className = "reply-text";
    if (initialText) replyText.textContent = initialText;
    replyBody.appendChild(replyText);

    const statusRow = document.createElement("div");
    statusRow.className = "status-row";

    const nextGrid = document.createElement("div");
    nextGrid.className = "customer-next";

    const actionVisibility = document.createElement("div");
    actionVisibility.className = "action-visibility";
    actionVisibility.setAttribute("aria-live", "polite");

    const actionsRow = document.createElement("div");
    actionsRow.className = "msg-actions";

    group.appendChild(header);
    group.appendChild(replyBody);

    if (role !== "user") {
      group.appendChild(statusRow);
      group.appendChild(nextGrid);
      group.appendChild(actionVisibility);
      group.appendChild(actionsRow);

      const copyBtn = document.createElement("button");
      copyBtn.className = "act-btn";
      copyBtn.type = "button";
      copyBtn.title = "Copy reply";
      copyBtn.innerHTML = `${ICONS.copy}<span>Copy</span>`;
      copyBtn.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(replyText.textContent || "");
          copyBtn.classList.add("done");
          copyBtn.innerHTML = `${ICONS.check}<span>Copied</span>`;
          setTimeout(() => {
            copyBtn.classList.remove("done");
            copyBtn.innerHTML = `${ICONS.copy}<span>Copy</span>`;
          }, 1600);
        } catch {}
      });

      const sep1 = document.createElement("div");
      sep1.className = "act-sep";

      const sendCustomerBtn = document.createElement("button");
      sendCustomerBtn.className = "act-btn send";
      sendCustomerBtn.type = "button";
      sendCustomerBtn.title = "Load reply into composer";
      sendCustomerBtn.innerHTML = `${ICONS.send}<span>Send to customer</span>`;
      sendCustomerBtn.addEventListener("click", () => {
        fillComposer(replyText.textContent || "");
        sendCustomerBtn.classList.add("done");
        sendCustomerBtn.innerHTML = `${ICONS.check}<span>Loaded</span>`;
        setTimeout(() => {
          sendCustomerBtn.classList.remove("done");
          sendCustomerBtn.innerHTML = `${ICONS.send}<span>Send to customer</span>`;
        }, 1600);
      });

      const sep2 = document.createElement("div");
      sep2.className = "act-sep";

      const upBtn = document.createElement("button");
      upBtn.className = "fb-btn";
      upBtn.type = "button";
      upBtn.textContent = "👍";
      upBtn.title = "Good";

      const downBtn = document.createElement("button");
      downBtn.className = "fb-btn";
      downBtn.type = "button";
      downBtn.textContent = "👎";
      downBtn.title = "Bad";

      upBtn.addEventListener("click", () => {
        upBtn.classList.toggle("up");
        downBtn.classList.remove("down");
      });

      downBtn.addEventListener("click", () => {
        downBtn.classList.toggle("down");
        upBtn.classList.remove("up");
      });

      actionsRow.appendChild(copyBtn);
      actionsRow.appendChild(sep1);
      actionsRow.appendChild(sendCustomerBtn);
      actionsRow.appendChild(sep2);
      actionsRow.appendChild(upBtn);
      actionsRow.appendChild(downBtn);
    }

    if (appendNow && els.messages) {
      const siblings = els.messages.querySelectorAll(".msg-group");
      const delay = Math.min(siblings.length * 28, 84);
      group.style.animationDelay = `${delay}ms`;
      els.messages.appendChild(group);
      scrollMessagesToBottom(true);
    }

    return { wrapper: group, replyText, statusRow, nextGrid, actionVisibility };
  }

  function setTypingBubble(node) {
    node.replyText.innerHTML = `<div class="typing"><span></span><span></span><span></span></div>`;
  }

  function setBubbleText(node, text) {
    node.replyText.textContent = text;
  }

  function renderStatuses(node, statuses) {
    if (!node.statusRow) return;
    node.statusRow.innerHTML = "";

    (statuses || []).slice(-3).forEach((text) => {
      const pill = document.createElement("div");
      pill.className = "status-pill";
      pill.textContent = text;
      node.statusRow.appendChild(pill);
    });
  }

  function normalizeDisplayedReason(meta) {
    const raw = String(meta.reason || "").trim();
    if (!raw) return "";

    if (raw === "local_fallback") {
      if (meta.action === "review") return "A quick review is needed before the next step is confirmed.";
      if (meta.action === "refund") return "This request matched an approved refund path.";
      if (meta.action === "credit") return "This request matched an approved recovery path.";
      return "The workspace completed the safest available response path.";
    }

    if (raw === "resolved") return "The workspace completed the best available response path.";
    return raw;
  }

  function renderCustomerNextStep(node, meta) {
    if (!node.nextGrid) return;
    node.nextGrid.innerHTML = "";

    const pills = [];
    const reason = normalizeDisplayedReason(meta);
    const action = String(meta.action || "none");
    const issue = String(meta.issue_type || "");
    const orderStatus = String(meta.order_status || "");

    if (action !== "none") {
      let label = "Next step";
      let value = "Moving forward.";
      let cls = "next-pill primary";

      if (action === "refund") {
        label = "Refund";
        value = meta.amount && Number(meta.amount) > 0 ? `$${meta.amount} approved` : "Approved";
      } else if (action === "credit") {
        label = "Credit";
        value = meta.amount && Number(meta.amount) > 0 ? `$${meta.amount} applied` : "Applied";
      } else if (action === "review") {
        label = "Review";
        value = issue === "damaged_order" ? "Send order # + photo" : "Review in progress";
        cls = "next-pill warning";
      }

      pills.push({ cls, label, value });
    }

    if (orderStatus && orderStatus !== "unknown") {
      const statusMap = {
        delayed: "Delayed in transit",
        shipped: "Shipped",
        delivered: "Delivered",
        processing: "Preparing"
      };

      pills.push({
        cls: "next-pill",
        label: "Order",
        value: statusMap[orderStatus] || orderStatus
      });
    } else if (reason && action === "none") {
      pills.push({
        cls: "next-pill",
        label: "Note",
        value: reason
      });
    }

    if (!pills.length) {
      pills.push({
        cls: "next-pill primary",
        label: "Status",
        value: "Response ready"
      });
    }

    pills.slice(0, 3).forEach((pillData) => {
      const el = document.createElement("div");
      el.className = pillData.cls;
      el.innerHTML = `
        <span class="pill-label">${escapeHtml(pillData.label)}</span>
        <span class="pill-value">${escapeHtml(pillData.value)}</span>
      `;
      node.nextGrid.appendChild(el);
    });
  }

  function getActionIcon(action, orderStatus) {
    const normalized = String(action || "").toLowerCase();
    if (normalized === "refund") return ICONS.refund;
    if (normalized === "credit") return ICONS.credit;
    if (normalized === "review") return ICONS.review;
    if (orderStatus && orderStatus !== "unknown") return ICONS.status;
    return ICONS.sparkle;
  }

  function normalizeActionVisibility(meta) {
    const action = String(meta.action || "none").toLowerCase();
    const amount = Number(meta.amount || 0);
    const issueType = String(meta.issue_type || "").toLowerCase();
    const orderStatus = String(meta.order_status || "").toLowerCase();
    const reason = normalizeDisplayedReason(meta);

    if (action === "refund") {
      return {
        tone: "success",
        badge: "Completed",
        title: "Action completed",
        kicker: "Refund issued",
        icon: getActionIcon(action, orderStatus),
        line: amount > 0
          ? `Refund issued — $${amount} returned to the original payment method.`
          : "Refund issued to the original payment method.",
        sub: reason || "This request matched an approved refund path.",
        pills: [
          amount > 0 ? { label: "Amount", value: `$${amount}`, icon: ICONS.refund } : null,
          { label: "Type", value: "Refund", icon: ICONS.check }
        ].filter(Boolean),
        trail: [
          { label: "Issue reviewed", state: "done", icon: ICONS.check },
          { label: "Refund confirmed", state: "done", icon: ICONS.refund }
        ]
      };
    }

    if (action === "credit") {
      return {
        tone: "success",
        badge: "Completed",
        title: "Action completed",
        kicker: "Credit applied",
        icon: getActionIcon(action, orderStatus),
        line: amount > 0
          ? `Credit applied — $${amount} added to the account.`
          : "Credit applied to the account.",
        sub: reason || "This request matched an approved recovery path.",
        pills: [
          amount > 0 ? { label: "Amount", value: `$${amount}`, icon: ICONS.credit } : null,
          { label: "Type", value: "Credit", icon: ICONS.check }
        ].filter(Boolean),
        trail: [
          { label: "Issue reviewed", state: "done", icon: ICONS.check },
          { label: "Credit applied", state: "done", icon: ICONS.credit }
        ]
      };
    }

    if (action === "review") {
      let reviewLine = "Escalated for review — next step is already in progress.";
      let reviewSub = reason || "A quick review is needed before the next step is confirmed.";
      const pills = [{ label: "Type", value: "Review", icon: ICONS.review }];
      const trail = [
        { label: "Case reviewed", state: "done", icon: ICONS.check },
        { label: "Review opened", state: "live", icon: ICONS.review }
      ];

      if (issueType === "damaged_order") {
        reviewLine = "Escalated for review — send the order number and one photo of the damage.";
        reviewSub = "This keeps the case moving with the right evidence attached from the start.";
        pills.push({ label: "Needed", value: "Order # + photo", icon: ICONS.review });
      } else if (issueType === "usage_limit") {
        reviewLine = "Usage limit reached — upgrade to keep resolving requests instantly.";
        reviewSub = reason || "This request was blocked by the current plan limit.";
        pills.push({ label: "Needed", value: "Upgrade plan", icon: ICONS.sparkle });
      }

      return {
        tone: issueType === "usage_limit" ? "warning" : "info",
        badge: issueType === "usage_limit" ? "Attention" : "In progress",
        title: issueType === "usage_limit" ? "Plan action required" : "Action opened",
        kicker: issueType === "usage_limit" ? "Upgrade needed" : "Review opened",
        icon: getActionIcon(action, orderStatus),
        line: reviewLine,
        sub: reviewSub,
        pills,
        trail
      };
    }

    if (orderStatus && orderStatus !== "unknown") {
      const map = {
        delayed: "Order status checked — currently delayed in transit.",
        shipped: "Order status checked — the shipment is on the way.",
        delivered: "Order status checked — the order shows as delivered.",
        processing: "Order status checked — the order is still being prepared."
      };

      const prettyStatus = {
        delayed: "Delayed",
        shipped: "Shipped",
        delivered: "Delivered",
        processing: "Preparing"
      };

      return {
        tone: "info",
        badge: "Checked",
        title: "Action completed",
        kicker: "Order checked",
        icon: getActionIcon(action, orderStatus),
        line: map[orderStatus] || `Order status checked — ${orderStatus}.`,
        sub: reason || "The latest order state has been surfaced in the reply.",
        pills: [
          { label: "Type", value: "Status check", icon: ICONS.status },
          { label: "Order", value: prettyStatus[orderStatus] || orderStatus, icon: ICONS.check }
        ],
        trail: [
          { label: "Case reviewed", state: "done", icon: ICONS.check },
          { label: "Status checked", state: "done", icon: ICONS.status }
        ]
      };
    }

    if (reason) {
      return {
        tone: "info",
        badge: "Updated",
        title: "Workspace update",
        kicker: "Reply prepared",
        icon: getActionIcon(action, orderStatus),
        line: "Response prepared with the clearest available next step.",
        sub: reason,
        pills: [{ label: "Type", value: "Reply", icon: ICONS.sparkle }],
        trail: [
          { label: "Request reviewed", state: "done", icon: ICONS.check },
          { label: "Reply prepared", state: "done", icon: ICONS.sparkle }
        ]
      };
    }

    return null;
  }

  function renderActionVisibility(node, meta) {
    if (!node.actionVisibility) return;

    const model = normalizeActionVisibility(meta);
    if (!model) {
      node.actionVisibility.className = "action-visibility";
      node.actionVisibility.innerHTML = "";
      return;
    }

    const pillsHtml = (model.pills || [])
      .map((pill) => {
        return `<div class="action-visibility-pill">${pill.icon || ICONS.sparkle}<strong>${escapeHtml(pill.label)}</strong><span>${escapeHtml(pill.value)}</span></div>`;
      })
      .join("");

    const trailHtml = (model.trail || [])
      .map((step) => {
        return `<div class="action-step ${escapeHtml(step.state || "")}">${step.icon || ICONS.check}<span>${escapeHtml(step.label)}</span></div>`;
      })
      .join("");

    node.actionVisibility.className = `action-visibility ${escapeHtml(model.tone || "info")} show`;
    node.actionVisibility.innerHTML = `
      <div class="action-visibility-head">
        <div class="action-visibility-title">
          <span class="action-visibility-icon-wrap">${model.icon || ICONS.sparkle}</span>
          <div class="action-visibility-title-stack">
            <span class="action-visibility-title-text">${escapeHtml(model.title || "Action update")}</span>
            <span class="action-visibility-kicker">${escapeHtml(model.kicker || "Update")}</span>
          </div>
        </div>
        <div class="action-visibility-badge">${escapeHtml(model.badge || "Ready")}</div>
      </div>
      <div class="action-visibility-body">
        <div class="action-visibility-line">${escapeHtml(model.line || "")}</div>
        <div class="action-visibility-sub">${escapeHtml(model.sub || "")}</div>
        ${trailHtml ? `<div class="action-visibility-trail">${trailHtml}</div>` : ""}
        ${pillsHtml ? `<div class="action-visibility-meta">${pillsHtml}</div>` : ""}
      </div>
    `;
  }

  function parseRefundReference(rawValue) {
    const value = String(rawValue || "").trim();
    if (!value) {
      return {
        payment_intent_id: null,
        charge_id: null,
        error: ""
      };
    }

    if (value.startsWith("pi_")) {
      return {
        payment_intent_id: value,
        charge_id: null,
        error: ""
      };
    }

    if (value.startsWith("ch_")) {
      return {
        payment_intent_id: null,
        charge_id: value,
        error: ""
      };
    }

    return {
      payment_intent_id: null,
      charge_id: null,
      error: "Use a Stripe payment_intent_id (pi_...) or charge_id (ch_...)."
    };
  }

  function updatePlanUI(tier, usage, limit, remaining) {
    if (tier) state.tier = String(tier).toLowerCase();
    if (typeof usage === "number") state.usage = usage;
    if (typeof limit === "number") state.limit = limit >= 1000000000 ? Infinity : limit;
    if (typeof remaining === "number") state.remaining = remaining >= 1000000000 ? Infinity : remaining;

    setText(els.planTier, String(getVisibleTierLabel()).toUpperCase());
    setText(els.planUsed, String(state.usage));
    setText(els.planUsage, formatLimit(state.limit));
    setText(els.planRemaining, formatLimit(state.remaining));

    if (els.planBar) {
      let percent = 2;
      if (Number.isFinite(state.limit) && state.limit > 0) {
        percent = Math.max(2, Math.min(100, (state.usage / state.limit) * 100));
      }
      els.planBar.style.width = `${percent}%`;
    }

    persistAuth();
    updateCustomerFacingCopy();
    pulseRail("usage");
  }

  function updateDashboardUI(data) {
    if (!data) return;

    setText(els.statInteractions, formatMetric(data.total_interactions || 0, 0));
    setText(els.statQuality, formatMetric(data.avg_quality || 0));
    setText(els.statConfidence, formatMetric(data.avg_confidence || 0));
    setText(els.statActions, formatMetric(state.actions || 0, 0));

    if (
      data.your_tier ||
      data.your_usage !== undefined ||
      data.your_limit !== undefined ||
      data.remaining !== undefined
    ) {
      updatePlanUI(
        data.your_tier || state.tier,
        Number(data.your_usage ?? state.usage),
        Number(data.your_limit ?? state.limit),
        Number(data.remaining ?? state.remaining)
      );
    }

    pulseRail("dashboard");
  }

  async function checkHealth() {
    try {
      const res = await fetch(`${API}/health`);
      if (!res.ok) throw new Error("Health check failed");
      setText(els.backendStatus, "Status: online");
      setNotice("success", "Response ready", "Workspace ready");
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
      state.tier = data.tier || state.tier || "dev";
      persistAuth();

      updatePlanUI(
        data.tier || "dev",
        Number(data.usage || 0),
        Number(data.limit || 1000000000),
        Number(data.remaining || 1000000000)
      );

      setText(
        els.authStatus,
        data.username ? `Account: ${data.username}` : "Account: preview access"
      );
    } catch {
      clearAuth();
      updatePlanUI("dev", 0, Infinity, Infinity);
      setText(els.authStatus, "Account: preview access");
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
    updatePlanUI("dev", 0, Infinity, Infinity);
    setText(els.authStatus, "Account: preview access");
    setNotice("info", "Preview access", "Unlimited testing active");
    pulseRail("account");
  }

  function logout() {
    clearAuth();
    updatePlanUI("dev", 0, Infinity, Infinity);
    setText(els.authStatus, "Account: preview access");
    setNotice("info", "Logged out", "Session cleared");
    pulseRail("account");
  }

  async function upgradePlan(tier) {
    try {
      setNotice("info", "Preparing upgrade", `Preparing ${String(tier).toUpperCase()} upgrade...`);
      pulseRail("usage");

      const res = await fetch(`${API}/billing/upgrade`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ tier })
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Upgrade failed");

      if (data.checkout_url) {
        setNotice("info", "Redirecting", `Opening ${String(tier).toUpperCase()} checkout...`);
        window.location.href = data.checkout_url;
        return;
      }

      updatePlanUI(
        data.tier || tier,
        Number(data.usage || state.usage),
        Number(data.limit || state.limit),
        Number(data.remaining || state.remaining)
      );

      setNotice("success", "Upgrade applied", `Your account is now on ${String(data.tier || tier).toUpperCase()}.`);
      await loadDashboard();
    } catch (err) {
      setNotice("error", "Upgrade failed", err.message || "Could not upgrade the account.");
    }
  }

  async function sendMessage() {
    const text = (els.messageInput?.value || "").trim();
    if (!text || state.sending) return;

    const rawRefundRef = (els.paymentIntentInput?.value || "").trim();
    const parsedRefundRef = parseRefundReference(rawRefundRef);

    if (parsedRefundRef.error) {
      setNotice("warning", "Invalid refund reference", parsedRefundRef.error);
      if (els.paymentIntentInput) els.paymentIntentInput.focus();
      return;
    }

    state.sending = true;
    if (els.sendBtn) els.sendBtn.disabled = true;

    if (els.messages?.querySelector(".empty-state")) {
      els.messages.innerHTML = "";
    }

    buildMessage("user", text, true);

    if (els.messageInput) {
      els.messageInput.value = "";
      autoResizeTextarea();
    }

    const aiMsg = buildMessage("assistant", "", false);
    setTypingBubble(aiMsg);
    renderStatuses(aiMsg, ["Processing request", "Preparing response"]);

    if (els.messages) {
      els.messages.appendChild(aiMsg.wrapper);
      scrollMessagesToBottom(true);
    }

    try {
      setText(els.streamStatus, "Response: loading");
      setNotice("info", "Processing request", "Response in progress");
      pulseRail("account");

      const res = await fetch(`${API}/support/stream`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({
          message: text,
          payment_intent_id: parsedRefundRef.payment_intent_id,
          charge_id: parsedRefundRef.charge_id
        })
      });

      if (res.status === 402) {
        const data = await res.json().catch(() => ({}));
        const detail = data.detail || "Plan limit reached.";

        setBubbleText(aiMsg, detail);
        renderStatuses(aiMsg, ["Usage limit reached"]);
        renderCustomerNextStep(aiMsg, {
          action: "review",
          reason: detail,
          issue_type: "usage_limit"
        });
        renderActionVisibility(aiMsg, {
          action: "review",
          reason: detail,
          issue_type: "usage_limit"
        });
        setNotice("warning", "Usage limit reached", detail);
        setText(els.streamStatus, "Response: blocked by plan");
        pulseRail("usage");
        return;
      }

      if (res.status === 401) {
        throw new Error("Session expired. Log in again.");
      }

      if (!res.ok || !res.body) {
        throw new Error("Reply service unavailable.");
      }

      setText(els.streamStatus, "Response: live");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let builtText = "";
      let statuses = ["Processing request", "Preparing response"];

      setBubbleText(aiMsg, "");

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() || "";

        for (const block of blocks) {
          const lines = block.split("\n");
          let eventName = "message";
          const dataLines = [];

          for (const line of lines) {
            if (line.startsWith("event:")) eventName = line.slice(6).trim();
            if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
          }

          let payload = {};
          try {
            payload = JSON.parse(dataLines.join("\n") || "{}");
          } catch {
            payload = {};
          }

          if (eventName === "status") {
            const rawLabel = payload.label || payload.stage || "Working";

            const cleaned =
              rawLabel === "Running decision flow"
                ? "Choosing next step"
                : rawLabel === "Preparing response"
                  ? "Preparing response"
                  : rawLabel === "Analyzing issue"
                    ? "Processing request"
                    : rawLabel === "Executing review"
                      ? "Review in progress"
                      : rawLabel === "local_fallback"
                        ? "Processing request"
                        : rawLabel;

            if (!statuses.includes(cleaned)) statuses.push(cleaned);
            renderStatuses(aiMsg, statuses);
            state.latestStatus = cleaned;
            pulseRail("account");
          }

          if (eventName === "chunk") {
            builtText += payload.chunk || "";
            setBubbleText(aiMsg, builtText || " ");
            scrollMessagesToBottom();
          }

          if (eventName === "meta") {
            renderCustomerNextStep(aiMsg, payload);
            renderActionVisibility(aiMsg, payload);

            if (payload.action && payload.action !== "none") {
              state.actions += 1;
              state.latestAction = String(payload.action);
              setText(els.statActions, String(state.actions));
              pulseRail("dashboard");
            }

            if (
              payload.tier ||
              payload.usage !== undefined ||
              payload.plan_limit !== undefined ||
              payload.remaining !== undefined
            ) {
              updatePlanUI(
                payload.tier || state.tier,
                Number(payload.usage ?? state.usage),
                Number(payload.plan_limit ?? state.limit),
                Number(payload.remaining ?? state.remaining)
              );
            }

            if (payload.action === "refund") {
              setNotice("success", "Refund ready", "Approved and in motion");
              pulseRail("dashboard");
            } else if (payload.action === "credit") {
              setNotice("success", "Credit applied", "Applied to account");
              pulseRail("dashboard");
            } else if (payload.action === "review") {
              setNotice("warning", "Review in progress", "Next step underway");
              pulseRail("account");
            } else {
              setNotice("success", "Response ready", "Reply delivered");
              pulseRail("account");
            }
          }

          if (eventName === "done") {
            setText(els.streamStatus, "Response: ready");
          }
        }
      }

      if (!builtText.trim()) {
        setBubbleText(aiMsg, "No response returned.");
      }

      renderStatuses(aiMsg, statuses.filter(Boolean));
      await loadDashboard();
    } catch (err) {
      setBubbleText(aiMsg, err.message || "Something went wrong.");
      renderStatuses(aiMsg, ["Request failed"]);
      renderCustomerNextStep(aiMsg, {
        action: "none",
        reason: err.message || "Unexpected error"
      });
      renderActionVisibility(aiMsg, {
        action: "none",
        reason: err.message || "Unexpected error"
      });
      setNotice("error", "Request failed", err.message || "Unexpected error.");
      setText(els.streamStatus, "Response: error");
      pulseRail("account");
    } finally {
      state.sending = false;
      if (els.sendBtn) els.sendBtn.disabled = false;
      scrollMessagesToBottom(true);
    }
  }

  function startNewChat() {
    renderEmptyState();
    setNotice("info", "New workspace", "Conversation cleared");
  }

  function bindEvents() {
    if (els.messageInput) {
      els.messageInput.addEventListener("input", autoResizeTextarea);
      els.messageInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          sendMessage();
        }
      });
    }

    if (els.paymentIntentInput) {
      els.paymentIntentInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          sendMessage();
        }
      });
    }

    if (els.sendBtn) els.sendBtn.addEventListener("click", sendMessage);
    if (els.signupBtn) els.signupBtn.addEventListener("click", signUp);
    if (els.loginBtn) els.loginBtn.addEventListener("click", logIn);
    if (els.devBtn) els.devBtn.addEventListener("click", useDevMode);
    if (els.logoutBtn) els.logoutBtn.addEventListener("click", logout);
    if (els.newChatBtn) els.newChatBtn.addEventListener("click", startNewChat);

    els.upgradeButtons.forEach((btn) => {
      btn.addEventListener("click", () => {
        upgradePlan(btn.getAttribute("data-upgrade"));
      });
    });

    els.chips.forEach((chip) => {
      chip.addEventListener("click", () => {
        fillComposer(chip.getAttribute("data-fill") || "");
      });
    });
  }

  async function renderAdminPanel() {
    try {
      const [usersRes, logsRes, pendingRes] = await Promise.all([
        fetch(`${API}/admin/users`, { headers: headers(false) }),
        fetch(`${API}/admin/action-logs?limit=50`, { headers: headers(false) }),
        fetch(`${API}/admin/pending-approvals`, { headers: headers(false) }),
      ]);

      if (!usersRes.ok) return;

      const users = await usersRes.json();
      const logs = logsRes.ok ? await logsRes.json() : [];
      const pending = pendingRes.ok ? await pendingRes.json() : [];

      const rail = document.getElementById("railScroll");
      if (!rail) return;

      const existing = document.getElementById("adminCard");
      if (existing) existing.remove();

      const card = document.createElement("div");
      card.id = "adminCard";
      card.className = "rail-card";

      const pendingBadge = pending.length > 0
        ? `<span style="background:rgba(248,113,113,.18);border:1px solid rgba(248,113,113,.3);color:rgba(248,113,113,.9);font-size:9px;padding:2px 7px;border-radius:999px;margin-left:6px">${pending.length} pending</span>`
        : "";

      card.innerHTML = `
        <div class="rail-title">Admin${pendingBadge}</div>

        ${pending.length > 0 ? `
        <div style="margin-bottom:12px">
          <div style="font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:rgba(248,113,113,.7);margin-bottom:6px">Pending approval</div>
          ${pending.map(p => `
            <div style="display:grid;grid-template-columns:1fr auto;align-items:center;gap:8px;padding:7px 6px;border-radius:8px;background:rgba(248,113,113,.06);border:1px solid rgba(248,113,113,.12);margin-bottom:4px">
              <div>
                <div style="font-size:11px;color:rgba(248,180,180,.9);font-weight:600">$${p.amount} ${p.action}</div>
                <div style="font-size:9px;color:rgba(200,180,180,.5);margin-top:1px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:140px">${escapeHtml(p.username)} · ${escapeHtml(p.issue_type)}</div>
              </div>
              <button onclick="adminApprove(${p.id})" style="font-size:9px;padding:3px 9px;border-radius:6px;border:1px solid rgba(52,211,153,.22);background:rgba(52,211,153,.08);color:rgba(110,231,183,.9);cursor:pointer;white-space:nowrap">Approve</button>
            </div>
          `).join("")}
        </div>
        ` : ""}

        <div style="margin-bottom:12px">
          <div style="font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:rgba(185,200,240,.4);margin-bottom:6px">Users</div>
          ${users.map(u => `
            <div style="display:grid;grid-template-columns:1fr auto auto auto;align-items:center;gap:6px;padding:7px 2px;border-bottom:1px solid rgba(255,255,255,.04);font-size:11px">
              <span style="color:rgba(215,225,250,.85);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(u.username)}</span>
              <span style="color:rgba(167,139,250,.8);font-size:9px;letter-spacing:.06em;text-transform:uppercase">${escapeHtml(u.tier)}</span>
              <span style="color:rgba(200,211,235,.38);font-size:10px">${u.usage}</span>
              <button onclick="adminReset('${escapeHtml(u.username)}')" style="font-size:9px;padding:2px 7px;border-radius:6px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.04);color:rgba(200,211,235,.55);cursor:pointer" onmouseover="this.style.background='rgba(255,255,255,.08)'" onmouseout="this.style.background='rgba(255,255,255,.04)'">Reset</button>
            </div>
          `).join("")}
        </div>

        <div>
          <div style="font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:rgba(185,200,240,.4);margin-bottom:6px">Recent actions</div>
          ${logs.slice(0, 15).map(l => {
            const actionColor = l.action === "refund" ? "rgba(248,113,113,.8)"
              : l.action === "credit" ? "rgba(52,211,153,.8)"
              : l.action === "review" ? "rgba(251,191,36,.8)"
              : "rgba(148,163,184,.5)";
            return `
            <div style="display:grid;grid-template-columns:auto 1fr auto;gap:6px;align-items:center;padding:5px 2px;border-bottom:1px solid rgba(255,255,255,.03);font-size:10px">
              <span style="color:${actionColor};font-weight:600;text-transform:uppercase;font-size:8px;letter-spacing:.08em;min-width:36px">${escapeHtml(l.action)}</span>
              <span style="color:rgba(200,211,235,.45);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(l.username)}</span>
              <span style="color:rgba(200,211,235,.35);white-space:nowrap">${l.amount > 0 ? "$" + l.amount : "—"}</span>
            </div>`;
          }).join("")}
        </div>

        <div style="margin-top:8px;font-size:9px;color:rgba(200,211,235,.2);letter-spacing:.06em">${users.length} user${users.length !== 1 ? "s" : ""} · ${logs.length} logged</div>
      `;

      rail.appendChild(card);
    } catch {}
  }

  window.adminApprove = async function(logId) {
    try {
      const res = await fetch(`${API}/admin/approve/${logId}`, {
        method: "POST",
        headers: headers(),
      });
      if (res.ok) {
        setNotice("success", "Approved", `Action ${logId} marked as approved.`);
        await renderAdminPanel();
      }
    } catch {}
  };

  window.adminReset = async function(username) {
    try {
      const res = await fetch(`${API}/admin/reset-usage`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ username })
      });
      if (res.ok) {
        setNotice("success", "Usage reset", `${username} reset to 0.`);
        await renderAdminPanel();
      }
    } catch {}
  };

  async function boot() {
    ensureActionVisibilityStyles();
    ensurePaymentIntentField();
    renderEmptyState();
    bindEvents();
    autoResizeTextarea();
    await checkHealth();
    await hydrateMe();
    await loadDashboard();
    updateCustomerFacingCopy();
    pulseRail("account");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();