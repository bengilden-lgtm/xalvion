import { createApiClient } from "./api/client.js";
import { createSessionStore } from "./stores/session-store.js";
import { createAgentStore } from "./stores/agent-store.js";
import { createUiStore } from "./stores/ui-store.js";
import { createCrmStore } from "./stores/crm-store.js";
import { createRefundStore } from "./stores/refund-store.js";
import { createAnalyticsEngine } from "./engines/analytics-engine.js";
import { createAgentVisualizer } from "./engines/agent-visualizer.js";
import { createStripeEngine } from "./engines/stripe-engine.js";
import { createInboxScanEngine } from "./engines/inbox-scan-engine.js";
import { createChromeContext } from "./adapters/chrome-context.js";

const sessionStore = createSessionStore();
const agentStore = createAgentStore();
const uiStore = createUiStore();
const crmStore = createCrmStore();
const refundStore = createRefundStore();

const analyticsEngine = createAnalyticsEngine({ sessionStore });
const agentVisualizer = createAgentVisualizer({ agentStore });
const stripeEngine = createStripeEngine({ refundStore, apiClient: null });
const inboxScanEngine = createInboxScanEngine({ chromeContext: createChromeContext() });
const chromeContext = createChromeContext();

function createBoundApi(getToken, onUnauthorized) {
  return createApiClient({
    getToken,
    baseUrl: "",
    onUnauthorized,
  });
}

globalThis.__XALVION_PHASE2__ = {
  version: 2,
  sessionStore,
  agentStore,
  uiStore,
  crmStore,
  refundStore,
  analyticsEngine,
  agentVisualizer,
  stripeEngine,
  inboxScanEngine,
  chromeContext,
  createBoundApi,
  ready: true,
};

globalThis.dispatchEvent(new CustomEvent("xalvion:phase2-ready"));
