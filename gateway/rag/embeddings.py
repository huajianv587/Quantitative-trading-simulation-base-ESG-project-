from __future__ import annotations

import hashlib
import os
import threading
from typing import Any, Optional

try:
    import torch
except Exception:
    class _TorchFallback:
        float16 = "float16"
        float32 = "float32"

        class cuda:
            @staticmethod
            def is_available() -> bool:
                return False

    torch = _TorchFallback()

from llama_index.core.base.embeddings.base import BaseEmbedding, Embedding
from llama_index.core.bridge.pydantic import Field, PrivateAttr
from llama_index.embeddings.openai import OpenAIEmbedding
try:
    from sentence_transformers import SentenceTransformer
except Exception:
    class SentenceTransformer:  # type: ignore[no-redef]
        transformers_model = None

        def __init__(self, model_name: str, **_kwargs) -> None:
            self.model_name = model_name

        def encode(self, texts: list[str], **_kwargs) -> list[list[float]]:
            return [self._vectorize(text) for text in texts]

        def get_sentence_embedding_dimension(self) -> int:
            return 384

        def _vectorize(self, text: str) -> list[float]:
            values: list[float] = []
            material = text.encode("utf-8")
            counter = 0
            while len(values) < self.get_sentence_embedding_dimension():
                digest = hashlib.sha256(material + counter.to_bytes(4, "little")).digest()
                values.extend(round(byte / 255.0, 6) for byte in digest)
                counter += 1
            return values[: self.get_sentence_embedding_dimension()]

from gateway.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_LOCAL_EMBEDDING_MODEL = "Alibaba-NLP/gte-Qwen2-1.5B-instruct"
KNOWN_EMBEDDING_DIMENSIONS = {
    "Alibaba-NLP/gte-Qwen2-1.5B-instruct": 1536,
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}
OPENAI_EMBEDDING_MODELS = {
    "text-embedding-3-small",
    "text-embedding-3-large",
    "text-embedding-ada-002",
}

_embed_model: BaseEmbedding | None = None
_embed_dimension: int | None = None
_embed_lock = threading.Lock()


def _clean_model_name(value: str) -> str:
    return value.split("#")[0].strip()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name, str(default))
    return str(value).lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int | None = None) -> int | None:
    value = os.getenv(name, "")
    if not value:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _looks_like_openai_embedding_model(model_name: str) -> bool:
    return _clean_model_name(model_name) in OPENAI_EMBEDDING_MODELS


def _resolve_embedding_provider() -> str:
    provider = os.getenv("EMBEDDING_PROVIDER", "local").strip().lower()
    return provider if provider in {"local", "openai"} else "local"


def _resolve_local_embedding_model() -> str:
    configured = _clean_model_name(os.getenv("LOCAL_EMBEDDING_MODEL", ""))
    if configured:
        return configured

    legacy_model = _clean_model_name(os.getenv("EMBEDDING_MODEL", ""))
    if legacy_model and not _looks_like_openai_embedding_model(legacy_model):
        return legacy_model

    if legacy_model:
        logger.warning(
            "[RAG] EMBEDDING_MODEL=%s points to an OpenAI embedding model; "
            "using LOCAL_EMBEDDING_MODEL=%s for local query embeddings.",
            legacy_model,
            DEFAULT_LOCAL_EMBEDDING_MODEL,
        )

    return DEFAULT_LOCAL_EMBEDDING_MODEL


def _resolve_embedding_dimension(model_name: str) -> int | None:
    configured = _env_int("EMBEDDING_DIMENSION")
    if configured:
        return configured
    return KNOWN_EMBEDDING_DIMENSIONS.get(_clean_model_name(model_name))


def _resolve_embedding_device() -> str:
    configured = os.getenv("EMBEDDING_DEVICE", "").strip().lower()
    if configured and configured != "auto":
        return configured
    return "cuda" if torch.cuda.is_available() else "cpu"


def _as_list(value: Any) -> list[float] | list[list[float]]:
    if hasattr(value, "tolist"):
        return value.tolist()
    return value


class LocalSentenceTransformerEmbedding(BaseEmbedding):
    model_name: str = Field(
        default=DEFAULT_LOCAL_EMBEDDING_MODEL,
        description="Local sentence-transformers embedding model.",
    )
    device: str = Field(default="cpu", description="Embedding inference device.")
    normalize_embeddings: bool = Field(
        default=True,
        description="Whether to L2-normalize embeddings before returning them.",
    )
    trust_remote_code: bool = Field(
        default=True,
        description="Allow custom Hub model code for local embedding models.",
    )
    local_files_only: bool = Field(
        default=False,
        description="Only load local embedding model files without downloading.",
    )
    query_prompt_name: Optional[str] = Field(
        default="query",
        description="SentenceTransformer prompt name for query embeddings.",
    )
    text_prompt_name: Optional[str] = Field(
        default="document",
        description="SentenceTransformer prompt name for document embeddings.",
    )
    query_instruction: str = Field(
        default="",
        description="Optional explicit query instruction for embedding models.",
    )
    text_instruction: str = Field(
        default="",
        description="Optional explicit document instruction for embedding models.",
    )
    configured_dimension: Optional[int] = Field(
        default=None,
        description="Expected embedding dimension used to validate existing collections.",
    )

    _model: SentenceTransformer | None = PrivateAttr(default=None)
    _load_lock: threading.Lock = PrivateAttr(default_factory=threading.Lock)

    @classmethod
    def class_name(cls) -> str:
        return "LocalSentenceTransformerEmbedding"

    def get_dimension(self) -> int | None:
        if self.configured_dimension:
            return self.configured_dimension

        model = self._get_model()
        self.configured_dimension = model.get_sentence_embedding_dimension()
        return self.configured_dimension

    def _get_model(self) -> SentenceTransformer:
        if self._model is not None:
            return self._model

        with self._load_lock:
            if self._model is not None:
                return self._model

            logger.info(
                "[RAG] Loading local embedding model %s on %s ...",
                self.model_name,
                self.device,
            )
            model_kwargs = {
                "dtype": torch.float16 if self.device.startswith("cuda") else torch.float32,
            }
            model = SentenceTransformer(
                self.model_name,
                device=self.device,
                trust_remote_code=self.trust_remote_code,
                local_files_only=self.local_files_only,
                model_kwargs=model_kwargs,
            )
            if model.transformers_model is not None and hasattr(model.transformers_model, "config"):
                setattr(model.transformers_model.config, "use_cache", False)
            self._model = model
            if self.configured_dimension is None:
                self.configured_dimension = model.get_sentence_embedding_dimension()
            logger.info(
                "[RAG] Local embedding model ready: %s (dimension=%s)",
                self.model_name,
                self.configured_dimension,
            )
            return model

    def _encode(self, texts: list[str], *, prompt_name: str | None, prompt: str | None) -> list[list[float]]:
        model = self._get_model()
        encode_kwargs: dict[str, Any] = {
            "convert_to_numpy": True,
            "normalize_embeddings": self.normalize_embeddings,
            "show_progress_bar": False,
        }
        if prompt:
            encode_kwargs["prompt"] = prompt
        elif prompt_name:
            encode_kwargs["prompt_name"] = prompt_name

        vectors = _as_list(model.encode(texts, **encode_kwargs))
        if texts and vectors and isinstance(vectors[0], float):
            return [vectors]
        return vectors

    def _get_query_embedding(self, query: str) -> Embedding:
        return self._encode(
            [query],
            prompt_name=self.query_prompt_name,
            prompt=self.query_instruction or None,
        )[0]

    async def _aget_query_embedding(self, query: str) -> Embedding:
        return self._get_query_embedding(query)

    def _get_text_embedding(self, text: str) -> Embedding:
        return self._encode(
            [text],
            prompt_name=self.text_prompt_name,
            prompt=self.text_instruction or None,
        )[0]

    def _get_text_embeddings(self, texts: list[str]) -> list[Embedding]:
        return self._encode(
            texts,
            prompt_name=self.text_prompt_name,
            prompt=self.text_instruction or None,
        )


def reset_embed_model() -> None:
    global _embed_model, _embed_dimension
    _embed_model = None
    _embed_dimension = None


def get_embed_model() -> BaseEmbedding:
    global _embed_model, _embed_dimension
    if _embed_model is not None:
        return _embed_model

    with _embed_lock:
        if _embed_model is not None:
            return _embed_model

        provider = _resolve_embedding_provider()
        embed_batch_size = _env_int("EMBEDDING_BATCH_SIZE", 100) or 100

        if provider == "openai":
            model_name = _clean_model_name(os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))
            _embed_dimension = _resolve_embedding_dimension(model_name)
            logger.info("[RAG] Using OpenAI embedding model %s", model_name)
            _embed_model = OpenAIEmbedding(
                model=model_name,
                embed_batch_size=embed_batch_size,
            )
            return _embed_model

        model_name = _resolve_local_embedding_model()
        configured_dimension = _resolve_embedding_dimension(model_name)
        device = _resolve_embedding_device()
        logger.info("[RAG] Using local embedding model %s on %s", model_name, device)
        _embed_model = LocalSentenceTransformerEmbedding(
            model_name=model_name,
            device=device,
            embed_batch_size=embed_batch_size,
            normalize_embeddings=_env_bool("EMBEDDING_NORMALIZE", True),
            trust_remote_code=_env_bool("EMBEDDING_TRUST_REMOTE_CODE", True),
            local_files_only=_env_bool("EMBEDDING_LOCAL_FILES_ONLY", False),
            query_prompt_name=os.getenv("EMBEDDING_QUERY_PROMPT_NAME", "query").strip() or None,
            text_prompt_name=os.getenv("EMBEDDING_TEXT_PROMPT_NAME", "document").strip() or None,
            query_instruction=os.getenv("EMBEDDING_QUERY_INSTRUCTION", "").strip(),
            text_instruction=os.getenv("EMBEDDING_TEXT_INSTRUCTION", "").strip(),
            configured_dimension=configured_dimension,
        )
        _embed_dimension = configured_dimension
        return _embed_model


def get_embed_dimension() -> int | None:
    global _embed_dimension
    model = get_embed_model()
    if _embed_dimension:
        return _embed_dimension
    if hasattr(model, "get_dimension"):
        _embed_dimension = model.get_dimension()
    return _embed_dimension


def _extract_vector_size(collection_info: Any) -> int | None:
    config = getattr(collection_info, "config", None)
    params = getattr(config, "params", None)
    vectors = getattr(params, "vectors", None)

    if vectors is None:
        return None

    size = getattr(vectors, "size", None)
    if size is not None:
        return int(size)

    if isinstance(vectors, dict) and vectors:
        first = next(iter(vectors.values()))
        if isinstance(first, dict) and "size" in first:
            return int(first["size"])
        if hasattr(first, "size"):
            return int(first.size)

    return None


def validate_collection_embedding_dimension(collection_info: Any, collection_name: str) -> None:
    expected = get_embed_dimension()
    actual = _extract_vector_size(collection_info)

    if expected is None or actual is None:
        return

    if expected != actual:
        raise RuntimeError(
            f"Embedding dimension mismatch for collection '{collection_name}': "
            f"collection={actual}, configured={expected}. "
            "Set LOCAL_EMBEDDING_MODEL/EMBEDDING_DIMENSION to the model used during indexing, "
            "or rebuild the Qdrant collection with the new embedding model."
        )
