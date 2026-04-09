from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TextNode(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    text: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    def get_content(self) -> str:
        return self.text

    def set_content(self, value: str) -> None:
        self.text = value


class NodeWithScore(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    node: TextNode
    score: float | None = None

    def get_content(self) -> str:
        return self.node.get_content()


class QueryBundle(BaseModel):
    query_str: str

