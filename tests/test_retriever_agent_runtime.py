from llama_index.core.schema import NodeWithScore, TextNode

from gateway.agents import retriever_agent


def test_run_retriever_uses_cached_context_payload(monkeypatch):
    monkeypatch.setattr(
        retriever_agent,
        "get_cache",
        lambda question: {
            "rewritten_query": "cached rewrite",
            "context": "grounded context",
            "raw_answer": "cached answer",
        },
    )
    monkeypatch.setattr(
        retriever_agent,
        "get_query_engine",
        lambda: (_ for _ in ()).throw(AssertionError("query engine should not be called")),
    )

    result = retriever_agent.run_retriever({"question": "What changed in climate governance?"})

    assert result["rewritten_query"] == "cached rewrite"
    assert result["context"] == "grounded context"
    assert result["raw_answer"] == "cached answer"


def test_run_retriever_filters_noisy_source_nodes_and_caches_context(monkeypatch):
    captured: dict[str, object] = {}

    class DummyResponse:
        source_nodes = [
            NodeWithScore(
                node=TextNode(text="12 0 obj << /Type/Page /Resources 5 0 R >> endobj"),
                score=0.9,
            ),
            NodeWithScore(
                node=TextNode(
                    text=(
                        "The company reduced Scope 1 emissions by 12 percent and expanded worker "
                        "safety training across operations during the year."
                    )
                ),
                score=0.8,
            ),
            NodeWithScore(
                node=TextNode(
                    text=(
                        "The company reduced Scope 1 emissions by 12 percent and expanded worker "
                        "safety training across operations during the year."
                    )
                ),
                score=0.7,
            ),
        ]

        def __str__(self) -> str:
            return "Grounded answer."

    class DummyEngine:
        def query(self, _question: str) -> DummyResponse:
            return DummyResponse()

    def capture_cache(question: str, value: object, ttl_hours=None, ttl_seconds=None) -> None:
        captured["question"] = question
        captured["value"] = value

    monkeypatch.setattr(retriever_agent, "get_cache", lambda question: None)
    monkeypatch.setattr(retriever_agent, "_rewrite_query", lambda question: "rewritten query")
    monkeypatch.setattr(retriever_agent, "get_query_engine", lambda: DummyEngine())
    monkeypatch.setattr(retriever_agent, "set_cache", capture_cache)

    result = retriever_agent.run_retriever({"question": "How is environmental performance improving?"})

    assert result["rewritten_query"] == "rewritten query"
    assert "Scope 1 emissions" in result["context"]
    assert "worker safety training" in result["context"]
    assert "endobj" not in result["context"].lower()
    assert captured["question"] == "How is environmental performance improving?"
    assert captured["value"]["context"] == result["context"]
    assert captured["value"]["raw_answer"] == "Grounded answer."
