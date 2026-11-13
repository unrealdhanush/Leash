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

- 2026-06 v3: own quote (paste / upload txt, eml, PDF via POST /api/quotes/extract; optional price-change email, chapter 5 skipped without it; server points leash.demo.QUOTES_DIR at a temp dir for the run and uses a WebDemo subclass, leash/ untouched), share link (POST/DELETE /api/runs/{id}/share, GET /api/shared/{token}, route /share/:token), JSON export (GET /api/runs/{id}/export), approval notes (Decision.note, added to approval_result event), `at` timestamp on every event. Tested: iteration_3.json

## Known issues (inside leash/, not fixed because leash/ is off limits)
- A plan billed once a year that passes policy (e.g. own quote 400/month or 4,200/year) gets a single-use card; after the checkout charge, unfreezing it in chapter 8 fails with Airwallex 400 "Invalid status update" and the purchase ends "Stopped".
- Example quote with the annual plan approved in chapter 2: run finishes, but chapter 7 freezes the card with reason "charge exceeds auto-approve limit" and chapter 8 leaves it frozen.

## Hackathon (Airwallex Agentic Banking, HackerEarth, Track 2)
Required per public summaries: working demo, video under 5 minutes, repo with setup instructions. Open: record video, push repo (Save to GitHub), decide on hosting + access control (no login today), fix or avoid the two known issues.

## Backlog
- P0: fix single-use card unfreeze path (needs user permission to touch leash/)
- P1: access control before hosting publicly
- P2: delete/archive purchases
- P2: several purchases at once (currently one live run at a time)
