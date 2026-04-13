import json
import os
import re
import threading
from pathlib import Path

from dotenv import load_dotenv

from gateway.rag.text_quality import clean_document_text, make_text_fingerprint, truncate_text
from gateway.utils.llm_client import chat as _llm_chat
from gateway.utils.logger import get_logger

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

logger = get_logger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "raw"
RAG_TRAINING_DIR = PROJECT_ROOT / "data" / "rag_training_data"

_query_engine = None
_index = None
_storage_context = None
_init_lock = threading.Lock()

_FULL_STACK_ERROR = None
_FALLBACK_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "about",
    "what",
    "when",
    "where",
    "which",
    "tell",
    "into",
    "your",
    "have",
    "will",
    "would",
    "could",
    "should",
    "there",
    "here",
    "they",
    "them",
    "their",
    "about",
    "me",
    "at",
    "an",
}


def _parse_source_dir_tokens(value: str) -> list[str]:
    if not value:
        return []
    return [item.strip().strip('"').strip("'") for item in re.split(r"[;\n,]+", value) if item.strip()]


def _resolve_source_dir(token: str) -> Path:
    candidate = Path(token).expanduser()
    if not candidate.is_absolute():
        candidate = (PROJECT_ROOT / candidate).resolve()
    return candidate


def _configured_source_dirs() -> list[Path]:
    configured = _parse_source_dir_tokens(str(os.getenv("RAG_SOURCE_DIRS", "") or ""))
    defaults = configured or [str(DATA_DIR)]
    resolved: list[Path] = []
    seen: set[str] = set()
    for token in defaults:
        path = _resolve_source_dir(token)
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        resolved.append(path)
    return resolved


def _skip_autobuild_on_read() -> bool:
    value = str(os.getenv("RAG_SKIP_AUTOBUILD_ON_READ", "true") or "true").strip().lower()
    return value not in {"0", "false", "no", "off"}

try:
    from llama_index.core import Settings, SimpleDirectoryReader
    from llama_index.core.llms import CompletionResponse, CompletionResponseGen, CustomLLM, LLMMetadata
    from llama_index.core.llms.callbacks import llm_completion_callback
    from llama_index.core.node_parser import get_leaf_nodes
    from llama_index.core.query_engine import RetrieverQueryEngine

    from gateway.rag.chunking import chunk_documents
    from gateway.rag.embeddings import get_embed_model, validate_collection_embedding_dimension
    from gateway.rag.indexer import _get_qdrant_client, collection_exists, load_index, persist_storage
    from gateway.rag.ingestion import COLLECTION_NAME, build_index
    from gateway.rag.retriever import build_query_engine
except Exception as exc:  # pragma: no cover - runtime import guard
    _FULL_STACK_ERROR = exc
    Settings = None
    SimpleDirectoryReader = None
    CompletionResponse = None
    CompletionResponseGen = None
    CustomLLM = None
    LLMMetadata = None
    llm_completion_callback = None
    get_leaf_nodes = None
    RetrieverQueryEngine = None
    chunk_documents = None
    get_embed_model = None
    validate_collection_embedding_dimension = None
    _get_qdrant_client = None
    collection_exists = None
    load_index = None
    persist_storage = None
    COLLECTION_NAME = "esg_docs"
    build_index = None
    build_query_engine = None


class _FallbackSourceNode:
    def __init__(self, text: str, metadata: dict | None = None) -> None:
        self.text = text
        self.metadata = metadata or {}

    def get_content(self) -> str:
        return self.text


class _FallbackResponse:
    def __init__(self, answer: str, source_nodes: list[_FallbackSourceNode]) -> None:
        self.answer = answer
        self.source_nodes = list(source_nodes)

    def __str__(self) -> str:
        return self.answer


class _FallbackQueryEngine:
    def __init__(self, nodes: list[_FallbackSourceNode]) -> None:
        self.nodes = nodes

    def query(self, query_str: str) -> _FallbackResponse:
        query_terms = {
            token.lower()
            for token in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,}", query_str)
            if token.strip() and (len(token.strip()) >= 3 or re.search(r"[\u4e00-\u9fff]", token)) and token.lower() not in _FALLBACK_STOPWORDS
        }

        scored: list[tuple[int, _FallbackSourceNode]] = []
        for node in self.nodes:
            content = node.get_content().lower()
            score = sum(1 for term in query_terms if term in content)
            if score:
                scored.append((score, node))

        if not scored:
            selected = []
        else:
            scored.sort(key=lambda item: item[0], reverse=True)
            selected = [item[1] for item in scored[:3]]

        if not selected:
            answer = (
                "Local fallback RAG is available, but no relevant ESG evidence matched the query. "
                "Add company documents to the directories configured by RAG_SOURCE_DIRS or extend the ESG QA corpus under data/rag_training_data/."
            )
            return _FallbackResponse(answer, [])

        context = "\n\n".join(node.get_content() for node in selected if node.get_content()).strip()
        prompt = (
            "You are an ESG research copilot. Summarize the retrieved evidence in a grounded way.\n\n"
            f"Question: {query_str}\n\n"
            f"Retrieved evidence:\n{context}"
        )
        try:
            answer = _llm_chat([{"role": "user", "content": prompt}], max_tokens=512)
        except Exception as exc:  # pragma: no cover - defensive runtime fallback
            logger.warning(f"[RAG] Fallback summarization failed: {exc}")
            answer = truncate_text(context, 900)

        return _FallbackResponse(answer, selected)


def _load_fallback_documents() -> list[_FallbackSourceNode]:
    nodes: list[_FallbackSourceNode] = []
    seen: set[str] = set()

    nodes.extend(_load_fallback_training_qa(seen))

    source_paths: list[Path] = []

    if DATA_DIR.exists():
        source_paths.extend(
            path for path in DATA_DIR.rglob("*")
            if path.is_file() and path.suffix.lower() in {".md", ".txt", ".docx", ".pdf"}
        )

    docs_dir = PROJECT_ROOT / "docs"
    if docs_dir.exists():
        source_paths.extend(
            path for path in docs_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in {".md", ".txt"}
        )

    readme_path = PROJECT_ROOT / "README.md"
    if readme_path.exists():
        source_paths.append(readme_path)

    for path in source_paths[:40]:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        cleaned = clean_document_text(text, min_line_score=0.16)
        cleaned = truncate_text(cleaned or text, 2200)
        if not cleaned:
            continue

        fingerprint = make_text_fingerprint(cleaned)
        if fingerprint and fingerprint in seen:
            continue
        if fingerprint:
            seen.add(fingerprint)
        nodes.append(_FallbackSourceNode(cleaned, metadata={"path": str(path)}))

    if nodes:
        logger.info(f"[RAG] Loaded {len(nodes)} fallback document(s) from local workspace.")
        return nodes

    logger.warning("[RAG] No local documents found for fallback retrieval; using built-in starter knowledge.")
    return [
        _FallbackSourceNode(
            "ESG analysis should combine environmental, social and governance evidence, "
            "highlight material risks, and keep conclusions tied to retrieved documents."
        ),
        _FallbackSourceNode(
            "When external APIs or vector indexes are unavailable, the local runtime should "
            "still provide grounded summaries, explain degraded mode, and preserve the UI flow."
        ),
        _FallbackSourceNode(
            "Daily and weekly ESG reporting focuses on recent events, company-level score movement, "
            "risk alerts, and recommended follow-up actions for operators."
        ),
    ]


def _load_fallback_training_qa(seen: set[str], limit_per_file: int = 180) -> list[_FallbackSourceNode]:
    if not RAG_TRAINING_DIR.exists():
        return []

    nodes: list[_FallbackSourceNode] = []
    for name in ("val.jsonl", "train.jsonl"):
        path = RAG_TRAINING_DIR / name
        if not path.exists():
            continue

        loaded = 0
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    if loaded >= limit_per_file:
                        break

                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    messages = row.get("messages") or []
                    user_message = next((item.get("content", "") for item in messages if item.get("role") == "user"), "")
                    assistant_message = next((item.get("content", "") for item in messages if item.get("role") == "assistant"), "")
                    if not user_message or not assistant_message:
                        continue

                    text = f"Question: {user_message}\nAnswer: {assistant_message}"
                    cleaned = truncate_text(clean_document_text(text, min_line_score=0.12) or text, 1200)
                    if not cleaned:
                        continue

                    fingerprint = make_text_fingerprint(cleaned)
                    if fingerprint and fingerprint in seen:
                        continue
                    if fingerprint:
                        seen.add(fingerprint)

                    nodes.append(
                        _FallbackSourceNode(
                            cleaned,
                            metadata={
                                "path": str(path),
                                "source": "rag_training_data",
                            },
                        )
                    )
                    loaded += 1
        except Exception as exc:
            logger.warning(f"[RAG] Failed to load fallback QA pairs from {path}: {exc}")

    if nodes:
        logger.info(f"[RAG] Loaded {len(nodes)} fallback ESG QA node(s) from training data.")
    return nodes


def _build_fallback_query_engine(reason: str) -> _FallbackQueryEngine:
    logger.warning(f"[RAG] Using lightweight fallback query engine: {reason}")
    return _FallbackQueryEngine(_load_fallback_documents())


if _FULL_STACK_ERROR is None and Settings is not None and CustomLLM is not None:
    class ESGLocalLLM(CustomLLM):
        context_window: int = 4096
        num_output: int = 1024
        model_name: str = "esg-local-with-fallback"

        @property
        def metadata(self) -> LLMMetadata:
            return LLMMetadata(
                context_window=self.context_window,
                num_output=self.num_output,
                model_name=self.model_name,
            )

        @llm_completion_callback()
        def complete(self, prompt: str, **_kwargs) -> CompletionResponse:
            messages = [{"role": "user", "content": prompt}]
            reply = _llm_chat(messages, max_tokens=self.num_output)
            return CompletionResponse(text=reply)

        @llm_completion_callback()
        def stream_complete(self, prompt: str, **_kwargs) -> CompletionResponseGen:
            response = self.complete(prompt)
            yield CompletionResponse(text=response.text, delta=response.text)


    Settings.llm = ESGLocalLLM()
    Settings.embed_model = get_embed_model()


def get_query_engine(force_rebuild: bool = False):
    global _query_engine, _index, _storage_context
    if _query_engine is not None and not force_rebuild:
        return _query_engine

    with _init_lock:
        if _query_engine is not None and not force_rebuild:
            return _query_engine

        if _FULL_STACK_ERROR is not None:
            _query_engine = _build_fallback_query_engine(str(_FULL_STACK_ERROR))
            return _query_engine

        try:
            client, _ = _get_qdrant_client()
            need_rebuild = force_rebuild or not collection_exists(client)
            if need_rebuild and not force_rebuild and _skip_autobuild_on_read():
                _query_engine = _build_fallback_query_engine(
                    "RAG index is not ready yet. Run scripts/rebuild_rag_index.py for a full Qdrant rebuild."
                )
                return _query_engine

            if not need_rebuild:
                try:
                    validate_collection_embedding_dimension(
                        client.get_collection(COLLECTION_NAME),
                        COLLECTION_NAME,
                    )
                    logger.info("[RAG] Existing index found, loading from Qdrant + docstore...")
                    index, storage_context = load_index()
                    leaf_nodes = _get_leaf_nodes_from_docstore(storage_context)
                except Exception as exc:
                    logger.warning(f"[RAG] Fast-load failed ({exc}), rebuilding index instead.")
                    need_rebuild = True

            if need_rebuild:
                try:
                    client.delete_collection("esg_docs")
                except Exception:
                    pass
                logger.info(f"[RAG] Building index from documents in {DATA_DIR} ...")
                documents = _load_documents()
                all_nodes, leaf_nodes = chunk_documents(documents)
                index, storage_context = build_index(all_nodes, leaf_nodes)
                persist_storage(storage_context)

            _index = index
            _storage_context = storage_context
            _query_engine = build_query_engine(index, storage_context, leaf_nodes)
            logger.info("[RAG] Full query engine ready.")
            return _query_engine
        except Exception as exc:
            _index = None
            _storage_context = None
            _query_engine = _build_fallback_query_engine(str(exc))
            return _query_engine


def get_index_and_storage() -> tuple:
    if _FULL_STACK_ERROR is not None:
        return None, None
    global _index, _storage_context
    if _index is None or _storage_context is None:
        get_query_engine()
    return _index, _storage_context


def _load_documents():
    source_dirs = _configured_source_dirs()
    existing_dirs = [path for path in source_dirs if path.exists()]
    if not existing_dirs:
        configured_display = ", ".join(str(path) for path in source_dirs)
        raise FileNotFoundError(
            f"No RAG source directories were found. Checked: {configured_display}\n"
            "Set RAG_SOURCE_DIRS in .env or put ESG reports into data/raw/."
        )

    docs = []
    loaded_from: list[str] = []
    for source_dir in existing_dirs:
        batch = SimpleDirectoryReader(
            source_dir,
            required_exts=[".pdf", ".docx", ".txt", ".md"],
            recursive=True,
        ).load_data()
        if not batch:
            continue
        for doc in batch:
            metadata = dict(getattr(doc, "metadata", {}) or {})
            metadata.setdefault("rag_source_dir", str(source_dir))
            metadata.setdefault("rag_source_type", "external_raw_corpus" if source_dir != DATA_DIR else "project_raw_corpus")
            doc.metadata = metadata
        docs.extend(batch)
        loaded_from.append(str(source_dir))

    if not docs:
        raise ValueError(
            "No ESG documents were found in the configured RAG sources: "
            + ", ".join(str(path) for path in existing_dirs)
        )

    original_chars = 0
    cleaned_chars = 0
    for doc in docs:
        original = doc.text or ""
        original_chars += len(original)

        cleaned = clean_document_text(original, min_line_score=0.18)
        if not cleaned:
            cleaned = original.replace("\x00", " ")

        cleaned_chars += len(cleaned)
        doc.set_content(cleaned)

    logger.info(
        f"[RAG] Loaded {len(docs)} document(s) from {', '.join(loaded_from)} "
        f"(cleaned {original_chars:,} -> {cleaned_chars:,} chars)"
    )
    return docs


def _get_leaf_nodes_from_docstore(storage_context) -> list:
    all_nodes = list(storage_context.docstore.docs.values())
    leaf_nodes = get_leaf_nodes(all_nodes)
    logger.info(f"[RAG] Restored {len(leaf_nodes)} leaf nodes from docstore.")
    return leaf_nodes
