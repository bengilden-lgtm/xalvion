# UI Componentization Strategy

## Goal
Break `app.js` and `sidepanel.js` into state-driven modules without removing features.

## Proposed modules

### Shared core
- `stores/session-store.js` - auth, plan tier, usage, streaming flags, current user
- `stores/agent-store.js` - latest run, thinking trace, decision envelope, execution state
- `stores/crm-store.js` - leads, followups, daily summary, revenue metrics
- `stores/refund-store.js` - refund modal state, history, Stripe state
- `stores/ui-store.js` - notices, modals, scroll state, stick-to-bottom, view toggles

### Engines
- `engines/analytics-engine.js` - metrics aggregation, impact formatting, ROI banners
- `engines/agent-visualizer.js` - explainability, trace rendering, confidence meter, header insight
- `engines/inbox-scan-engine.js` - active-tab extraction, inbox scan sequence, multi-ticket summary
- `engines/stripe-engine.js` - connect/disconnect, refund execution, refund history sync

### Adapters
- `api/client.js` - fetch wrapper, auth header injection, retry/backoff, JSON parsing
- `adapters/chrome-context.js` - tab context extraction, script injection, compose insertion

## Migration order
1. Extract pure formatting/helpers from `sidepanel.js`.
2. Move state into plain stores with subscribe/set/get.
3. Point render functions at stores.
4. Split side effects into engines.
5. Leave entry files as composition roots only.

## Result
- Smaller blast radius for changes
- Easier testing
- No maintenance collapse as CRM, analytics, and agent visualization grow
