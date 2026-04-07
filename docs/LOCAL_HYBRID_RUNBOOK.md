# Local Hybrid Runbook

Note: this is an optional runbook for the future remote GPU path. The current
product delivery baseline is local-first mode (`APP_MODE=local`,
`LLM_BACKEND_MODE=auto`).

This is the recommended long-term workflow for a Windows local machine that
keeps the application, RAG, and data on the local computer, while borrowing GPU
compute from a remote host only for LLM generation.

## What stays local

- FastAPI app
- Qdrant
- RAG/docstore/PDF data
- Frontend and API development

## What moves to the remote GPU host

- Qwen2.5-7B + LoRA answer generation service only

## 1. Bootstrap the local environment

```bat
scripts\bootstrap_local_windows.bat
```

This script always uses `.venv\Scripts\python.exe` directly, which avoids
accidentally installing packages into the Windows Store global Python.

## 2. Keep the remote GPU service reachable

- Start the remote `remote_llm_server.py` service on the GPU host
- Keep a local SSH tunnel open:

```bat
ssh -N -L 8010:127.0.0.1:8010 -p <PORT> root@<REMOTE_HOST>
```

## 3. Configure `.env`

```env
APP_MODE=hybrid
LLM_BACKEND_MODE=remote
REMOTE_LLM_URL=http://127.0.0.1:8010
REMOTE_LLM_API_KEY=replace-with-your-shared-secret
```

In this mode the generation order is:

1. remote GPU LoRA service
2. DeepSeek
3. OpenAI

## 4. Start local Qdrant

```bat
scripts\start_local_qdrant_windows.bat
```

This helper avoids a common Windows issue where a stray standalone `qdrant`
container is running without publishing port `6333` to the host. It stops that
container if needed, then starts the compose-managed Qdrant service with the
expected port mapping.

## 5. Start the local API

```bat
scripts\run_local_hybrid_windows.bat
```

## 6. Inspect runtime health

```bat
.venv\Scripts\python.exe scripts\runtime_doctor.py
```

Expected checks:

- `qdrant.ok = true`
- `remote_llm.ok = true`
- `local_api.ok = true`

## Notes

- This mode keeps the local machine as the long-term source of truth.
- The remote host is treated as a replaceable compute backend, not the primary
  application host.
