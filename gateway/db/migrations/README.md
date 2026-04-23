# Database Migrations

This directory contains the Supabase/Postgres schema files used by the project runtime.

## Recommended order

Run these in Supabase SQL Editor, in order:

| File | Purpose |
| --- | --- |
| `000_supabase_bootstrap_all.sql` | One-shot bootstrap for a fresh Supabase project |
| `001_init_sessions.sql` | `sessions` and `chat_history` |
| `002_add_esg_report_tables.sql` | ESG reports, snapshots, push rules, subscriptions, feedback |
| `003_add_scheduler_tables.sql` | Users, holdings, preferences, events, risk scores, notifications |
| `004_align_runtime_schema.sql` | Safe alignment patch for legacy scheduler/event tables |
| `005_add_quant_rl_tables.sql` | Quant RL runtime persistence tables |
| `006_add_trading_agent_tables.sql` | Trading agent watchlist / alerts / debate / risk / review tables |
| `007_add_auth_runtime_tables.sql` | Supabase-primary auth runtime tables for register/login/reset/audit/mail delivery |

## Notes

- All migrations are written to be re-runnable with `IF NOT EXISTS` / safe `ALTER TABLE`.
- `000_supabase_bootstrap_all.sql` is convenient for a fresh project, but existing projects should still apply any later numbered migrations that were added afterward.
- If you are closing the real external dependency loop, make sure `007_add_auth_runtime_tables.sql` has been applied before expecting `/auth/status` to report `effective_backend=supabase`.
