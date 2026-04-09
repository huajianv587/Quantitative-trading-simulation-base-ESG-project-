from __future__ import annotations

import hashlib

from llama_index.core.base.embeddings.base import BaseEmbedding, Embedding


class OpenAIEmbedding(BaseEmbedding):
    model: str = "text-embedding-3-small"

    def _vector(self, text: str) -> Embedding:
        digest = hashlib.sha256(f"{self.model}:{text}".encode("utf-8")).digest()
        return [round(byte / 255.0, 6) for byte in digest[:16]]

    def _get_query_embedding(self, query: str) -> Embedding:
        return self._vector(query)

    def _get_text_embedding(self, text: str) -> Embedding:
        return self._vector(text)

