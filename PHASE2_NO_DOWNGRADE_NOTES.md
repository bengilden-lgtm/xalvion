# Phase 2 No-Downgrade Patch

This patch starts frontend modularization without removing features or changing the current UI shell.

## Included
- `app.js`
  - now bootstraps a modular helper layer through `loadPhase2Core()`
  - keeps all existing inline behavior as fallback if the module route fails
  - delegates API client and formatting helpers to the module when available
- `workspace_modules.js`
  - new Phase 2 module entry
  - contains extracted API client logic and formatting/store helpers
- `app.py`
  - serves `/workspace-modules.js` explicitly

## Why this is no-downgrade
- `app.js` still contains the full existing workspace logic
- if `/workspace-modules.js` fails to load, the current inline runtime still works
- no feature paths were removed
- no IDs/classes/routes used by the current UI were removed

## What this unlocks next
- move billing helpers into a dedicated module
- move CRM/revenue rendering into dedicated modules
- split state/store from DOM rendering incrementally
