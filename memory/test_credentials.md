# Test credentials

Sign-in is Emergent-managed Clerk (Google only in the UI). Do NOT automate the Google form; bot protection blocks it.

Three Clerk test users exist on the preview instance, with roles set in Mongo `users` (env "preview"). Keep them.

| Role | Email |
|---|---|
| admin | leash.admin+clerk_test@example.com |
| member | leash.member+clerk_test@example.com |
| pending (no access) | leash.pending+clerk_test@example.com |

Helper (recreates users/roles if missing):
- API token (1 hour): `/root/.venv/bin/python /app/memory/clerk_test_users.py token admin|member|pending` -> send as `Authorization: Bearer <jwt>`
- UI sign-in ticket (10 min, one use): `/root/.venv/bin/python /app/memory/clerk_test_users.py ticket admin|member|pending` -> open `<preview_url>/sign-in?__clerk_ticket=<ticket>`; if that page does not sign in, run in the page:
  `const si = await window.Clerk.client.signIn.create({strategy: "ticket", ticket}); await window.Clerk.setActive({session: si.createdSessionId});`

Real first admin (set by the owner): ADMIN_EMAIL=dhanushbalakrishna45@gmail.com in backend/.env; becomes admin on first Google sign-in.

Public without sign-in: `/`, `/share/{token}`, GET /api/health, GET /api/shared/{token}, GET /api/clerk/config.
Airwallex sandbox + LEASH_* values are platform secrets; LLM via EMERGENT_LLM_KEY in backend/.env.
