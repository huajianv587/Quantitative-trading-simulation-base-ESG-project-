from typing import Optional

from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.retrievers import AutoMergingRetriever, QueryFusionRetriever
from llama_index.core.retrievers.fusion_retriever import FUSION_MODES
from llama_index.core.schema import NodeWithScore, QueryBundle
from llama_index.retrievers.bm25 import BM25Retriever

from gateway.rag.text_quality import clean_document_text, make_text_fingerprint, score_text_quality, truncate_text

'''
BM25召回（关键词） ┐
                   ├→ Reciprocal Rank Fusion → 父节点扩展 → Rerank → 返回
Dense召回（语义）  ┘
'''


class QualityFilterPostprocessor(BaseNodePostprocessor):
    """Drop noisy or duplicated chunks before answer synthesis."""

    min_quality_score: float = 0.28
    max_nodes: int = 5
    max_chars_per_node: int = 1800

    @classmethod
    def class_name(cls) -> str:
        return "QualityFilterPostprocessor"

    def _postprocess_nodes(
        self,
        nodes: list[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None,
    ) -> list[NodeWithScore]:
        filtered: list[NodeWithScore] = []
        fallback: list[NodeWithScore] = []
        seen_fingerprints: set[str] = set()

        for node_with_score in nodes:
            raw_text = node_with_score.get_content()
            cleaned_text = truncate_text(
                clean_document_text(raw_text, min_line_score=0.20),
                self.max_chars_per_node,
            )
            if not cleaned_text:
                continue

            fingerprint = make_text_fingerprint(cleaned_text)
            if fingerprint and fingerprint in seen_fingerprints:
                continue
            if fingerprint:
                seen_fingerprints.add(fingerprint)

            try:
                node_with_score.node.set_content(cleaned_text)
            except Exception:
                pass

            if score_text_quality(cleaned_text) >= self.min_quality_score:
                filtered.append(node_with_score)
                if len(filtered) >= self.max_nodes:
                    break
            elif len(fallback) < self.max_nodes:
                fallback.append(node_with_score)

        if filtered:
            return filtered[: self.max_nodes]
        return fallback[: self.max_nodes]


def build_query_engine(
    index: VectorStoreIndex,
    storage_context: StorageContext,
    leaf_nodes: list,
    similarity_top_k: int = 12,
    rerank_top_n: int = 5,
) -> RetrieverQueryEngine:

    # 1. Dense retriever（语义）
    vector_retriever = index.as_retriever(similarity_top_k=similarity_top_k)

    # 2. BM25 retriever（关键词）
    bm25_retriever = BM25Retriever.from_defaults(
        nodes=leaf_nodes,
        similarity_top_k=similarity_top_k,
    )

    # 3. Reciprocal Rank Fusion
    fusion_retriever = QueryFusionRetriever(
        retrievers=[vector_retriever, bm25_retriever],
        similarity_top_k=similarity_top_k,
        num_queries=1,           # 不生成额外查询变体，只做融合
        mode=FUSION_MODES.RECIPROCAL_RANK,
        # FastAPI 请求链路里复用 async fusion 容易触发 "Event loop is closed"。
        # 上线场景优先稳态可用性，这里改为同步融合检索。
        use_async=False,
        verbose=True,
    )

    # 4. 父节点扩展（leaf 128 token → parent 512 token）
    auto_merging_retriever = AutoMergingRetriever(
        fusion_retriever,
        storage_context=storage_context,
        simple_ratio_thresh=0.4,   #leaf占某一个父 的超过占比40%，就把对应的整个父自动取出来
        verbose=True,
    )
  
    # 5. Query engine（不设相似度过滤，128-token 小 chunk 的相似度分数普遍偏低）
    query_engine = RetrieverQueryEngine(
        retriever=auto_merging_retriever,
        node_postprocessors=[
            QualityFilterPostprocessor(max_nodes=rerank_top_n),
        ],
    )

    return query_engine
