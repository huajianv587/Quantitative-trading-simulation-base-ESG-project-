from __future__ import annotations

from collections import OrderedDict
from typing import Any

from llama_index.core.schema import QueryBundle


class QueryFusionRetriever:
    def __init__(
        self,
        retrievers: list[Any],
        similarity_top_k: int = 5,
        num_queries: int = 1,
        mode: str | None = None,
        use_async: bool = False,
        verbose: bool = False,
    ) -> None:
        self.retrievers = retrievers
        self.similarity_top_k = similarity_top_k
        self.num_queries = num_queries
        self.mode = mode
        self.use_async = use_async
        self.verbose = verbose

    def retrieve(self, query_bundle: QueryBundle | str):
        merged: OrderedDict[str, Any] = OrderedDict()
        for retriever in self.retrievers:
            if not hasattr(retriever, "retrieve"):
                continue
            for node in retriever.retrieve(query_bundle):
                key = node.get_content() if hasattr(node, "get_content") else str(node)
                merged.setdefault(key, node)
        return list(merged.values())[: self.similarity_top_k]


class AutoMergingRetriever:
    def __init__(
        self,
        retriever: Any,
        storage_context: Any = None,
        simple_ratio_thresh: float = 0.4,
        verbose: bool = False,
    ) -> None:
        self.retriever = retriever
        self.storage_context = storage_context
        self.simple_ratio_thresh = simple_ratio_thresh
        self.verbose = verbose

    def retrieve(self, query_bundle: QueryBundle | str):
        if hasattr(self.retriever, "retrieve"):
            return self.retriever.retrieve(query_bundle)
        return []


__all__ = ["AutoMergingRetriever", "QueryFusionRetriever"]

