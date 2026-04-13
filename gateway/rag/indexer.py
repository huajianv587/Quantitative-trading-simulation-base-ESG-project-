import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from qdrant_client import QdrantClient, AsyncQdrantClient
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.vector_stores.qdrant import QdrantVectorStore

from gateway.rag.ingestion import _get_qdrant_client, COLLECTION_NAME

def _resolve_docstore_dir() -> str:
    configured = str(os.getenv("RAG_DOCSTORE_PERSIST_DIR", "") or "").strip()
    if configured:
        return str(Path(configured).expanduser())
    return str(Path(__file__).resolve().parents[2] / "storage" / "docstore")


# docstore 持久化目录（默认在项目内，可由 .env 覆盖）
PERSIST_DIR = _resolve_docstore_dir()


# ---------------------------------------------------------------------------
# 1. 检查 collection 是否已存在
# ---------------------------------------------------------------------------

def collection_exists(client: QdrantClient) -> bool:
    existing = [c.name for c in client.get_collections().collections]
    return COLLECTION_NAME in existing


def index_ready(client: QdrantClient | None = None) -> bool:
    try:
        client = client or _get_qdrant_client()[0]
        return collection_exists(client) and Path(PERSIST_DIR).exists()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 2. 持久化 docstore 到本地磁盘
# ---------------------------------------------------------------------------

def persist_storage(storage_context: StorageContext) -> None:
    """
    将 docstore（节点文本 + 父子层级）保存到本地 JSON 文件。
    每次新建 index 或插入/删除节点后调用。
    """
    Path(PERSIST_DIR).mkdir(parents=True, exist_ok=True)
    storage_context.persist(persist_dir=PERSIST_DIR)
    print(f"DocStore persisted to {PERSIST_DIR}")


# ---------------------------------------------------------------------------
# 3. 从磁盘 + Qdrant 恢复 index（服务重启后无需重新 embed）
# ---------------------------------------------------------------------------

def load_index() -> tuple[VectorStoreIndex, StorageContext]:
    """
    从本地 docstore JSON + Qdrant 向量恢复 index，不重新 embed。
    需要先调用过 persist_storage() 保存过 docstore。
    """
    client, aclient = _get_qdrant_client()

    if not collection_exists(client):
        raise RuntimeError(
            f"Collection '{COLLECTION_NAME}' not found in Qdrant. "
            "Run ingestion.build_index() first."
        )

    if not Path(PERSIST_DIR).exists():
        raise RuntimeError(
            f"DocStore not found at {PERSIST_DIR}. "
            "Run persist_storage() after building the index."
        )

    vector_store = QdrantVectorStore(client=client, aclient=aclient, collection_name=COLLECTION_NAME)

    # 从磁盘恢复 docstore（含父节点文本和层级结构）
    storage_context = StorageContext.from_defaults(
        vector_store=vector_store,
        persist_dir=PERSIST_DIR,
    )

    index = VectorStoreIndex.from_vector_store(
        vector_store,
        storage_context=storage_context,
    )
    print(f"Index loaded — Qdrant + DocStore from {PERSIST_DIR}")
    return index, storage_context


# ---------------------------------------------------------------------------
# 4. 增量插入新节点
# ---------------------------------------------------------------------------

def insert_nodes(
    index: VectorStoreIndex,
    storage_context: StorageContext,
    new_all_nodes: list,
    new_leaf_nodes: list,
) -> None:
    """
    插入新文档节点后自动持久化 docstore。
    new_all_nodes  — 全部节点（父 + 子），写入 docstore
    new_leaf_nodes — 叶节点，写入 Qdrant
    """
    storage_context.docstore.add_documents(new_all_nodes)
    index.insert_nodes(new_leaf_nodes)
    persist_storage(storage_context)
    print(f"Inserted {len(new_leaf_nodes)} leaf nodes, {len(new_all_nodes)} total nodes.")


# ---------------------------------------------------------------------------
# 5. 删除某公司旧数据
# ---------------------------------------------------------------------------

def delete_nodes_by_source(
    index: VectorStoreIndex,
    storage_context: StorageContext,
    source_file: str,
) -> None:
    """
    按来源文件名删除节点，删除后自动持久化 docstore。
    """
    all_node_ids = list(storage_context.docstore.docs.keys())
    to_delete = [
        nid for nid in all_node_ids
        if storage_context.docstore.get_document(nid).metadata.get("file_name") == source_file
    ]

    if not to_delete:
        print(f"No nodes found for source: {source_file}")
        return

    for nid in to_delete:
        index.delete_nodes([nid])

    persist_storage(storage_context)
    print(f"Deleted {len(to_delete)} nodes from source '{source_file}'.")


# ---------------------------------------------------------------------------
# 6. 统计当前库状态
# ---------------------------------------------------------------------------

def index_stats(client: QdrantClient | None = None) -> dict:
    client = client or _get_qdrant_client()[0]
    if not collection_exists(client):
        return {"status": "collection not found"}

    info = client.get_collection(COLLECTION_NAME)
    return {
        "collection": COLLECTION_NAME,
        "vector_count": info.vectors_count,
        "status": str(info.status),
        "docstore_path": PERSIST_DIR,
        "docstore_exists": Path(PERSIST_DIR).exists(),
    }
