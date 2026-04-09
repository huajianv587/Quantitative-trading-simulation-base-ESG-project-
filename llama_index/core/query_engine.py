from __future__ import annotations

from typing import Any

from llama_index.core.schema import QueryBundle


class _FallbackResponse:
    def __init__(self, source_nodes) -> None:
        self.source_nodes = list(source_nodes or [])

    def __str__(self) -> str:
        parts: list[str] = []
        for item in self.source_nodes:
            if hasattr(item, "get_content"):
                parts.append(item.get_content())
            elif hasattr(item, "node") and hasattr(item.node, "get_content"):
                parts.append(item.node.get_content())
            else:
                parts.append(str(item))
        return "\n\n".join(part for part in parts if part).strip()


class RetrieverQueryEngine:
    def __init__(self, retriever: Any, node_postprocessors: list[Any] | None = None) -> None:
        self.retriever = retriever
        self.node_postprocessors = list(node_postprocessors or [])

    def query(self, query_str: str) -> _FallbackResponse:
        bundle = QueryBundle(query_str=query_str)
        if hasattr(self.retriever, "retrieve"):
            nodes = self.retriever.retrieve(bundle)
        else:
            nodes = []

        for processor in self.node_postprocessors:
            if hasattr(processor, "postprocess_nodes"):
                nodes = processor.postprocess_nodes(nodes, query_bundle=bundle)

        return _FallbackResponse(nodes)

