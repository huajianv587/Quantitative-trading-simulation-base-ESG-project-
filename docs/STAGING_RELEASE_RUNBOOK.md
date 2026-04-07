# Staging And Release Runbook

For customer-facing deployment and acceptance handoff, use
`docs/PRODUCT_DELIVERY_CHECKLIST_ZH.md` as the primary checklist.

## Staging Startup

### 1. Preflight

```bash
python scripts/staging_check.py preflight
```

This checks:
- `.env` exists and required secrets are present
- `docker` / `docker compose` are available
- `docker compose config` can be parsed
- required files and directories exist
- default ports `80`, `8000`, `6333` are not already occupied

### 2. Bring Up Staging

```bash
python scripts/staging_check.py up --require-module rag --require-module esg_scorer
```

If you only want to reuse already-built images:

```bash
python scripts/staging_check.py up --skip-build --require-module rag --require-module esg_scorer
```

### 3. Manual Smoke Commands

```bash
docker compose ps
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
curl http://localhost:8000/dashboard/overview
curl http://localhost/health
```

### 4. Tear Down

```bash
docker compose down
```

Preserve Qdrant data volume:

```bash
docker compose down
```

Full cleanup including Qdrant volume:

```bash
docker compose down -v
```

## Go-Live Checklist

### Config

- `.env` uses production keys, not demo keys
- `CORS_ORIGINS` is restricted to production domains
- `SUPABASE_URL` and at least one server-side key are valid
- `OPENAI_API_KEY` is valid
- `ANTHROPIC_API_KEY` or `DEEPSEEK_API_KEY` is configured as fallback
- SMTP credentials are valid if notifications are required
- `QDRANT_URL` points to the in-cluster service in container environments

### Data And Model

- `data/raw/` contains the ESG source files needed for first-time indexing
- `model-serving/checkpoint/` exists and contains the LoRA adapter files
- Supabase migrations `001` through `004` have been applied in order
- Qdrant persistence is enabled and volume-backed

### Runtime

- `python -m pytest -q` passes in CI before deployment
- `python scripts/staging_check.py preflight` passes on the target host
- `docker compose up -d --build` succeeds without unhealthy services
- `/health` returns `200`
- `/health/ready` returns `200`
- `/dashboard/overview` returns `200`
- `/agent/analyze` works with a real staging prompt
- `/admin/reports/generate` works with a real staging request
- Nginx can proxy `http://localhost/health`

### Observability

- container logs are collected and retained
- application logs do not contain startup tracebacks
- health checks are wired into the hosting platform
- alerts exist for repeated container restarts or unhealthy services

### Release Control

- the release is tagged in git
- the image tag is immutable and recorded
- the previous known-good image tag is recorded before cutover
- rollback ownership and approval path are clear

## Rollback Plan

### Fast Rollback

Use this when the new release starts but user-facing behavior regresses.

1. Identify the previous known-good image tag.
2. Update deployment to point back to that tag.
3. Restart only the application tier.
4. Confirm `/health` and `/dashboard/overview` recover.
5. Confirm one real business request succeeds.

### Docker Compose Rollback

If you are deploying with local compose on a server:

1. Keep the previous image tag locally available.
2. Update `docker-compose.yml` or the image reference back to the prior tag.
3. Run:

```bash
docker compose up -d
```

4. Verify:

```bash
python scripts/staging_check.py compose
python scripts/staging_check.py smoke --require-module rag --require-module esg_scorer
```

### Database Safety

- Do not roll back database schema by hand during an active outage unless the migration is known to be backward-incompatible.
- Prefer backward-compatible migrations so app rollback does not require DB rollback.
- If a migration must be reverted, restore from backup or run a tested down-migration script only.

### Incident Notes Template

Record these items after rollback:

- release tag
- rollback time
- affected endpoints
- user impact window
- root-cause summary
- follow-up fix owner
