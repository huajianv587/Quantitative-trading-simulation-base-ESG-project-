# Remote GPU Runbook

Note: this path is optional and intended for the future case where you bring a
remote GPU host back online. The current delivery baseline is local-first mode.

This mode keeps the RAG stack on the local machine and moves only the LoRA
generation step to a remote GPU host.

## Topology

- Local machine: FastAPI, Qdrant, embeddings, docstore, frontend
- Remote GPU host: Qwen2.5-7B + LoRA adapter service
- Connectivity: SSH local port forward

## Remote Host Setup

```bash
cd /root/workspaces
git clone https://github.com/huajianv587/ESG_Agentic.git esg-rag
cd esg-rag
pip install -r requirements.txt
export REMOTE_LLM_API_KEY=replace-with-a-shared-secret
python model-serving/remote_llm_server.py
```

Expected health endpoint on the remote host:

```bash
curl http://127.0.0.1:8010/health
```

## Local SSH Tunnel

Run this on the local machine and keep it open:

```bash
ssh -N -L 8010:127.0.0.1:8010 -p <PORT> root@<REMOTE_HOST>
```

## Local `.env`

```bash
APP_MODE=hybrid
LLM_BACKEND_MODE=remote
REMOTE_LLM_URL=http://127.0.0.1:8010
REMOTE_LLM_API_KEY=replace-with-a-shared-secret
```

With this set, `gateway/utils/llm_client.py` will try:

1. remote GPU LoRA service
2. DeepSeek
3. OpenAI

In `remote` mode the remote GPU service is the primary generation backend.

## Smoke Checks

Remote service:

```bash
curl http://127.0.0.1:8010/health
```

Local app:

```bash
python -m pytest tests/test_llm_client_runtime.py -q
python scripts/runtime_doctor.py
```
