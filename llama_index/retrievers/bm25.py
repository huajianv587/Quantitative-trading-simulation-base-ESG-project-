from __future__ import annotations

from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode


class BM25Retriever:
    def __init__(self, nodes: list, similarity_top_k: int = 5) -> None:
        self.nodes = list(nodes)
        self.similarity_top_k = similarity_top_k

    @classmethod
    def from_defaults(cls, nodes: list, similarity_top_k: int = 5):
        return cls(nodes=nodes, similarity_top_k=similarity_top_k)

    def retrieve(self, query_bundle: QueryBundle | str) -> list[NodeWithScore]:
        query_text = query_bundle.query_str if hasattr(query_bundle, "query_str") else str(query_bundle)
        query_terms = [term.lower() for term in query_text.split() if term.strip()]
        matches: list[NodeWithScore] = []

        for raw_node in self.nodes:
            node = raw_node if isinstance(raw_node, TextNode) else TextNode(text=str(raw_node))
            content = node.get_content().lower()
            score = float(sum(1 for term in query_terms if term in content))
            if score > 0:
                matches.append(NodeWithScore(node=node, score=score))

        if not matches:
            return [
                NodeWithScore(
                    node=item if isinstance(item, TextNode) else TextNode(text=str(item)),
                    score=0.0,
                )
                for item in self.nodes[: self.similarity_top_k]
            ]

        matches.sort(key=lambda item: item.score or 0.0, reverse=True)
        return matches[: self.similarity_top_k]

