# Leash web console (PRD)
## Problem
Python CLI (main.py) driving leash/demo.py (8 Airwallex sandbox scenes; emits events, asks approvals via callback). Build a web UI around it without changing leash/ logic. LLM: Emergent key in preview, ANTHROPIC_API_KEY in live; only client creation in leash/agent.py changes.
## Built (2026-06)
- leash/agent.py: `_default_client()` + MODEL choice: ANTHROPIC_API_KEY -> Anthropic direct, claude-opus-5-5; else EMERGENT_LLM_KEY via proxy (EMERGENT_LLM_BASE_URL, EMERGENT_LLM_MODEL=claude-sonnet-5-5). Prompts, structured parse, _check_grounded untouched.
- backend/server.py: /api/health, POST /api/runs {auto}, GET /api/runs/{id}?after=n, GET /api/runs/latest, POST /api/runs/{id}/approval {approved,digest}. In-memory runs, one at a time.
- frontend (Vite+React+recharts): timeline by scene, approval panel, auto-answer toggle, card panel, forecast charts, raw JSON tab, expected/unexpected summary.
- Verified: CLI --auto all rows expected, scene 1 monthly 1,000 / annual 9,840 + real explanation; UI manual + auto runs 10/10 expected.
## Backlog
- P1: persist run history (Mongo); SSE instead of polling
- P2: download run as JSON lines
