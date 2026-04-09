from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .schema import NodeWithScore, QueryBundle, TextNode


class Document(TextNode):
    pass


class _DocStore:
    def __init__(self, docs: dict[str, Any] | None = None) -> None:
        self.docs = docs or {}


@dataclass
class StorageContext:
    docstore: Any = field(default_factory=_DocStore)


class _SimpleRetriever:
    def __init__(self, nodes: list[Any], similarity_top_k: int = 5) -> None:
        self.nodes = list(nodes)
        self.similarity_top_k = similarity_top_k

    def retrieve(self, query_bundle: QueryBundle | str) -> list[NodeWithScore]:
        query_text = query_bundle.query_str if hasattr(query_bundle, "query_str") else str(query_bundle)
        query_terms = {term.lower() for term in query_text.split() if term.strip()}
        if not self.nodes:
            return []

        scored: list[NodeWithScore] = []
        for node in self.nodes:
            content = node.get_content() if hasattr(node, "get_content") else str(node)
            text = content.lower()
            score = sum(1 for term in query_terms if term in text)
            if not query_terms:
                score = 1
            if score:
                payload = node if isinstance(node, TextNode) else TextNode(text=content)
                scored.append(NodeWithScore(node=payload, score=float(score)))

        if not scored:
            fallback = self.nodes[: self.similarity_top_k]
            return [
                NodeWithScore(
                    node=item if isinstance(item, TextNode) else TextNode(text=str(item)),
                    score=0.0,
                )
                for item in fallback
            ]

        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[: self.similarity_top_k]


class VectorStoreIndex:
    def __init__(self, nodes: list[Any] | None = None) -> None:
        self.nodes = list(nodes or [])

    def as_retriever(self, similarity_top_k: int = 5) -> _SimpleRetriever:
        return _SimpleRetriever(self.nodes, similarity_top_k=similarity_top_k)


class SimpleDirectoryReader:
    def __init__(self, input_dir: str | Path, required_exts: list[str] | None = None, recursive: bool = False) -> None:
        self.input_dir = Path(input_dir)
        self.required_exts = {ext.lower() for ext in (required_exts or [])}
        self.recursive = recursive

    def load_data(self) -> list[Document]:
        if not self.input_dir.exists():
            return []

        pattern = "**/*" if self.recursive else "*"
        documents: list[Document] = []
        for path in self.input_dir.glob(pattern):
            if not path.is_file():
                continue
            if self.required_exts and path.suffix.lower() not in self.required_exts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
            documents.append(Document(text=text, metadata={"path": str(path)}))
        return documents


class Settings:
    llm: Any = None
    embed_model: Any = None


__all__ = [
    "Document",
    "NodeWithScore",
    "QueryBundle",
    "Settings",
    "SimpleDirectoryReader",
    "StorageContext",
    "TextNode",
    "VectorStoreIndex",
]

