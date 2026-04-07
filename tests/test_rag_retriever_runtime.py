from llama_index.core.schema import NodeWithScore, TextNode

from gateway.rag import retriever


def test_quality_filter_postprocessor_drops_noise_and_duplicates():
    postprocessor = retriever.QualityFilterPostprocessor(
        min_quality_score=0.28,
        max_nodes=2,
        max_chars_per_node=300,
    )
    nodes = [
        NodeWithScore(
            node=TextNode(text="12 0 obj << /Type/Page /Resources 5 0 R >> endobj"),
            score=0.9,
        ),
        NodeWithScore(
            node=TextNode(
                text=(
                    "The company reduced Scope 1 emissions by 12 percent and improved board "
                    "oversight of climate risk during the reporting year."
                )
            ),
            score=0.8,
        ),
        NodeWithScore(
            node=TextNode(
                text=(
                    "The company reduced Scope 1 emissions by 12 percent and improved board "
                    "oversight of climate risk during the reporting year."
                )
            ),
            score=0.7,
        ),
    ]

    processed = postprocessor.postprocess_nodes(nodes, query_str="climate risk")

    assert len(processed) == 1
    assert "Scope 1 emissions" in processed[0].get_content()
    assert "endobj" not in processed[0].get_content().lower()


def test_build_query_engine_disables_async_fusion(monkeypatch):
    captured = {}

    class DummyIndex:
        def as_retriever(self, similarity_top_k):
            captured["similarity_top_k"] = similarity_top_k
            return "vector"

    class DummyFusionRetriever:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class DummyBM25Retriever:
        @staticmethod
        def from_defaults(**kwargs):
            captured["bm25_nodes"] = kwargs["nodes"]
            return "bm25"

    monkeypatch.setattr(retriever, "QueryFusionRetriever", DummyFusionRetriever)
    monkeypatch.setattr(retriever, "BM25Retriever", DummyBM25Retriever)
    monkeypatch.setattr(
        retriever,
        "AutoMergingRetriever",
        lambda fusion_retriever, storage_context, simple_ratio_thresh, verbose: {
            "fusion_retriever": fusion_retriever,
            "storage_context": storage_context,
            "simple_ratio_thresh": simple_ratio_thresh,
            "verbose": verbose,
        },
    )
    monkeypatch.setattr(
        retriever,
        "RetrieverQueryEngine",
        lambda retriever, node_postprocessors: {
            "retriever": retriever,
            "node_postprocessors": node_postprocessors,
        },
    )

    engine = retriever.build_query_engine(DummyIndex(), "storage", ["leaf"])

    assert captured["use_async"] is False
    assert captured["bm25_nodes"] == ["leaf"]
    assert engine["retriever"]["storage_context"] == "storage"
    assert len(engine["node_postprocessors"]) == 1
    assert isinstance(engine["node_postprocessors"][0], retriever.QualityFilterPostprocessor)
    assert engine["node_postprocessors"][0].max_nodes == 5
