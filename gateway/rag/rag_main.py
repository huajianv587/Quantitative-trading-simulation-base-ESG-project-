import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from llama_index.core import SimpleDirectoryReader
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.node_parser import get_leaf_nodes

from chunking  import chunk_documents
from ingestion import build_index
from indexer   import collection_exists, load_index, persist_storage, _get_qdrant_client
from retriever import build_query_engine

# ESG 报告存放目录
DATA_DIR = str(Path(__file__).resolve().parents[2] / "data" / "raw")

# 全局单例，避免重复初始化
_query_engine: RetrieverQueryEngine | None = None


def get_query_engine(force_rebuild: bool = False) -> RetrieverQueryEngine:
    """
    返回可用的 query_engine，供 main.py 和 Agent 直接调用。

    启动逻辑：
      已有 Qdrant collection + docstore → 直接加载，秒级恢复
      否则                             → 读取 PDF → 切块 → 建库 → 持久化

    force_rebuild=True 时强制重新 embed（数据批量更新时使用）。
    """
    global _query_engine
    if _query_engine is not None and not force_rebuild:
        return _query_engine

    client, _ = _get_qdrant_client()

    if not force_rebuild and collection_exists(client):
        # ── 快速恢复路径 ──────────────────────────────────────────
        print("[RAG] Existing index found — loading from Qdrant + docstore...")
        index, storage_context = load_index()
        # BM25 需要 leaf_nodes，从 docstore 重建
        leaf_nodes = _get_leaf_nodes_from_docstore(storage_context)
    else:
        # ── 首次建库 / 强制重建路径 ───────────────────────────────
        print(f"[RAG] Building index from documents in {DATA_DIR} ...")
        documents = _load_documents()
        all_nodes, leaf_nodes = chunk_documents(documents)
        index, storage_context = build_index(all_nodes, leaf_nodes)
        persist_storage(storage_context)

    _query_engine = build_query_engine(index, storage_context, leaf_nodes)
    print("[RAG] Query engine ready.")
    return _query_engine


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

    print(f"[RAG] Loaded {len(docs)} document(s) from {DATA_DIR}")
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
