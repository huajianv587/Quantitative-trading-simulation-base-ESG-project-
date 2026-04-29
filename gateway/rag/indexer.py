import os
from pathlib import Path

from dotenv import load_dotenv
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

from gateway.rag.ingestion import COLLECTION_NAME, _get_qdrant_client
from gateway.utils.logger import get_logger

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

logger = get_logger(__name__)


def _resolve_docstore_dir() -> str:
    configured = str(os.getenv("RAG_DOCSTORE_PERSIST_DIR", "") or "").strip()
    if configured:
        return str(Path(configured).expanduser())
    return str(Path(__file__).resolve().parents[2] / "storage" / "docstore")


PERSIST_DIR = _resolve_docstore_dir()


def collection_exists(client: QdrantClient) -> bool:
    existing = [collection.name for collection in client.get_collections().collections]
    return COLLECTION_NAME in existing


def index_ready(client: QdrantClient | None = None) -> bool:
    try:
        client = client or _get_qdrant_client()[0]
        return collection_exists(client) and Path(PERSIST_DIR).exists()
    except Exception:
        return False


def persist_storage(storage_context: StorageContext) -> None:
    Path(PERSIST_DIR).mkdir(parents=True, exist_ok=True)
    storage_context.persist(persist_dir=PERSIST_DIR)
    logger.info("DocStore persisted to %s", PERSIST_DIR)


def load_index() -> tuple[VectorStoreIndex, StorageContext]:
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
    storage_context = StorageContext.from_defaults(
        vector_store=vector_store,
        persist_dir=PERSIST_DIR,
    )

    index = VectorStoreIndex.from_vector_store(
        vector_store,
        storage_context=storage_context,
    )
    logger.info("Index loaded from Qdrant and DocStore at %s", PERSIST_DIR)
    return index, storage_context


def insert_nodes(
    index: VectorStoreIndex,
    storage_context: StorageContext,
    new_all_nodes: list,
    new_leaf_nodes: list,
) -> None:
    storage_context.docstore.add_documents(new_all_nodes)
    index.insert_nodes(new_leaf_nodes)
    persist_storage(storage_context)
    logger.info(
        "Inserted %s leaf nodes and %s total nodes.",
        len(new_leaf_nodes),
        len(new_all_nodes),
    )


def delete_nodes_by_source(
    index: VectorStoreIndex,
    storage_context: StorageContext,
    source_file: str,
) -> None:
    all_node_ids = list(storage_context.docstore.docs.keys())
    to_delete = [
        node_id
        for node_id in all_node_ids
        if storage_context.docstore.get_document(node_id).metadata.get("file_name") == source_file
    ]

    if not to_delete:
        logger.info("No nodes found for source: %s", source_file)
        return

    for node_id in to_delete:
        index.delete_nodes([node_id])

    persist_storage(storage_context)
    logger.info("Deleted %s nodes from source '%s'.", len(to_delete), source_file)


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
