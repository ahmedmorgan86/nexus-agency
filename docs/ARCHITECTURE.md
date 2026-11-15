# NEXUS 2.0 — Architecture (Milestone 1)

## Findings from the legacy repo (nexus-agency)
Static HTML dashboards with a localStorage CRM and Math.random scoring, a Python agent core (nexus_os), and a small FastAPI scaffold. Only ideas are reused: agent registry, CEO state machine, evidence-based audits, SSRF guard, honest reporting (accepted vs delivered). No legacy code is imported.

## Stack decisions
| Area | Choice | Why |
|---|---|---|
| Web | Next.js (App Router), TypeScript, Tailwind, shadcn/ui, Recharts | Preferred stack, Vercel-compatible |
| API / agents | Python FastAPI | Best ecosystem for agents, audits, media pipelines; secrets stay server-side |
| DB | PostgreSQL (Supabase) with RLS on every tenant table | Isolation enforced in the database, not only in code |
| Auth | Supabase Auth (JWT) + roles: owner, admin, operator, client_viewer | No custom crypto |
| Jobs | Postgres-backed durable queue (tasks table, SKIP LOCKED) + separate worker | No extra infra; idempotency keys, retries |
| Storage | Supabase Storage, per-tenant prefixes, signed URLs | Isolation |
| AI | Provider abstractions: LLM, Image, Video, Voice, Email | Swap vendors without rewrites |
| Hosting | Web on Vercel; API + worker on a persistent host (Fly/Render/Railway); separate staging and prod | Workers need long-lived processes |

## Services
web (Next.js) -> api (FastAPI) -> Postgres/Storage. worker (same codebase as api) polls tasks and runs agents via the CEO orchestrator.

## Invariants (enforced in code and tests)
1. Every tenant row has tenant_id; RLS policies plus an API dependency both check it.
2. Any external side effect (email, WhatsApp, ad publish, spend) is a task in WAITING_APPROVAL until a human approves; approvals are audit-logged.
3. Billable calls pass a budget gate that blocks when a limit is exceeded.
4. Every finding stores evidence, source URL and observed_at. No evidence, no finding.
5. Task states: CREATED, QUEUED, RUNNING, WAITING_APPROVAL, COMPLETED, FAILED, CANCELLED, RETRYING. COMPLETED only after QA verification.
6. Email logs keep provider_accepted_at separate from delivered_at.

## Data model (Milestone 2 migration)
tenants, memberships, profiles, leads, companies, contacts, lead_evidence, lead_scores, activities, deals, tasks, task_events, agents, approvals, budgets, usage_events, assets, demo_sites, demo_access_logs, reports, memories, audit_logs.
