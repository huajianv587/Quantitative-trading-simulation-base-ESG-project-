# ESG Quant Intelligence System

ESG Quant Intelligence System is a productized ESG quant platform that now combines:

- ESG RAG and multi-agent reasoning
- factor research and portfolio construction
- backtesting and paper-execution planning
- Supabase metadata storage and Cloudflare R2 artifact storage
- a product website at `/`
- a control console at `/app`

## Runtime

- Product site: `/`
- Control console: `/app`
- API docs: `/docs`
- Quant platform overview: `/api/v1/quant/platform/overview`

## Repository Layout

This repository now has two layers in parallel:

1. The original running implementation under `gateway/`, `frontend/`, `training/`, `scripts/`
2. A blueprint-aligned top-level architecture scaffold matching the target `esg-quant-intelligence/` layout:

- `config/`
- `data/`
- `analysis/`
- `models/`
- `agents/`
- `risk/`
- `backtest/`
- `infrastructure/`
- `reporting/`
- `rag/`
- `api/`
- `database/`
- `notebooks/`

The running FastAPI service still uses `gateway.main`, while the new top-level directories provide a standardized, industrialized module layout and compatibility adapters.

## Storage

- Structured metadata: Supabase
- Artifact storage: Cloudflare R2
- Local fallback: `storage/quant/`

## Quick Start

```bash
python -m uvicorn gateway.main:app --host 0.0.0.0 --port 8000
```

Then open:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/app`

## Tests

```bash
python -m pytest tests/test_api_contracts.py tests/test_quant_api.py tests/test_site_delivery.py tests/test_frontend_click_contracts.py -q
```

## Notes

- If Supabase or R2 credentials are missing, the system falls back to local storage.
- The quant stack is designed to extend toward remote RTX 5090 fine-tuning and training.
- The top-level blueprint folders are intentionally scaffolded to match the target industrial architecture while reusing the current working implementation.
