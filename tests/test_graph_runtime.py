import gateway.agents.graph as graph_module


def test_fallback_graph_runs_without_langgraph(monkeypatch):
    monkeypatch.setattr(graph_module, "_graph", None)
    monkeypatch.setattr(graph_module, "StateGraph", None)
    monkeypatch.setattr(graph_module, "run_router", lambda state: {**state, "task_type": "factual"})
    monkeypatch.setattr(graph_module, "run_retriever", lambda state: {**state, "raw_answer": "retrieved answer", "context": "retrieved context"})
    monkeypatch.setattr(graph_module, "run_analyst", lambda state: {**state, "esg_scores": {"overall_score": 80}})
    monkeypatch.setattr(
        graph_module,
        "run_verifier",
        lambda state: {**state, "final_answer": state.get("raw_answer", ""), "confidence": 0.7, "needs_retry": False},
    )

    result = graph_module.run_agent("Summarize Tesla ESG news", session_id="s1")

    assert result["final_answer"] == "retrieved answer"
    assert result["confidence"] == 0.7
