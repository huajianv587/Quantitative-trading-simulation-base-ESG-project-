from pathlib import Path
import json

from gateway.utils import llm_client


def _clear_llm_cache(monkeypatch):
    monkeypatch.setattr(llm_client, "get_cache", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(llm_client, "set_cache", lambda *_args, **_kwargs: None)


def test_local_backend_supported_skips_cpu_only_hosts(monkeypatch):
    monkeypatch.setattr(llm_client, "LOCAL_CKPT", str(Path(__file__)))
    monkeypatch.setattr(llm_client, "_local_fail_count", 0)
    monkeypatch.setattr(llm_client.torch.cuda, "is_available", lambda: False)

    assert llm_client._local_backend_supported() is False
    assert llm_client._local_fail_count == llm_client.MAX_LOCAL_FAILURES


def test_chat_remote_uses_configured_service(monkeypatch):
    captured = {}
    _clear_llm_cache(monkeypatch)

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"answer": "remote-ok"}

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return DummyResponse()

    monkeypatch.setattr(llm_client.settings, "REMOTE_LLM_URL", "http://127.0.0.1:8010")
    monkeypatch.setattr(llm_client.settings, "REMOTE_LLM_API_KEY", "secret-token")
    monkeypatch.setattr(llm_client.settings, "REMOTE_LLM_TIMEOUT", 42)
    monkeypatch.setattr(llm_client.requests, "post", fake_post)

    result = llm_client._chat_remote(
        [{"role": "user", "content": "Summarize Singtel governance priorities."}],
        max_tokens=256,
        temperature=0.1,
    )

    assert result == "remote-ok"
    assert captured["url"] == "http://127.0.0.1:8010/chat"
    assert captured["json"]["max_tokens"] == 256
    assert captured["headers"]["Authorization"] == "Bearer secret-token"
    assert captured["timeout"] == (2.0, 42.0)


def test_chat_prefers_deepseek_before_remote_and_openai_in_auto_mode(monkeypatch):
    _clear_llm_cache(monkeypatch)
    monkeypatch.setattr(llm_client, "_local_fail_count", llm_client.MAX_LOCAL_FAILURES)
    monkeypatch.setattr(llm_client, "_remote_fail_count", 0)
    monkeypatch.setattr(llm_client.settings, "LLM_BACKEND_MODE", "auto")
    monkeypatch.setattr(llm_client.settings, "REMOTE_LLM_URL", "http://127.0.0.1:8010")
    monkeypatch.setattr(llm_client.settings, "DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.setattr(llm_client.settings, "OPENAI_API_KEY", "openai-key")
    monkeypatch.setattr(
        llm_client,
        "_chat_remote",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Remote backend should not run in auto mode")),
    )
    monkeypatch.setattr(llm_client, "_chat_deepseek", lambda messages, max_tokens, temperature: "deepseek-answer")
    monkeypatch.setattr(
        llm_client,
        "_chat_openai",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("OpenAI fallback should not run")),
    )

    result = llm_client.chat(
        [{"role": "user", "content": "Analyze DBS climate disclosures."}],
        temperature=0.2,
        max_tokens=128,
    )

    assert result == "deepseek-answer"


def test_chat_falls_back_to_openai_after_deepseek_failure(monkeypatch):
    _clear_llm_cache(monkeypatch)
    monkeypatch.setattr(llm_client, "_local_fail_count", llm_client.MAX_LOCAL_FAILURES)
    monkeypatch.setattr(llm_client, "_remote_fail_count", 0)
    monkeypatch.setattr(llm_client.settings, "LLM_BACKEND_MODE", "auto")
    monkeypatch.setattr(llm_client.settings, "DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.setattr(llm_client.settings, "OPENAI_API_KEY", "openai-key")
    monkeypatch.setattr(
        llm_client,
        "_chat_deepseek",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("deepseek unavailable")),
    )
    monkeypatch.setattr(llm_client, "_chat_openai", lambda messages, max_tokens, temperature: "openai-answer")

    result = llm_client.chat(
        [{"role": "user", "content": "Summarize Grab social commitments."}],
        temperature=0.2,
        max_tokens=128,
    )

    assert result == "openai-answer"


def test_chat_remote_mode_skips_local_backend(monkeypatch):
    _clear_llm_cache(monkeypatch)
    monkeypatch.setattr(llm_client, "_local_fail_count", 0)
    monkeypatch.setattr(llm_client, "_remote_fail_count", 0)
    monkeypatch.setattr(llm_client.settings, "LLM_BACKEND_MODE", "remote")
    monkeypatch.setattr(llm_client.settings, "REMOTE_LLM_URL", "http://127.0.0.1:8010")
    monkeypatch.setattr(llm_client, "_remote_backend_retry_ready", lambda: True)
    monkeypatch.setattr(llm_client, "_remote_backend_healthy", lambda force=False: True)
    monkeypatch.setattr(llm_client.settings, "DEEPSEEK_API_KEY", "")
    monkeypatch.setattr(llm_client.settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(
        llm_client,
        "_chat_local",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("local backend should be skipped")),
    )
    monkeypatch.setattr(llm_client, "_chat_remote", lambda messages, max_tokens, temperature: "remote-only")

    result = llm_client.chat(
        [{"role": "user", "content": "Summarize Grab social commitments."}],
        temperature=0.2,
        max_tokens=128,
    )

    assert result == "remote-only"


def test_runtime_backend_status_reports_mode(monkeypatch):
    _clear_llm_cache(monkeypatch)
    monkeypatch.setattr(llm_client.settings, "APP_MODE", "hybrid")
    monkeypatch.setattr(llm_client.settings, "LLM_BACKEND_MODE", "remote")
    monkeypatch.setattr(llm_client.settings, "REMOTE_LLM_URL", "http://127.0.0.1:8010")
    monkeypatch.setattr(llm_client.torch.cuda, "is_available", lambda: False)

    status = llm_client.get_runtime_backend_status()

    assert status["app_mode"] == "hybrid"
    assert status["llm_backend_mode"] == "remote"
    assert status["remote_llm_configured"] is True
    assert status["remote_llm_enabled_in_mode"] is True
    assert status["cloud_fallback_order"] == ["deepseek", "openai"]
    assert status["local_llm_cuda_available"] is False
    assert status["degraded_llm_fallback_enabled"] is True


def test_chat_uses_degraded_fallback_when_no_live_backends(monkeypatch):
    _clear_llm_cache(monkeypatch)
    monkeypatch.setattr(llm_client, "_local_fail_count", llm_client.MAX_LOCAL_FAILURES)
    monkeypatch.setattr(llm_client, "_remote_fail_count", llm_client.MAX_REMOTE_FAILURES)
    monkeypatch.setattr(llm_client.settings, "APP_MODE", "local")
    monkeypatch.setattr(llm_client.settings, "LLM_BACKEND_MODE", "auto")
    monkeypatch.setattr(llm_client.settings, "DEEPSEEK_API_KEY", "")
    monkeypatch.setattr(llm_client.settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(llm_client.settings, "DEBUG", True)

    result = llm_client.chat(
        [
            {"role": "system", "content": "You are an ESG query classifier. Return only the label."},
            {"role": "user", "content": "Question: Analyze Tesla ESG score trend"},
        ],
        temperature=0.0,
        max_tokens=20,
    )

    assert result == "esg_analysis"


def test_degraded_analyst_fallback_returns_valid_json():
    payload = llm_client._chat_degraded(
        [
            {"role": "system", "content": "You are a professional ESG analyst. Only return valid JSON."},
            {
                "role": "user",
                "content": (
                    "Company/Topic: Tesla\n\n"
                    "Retrieved context:\n"
                    "Tesla expanded renewable energy usage, improved board oversight, and reported worker safety training."
                ),
            },
        ]
    )

    parsed = json.loads(payload)

    assert parsed["overall_score"] >= 50
    assert parsed["risk_level"] in {"low", "medium", "high"}
    assert parsed["environmental"]["score"] >= 50
