# Leash web app (PRD)
## Problem
Python CLI (main.py) driving leash/demo.py (Setup + 8 Airwallex sandbox scenes; emits events, asks approvals via callback). Web UI around it without changing leash/ logic. LLM: Emergent key in preview, ANTHROPIC_API_KEY in live; only client creation in leash/agent.py changed.
User wants the product itself to tell the story (no separate demo mode): a finance team hands a vendor quote to the agent and follows it to a controlled card.

## User choices (2026-06)
- Each run is a "purchase"; home is the purchases list (= run history)
- Plain-language chapters per scene, original scene title kept beside
- Landing page: product page for finance teams
- Compare: two runs side by side

## Architecture
- backend/server.py (FastAPI, sync pymongo, runs in a thread):
  - GET /api/health, GET /api/context (quote text, policy, cash plan read from leash/)
  - GET /api/runs (summaries, newest first), POST /api/runs {auto} (409 if one is live), GET /api/runs/latest, GET /api/runs/{id}?after=n
  - GET /api/runs/{id}/stream: SSE (`leash` events with id = index, `state` events, keepalive 15s, resumes from Last-Event-ID); 404 if run not live
  - POST /api/runs/{id}/approval {approved, digest}
  - Mongo `runs`: {_id (run id string), seq, auto, started_at, finished_at, status, error, model, summary, events[]}; each event is pushed as it happens; runs left active by a restart are marked `interrupted` at startup
- frontend (Vite + React 18 + react-router 6, plain CSS, recharts, lucide-react):
  - `/` Landing, `/app` Purchases (New purchase panel + history list + pick two), `/app/purchases/:id` detail (sticky chapter rail with jump + keys 0–8, live timeline, side panel: approval / card / forecast, raw JSON tab), `/app/compare?a=&b=`
  - src/chapters.js holds the chapter copy (used by rail, timeline and landing)
  - useRun(id): fetch snapshot, then EventSource while live

## Done
- 2026-06 v1: console, approvals, auto toggle, CLI --auto verified
- 2026-06 v2: SSE live streaming, chapter rail, Mongo run history, compare, purchases home, landing page, story chapters

## Backlog
- P1: paste/upload your own vendor quote (needs a change in leash/demo.py, which is currently fixed to quotes/northwind.txt)
- P2: download a purchase as JSON lines; delete/archive purchases
- P2: several purchases at once (currently one live run at a time)
