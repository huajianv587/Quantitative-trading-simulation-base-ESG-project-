from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict

from llama_index.core.schema import QueryBundle


class BaseNodePostprocessor(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def class_name(cls) -> str:
        return cls.__name__

    def postprocess_nodes(
        self,
        nodes,
        query_bundle: Optional[QueryBundle] = None,
        query_str: str | None = None,
    ):
        if query_bundle is None and query_str is not None:
            query_bundle = QueryBundle(query_str=query_str)
        return self._postprocess_nodes(nodes, query_bundle=query_bundle)

    def _postprocess_nodes(self, nodes, query_bundle: Optional[QueryBundle] = None):
        return nodes

