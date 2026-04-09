from __future__ import annotations

from gateway.rag.rag_main import _FallbackQueryEngine, _FallbackSourceNode


def test_fallback_query_engine_prefers_matching_esg_qa(monkeypatch):
    monkeypatch.setattr(
        "gateway.rag.rag_main._llm_chat",
        lambda messages, max_tokens=512: messages[-1]["content"],
    )
    engine = _FallbackQueryEngine(
        [
            _FallbackSourceNode("Internal developer setup guide for local GPU routing.", metadata={"path": "docs/setup.md"}),
            _FallbackSourceNode(
                "Question: What is Apple's renewable energy goal?\nAnswer: Apple aims to run its operations with 100% renewable electricity.",
                metadata={"path": "data/rag_training_data/val.jsonl", "source": "rag_training_data"},
            ),
        ]
    )

    response = engine.query("What is Apple's renewable energy goal?")

    assert response.source_nodes
    assert response.source_nodes[0].metadata["source"] == "rag_training_data"
    assert "renewable electricity" in response.answer


def test_fallback_query_engine_returns_clear_message_when_no_match():
    engine = _FallbackQueryEngine(
        [_FallbackSourceNode("Internal deployment checklist and Docker notes.")]
    )

    response = engine.query("Tell me about methane emissions at an energy company.")

    assert not response.source_nodes
    assert "no relevant ESG evidence matched the query" in response.answer
