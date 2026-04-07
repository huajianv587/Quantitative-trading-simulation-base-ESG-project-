import os
import sys
import threading
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from llama_index.core import SimpleDirectoryReader, Settings
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.node_parser import get_leaf_nodes
from llama_index.core.llms import CustomLLM, LLMMetadata, CompletionResponse, CompletionResponseGen
from llama_index.core.llms.callbacks import llm_completion_callback

from gateway.rag.chunking  import chunk_documents
from gateway.rag.ingestion import build_index, COLLECTION_NAME
from gateway.rag.indexer   import collection_exists, load_index, persist_storage, _get_qdrant_client
from gateway.rag.embeddings import get_embed_model, validate_collection_embedding_dimension
from gateway.rag.retriever import build_query_engine
from gateway.rag.text_quality import clean_document_text
from gateway.utils.llm_client import chat as _llm_chat


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
        # LlamaIndex 把检索到的 context + 问题拼成 prompt 字符串传进来
        # 包装成 messages 格式传给我们的 chat() 函数
        messages = [{"role": "user", "content": prompt}]
        reply = _llm_chat(messages, max_tokens=self.num_output)
        return CompletionResponse(text=reply)

    @llm_completion_callback()
    def stream_complete(self, prompt: str, **_kwargs) -> CompletionResponseGen:
        # 不实现流式，直接返回完整结果
        response = self.complete(prompt)
        yield CompletionResponse(text=response.text, delta=response.text)


# 注册为 LlamaIndex 全局 LLM，所有 query_engine 都会走这套模型
Settings.llm = ESGLocalLLM()

# 查询和重建都走统一的 embedding provider。
Settings.embed_model = get_embed_model()

# ESG 报告存放目录
DATA_DIR = str(Path(__file__).resolve().parents[2] / "data" / "raw")

# 全局单例，避免重复初始化
_query_engine: RetrieverQueryEngine | None = None
_index = None
_storage_context = None
_init_lock = threading.Lock()


def get_query_engine(force_rebuild: bool = False) -> RetrieverQueryEngine:
    """
    返回可用的 query_engine，供 main.py 和 Agent 直接调用。

    启动逻辑：
      已有 Qdrant collection + docstore → 直接加载，秒级恢复
      否则                             → 读取 PDF → 切块 → 建库 → 持久化

    force_rebuild=True 时强制重新 embed（数据批量更新时使用）。
    """
    global _query_engine, _index, _storage_context
    if _query_engine is not None and not force_rebuild:
        return _query_engine

    with _init_lock:
        # double-check inside lock，防止并发重复建索引
        if _query_engine is not None and not force_rebuild:
            return _query_engine

        client, _ = _get_qdrant_client()

        need_rebuild = force_rebuild or not collection_exists(client)

        if not need_rebuild:
            # ── 快速恢复路径 ──────────────────────────────────────────
            try:
                validate_collection_embedding_dimension(
                    client.get_collection(COLLECTION_NAME),
                    COLLECTION_NAME,
                )
                print("[RAG] Existing index found — loading from Qdrant + docstore...")
                index, storage_context = load_index()
                leaf_nodes = _get_leaf_nodes_from_docstore(storage_context)
            except Exception as e:
                print(f"[RAG] Fast-load failed ({e}), falling back to rebuild...")
                need_rebuild = True

        if need_rebuild:
            # ── 首次建库 / 强制重建路径 ───────────────────────────────
            # 先删除旧 collection，防止重启时反复追加向量导致数据膨胀
            try:
                client.delete_collection("esg_docs")
                print("[RAG] Deleted stale Qdrant collection before rebuild.")
            except Exception:
                pass
            print(f"[RAG] Building index from documents in {DATA_DIR} ...")
            documents = _load_documents()
            all_nodes, leaf_nodes = chunk_documents(documents)
            index, storage_context = build_index(all_nodes, leaf_nodes)
            persist_storage(storage_context)

        _index = index
        _storage_context = storage_context
        _query_engine = build_query_engine(index, storage_context, leaf_nodes)
        print("[RAG] Query engine ready.")
        return _query_engine


def get_index_and_storage() -> tuple:
    """
    返回 (VectorStoreIndex, StorageContext)，供 event_indexer 增量写入使用。
    若 index 尚未初始化，会触发 get_query_engine() 完成初始化。
    """
    global _index, _storage_context
    if _index is None or _storage_context is None:
        get_query_engine()
    return _index, _storage_context


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------

def _load_documents():
    """从 data/raw 读取所有 PDF / docx / txt 文件。"""
    if not Path(DATA_DIR).exists():
        raise FileNotFoundError(
            f"Data directory not found: {DATA_DIR}\n"
            "Please put ESG reports (PDF/docx/txt) into data/raw/ first."
        )
    docs = SimpleDirectoryReader(
        DATA_DIR,
        required_exts=[".pdf", ".docx", ".txt", ".md"],
        recursive=True,
    ).load_data()

    if not docs:
        raise ValueError(f"No documents found in {DATA_DIR}")

    original_chars = 0
    cleaned_chars = 0
    for doc in docs:
        original = doc.text or ""
        original_chars += len(original)

        cleaned = clean_document_text(original, min_line_score=0.18)
        if not cleaned:
            cleaned = original.replace('\x00', ' ')

        cleaned_chars += len(cleaned)
        doc.set_content(cleaned)

    print(
        f"[RAG] Loaded {len(docs)} document(s) from {DATA_DIR} "
        f"(cleaned {original_chars:,} -> {cleaned_chars:,} chars)"
    )
    return docs


def _get_leaf_nodes_from_docstore(storage_context) -> list:
    """
    从已持久化的 docstore 中还原 leaf_nodes（无父节点的节点）。
    BM25Retriever 需要传入 leaf_nodes 才能构建关键词索引。
    """
    all_nodes = list(storage_context.docstore.docs.values())
    leaf_nodes = get_leaf_nodes(all_nodes)   # 无 child_nodes 的节点才是叶节点
    print(f"[RAG] Restored {len(leaf_nodes)} leaf nodes from docstore.")
    return leaf_nodes
