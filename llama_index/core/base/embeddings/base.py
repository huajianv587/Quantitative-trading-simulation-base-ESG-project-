from __future__ import annotations

from pydantic import BaseModel, ConfigDict

Embedding = list[float]


class BaseEmbedding(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    embed_batch_size: int = 100

    @classmethod
    def class_name(cls) -> str:
        return cls.__name__

    def get_query_embedding(self, query: str) -> Embedding:
        return self._get_query_embedding(query)

    async def aget_query_embedding(self, query: str) -> Embedding:
        return await self._aget_query_embedding(query)

    def get_text_embedding(self, text: str) -> Embedding:
        return self._get_text_embedding(text)

    def get_text_embeddings(self, texts: list[str]) -> list[Embedding]:
        return self._get_text_embeddings(texts)

    def _get_query_embedding(self, query: str) -> Embedding:
        raise NotImplementedError

    async def _aget_query_embedding(self, query: str) -> Embedding:
        return self._get_query_embedding(query)

    def _get_text_embedding(self, text: str) -> Embedding:
        raise NotImplementedError

    def _get_text_embeddings(self, texts: list[str]) -> list[Embedding]:
        return [self._get_text_embedding(text) for text in texts]

