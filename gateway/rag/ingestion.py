import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import AsyncQdrantClient, QdrantClient

from gateway.utils.logger import get_logger

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent))

logger = get_logger(__name__)

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "esg_docs"


def _get_qdrant_client() -> tuple[QdrantClient, AsyncQdrantClient]:
    try:
        client = QdrantClient(url=QDRANT_URL, timeout=3, check_compatibility=False)
        client.get_collections()
        aclient = AsyncQdrantClient(url=QDRANT_URL, check_compatibility=False)
        logger.info("Connected to Qdrant at %s", QDRANT_URL)
        return client, aclient
    except Exception:
        logger.warning("Local Qdrant not reachable; using in-memory store.")
        return QdrantClient(":memory:"), AsyncQdrantClient(":memory:")


def build_index(all_nodes: list, leaf_nodes: list) -> tuple[VectorStoreIndex, StorageContext]:
    client, aclient = _get_qdrant_client()

    vector_store = QdrantVectorStore(
        client=client,
        aclient=aclient,
        collection_name=COLLECTION_NAME,
    )
    docstore = SimpleDocumentStore()
    docstore.add_documents(all_nodes)

    storage_context = StorageContext.from_defaults(
        vector_store=vector_store,
        docstore=docstore,
    )

    index = VectorStoreIndex(
        leaf_nodes,
        storage_context=storage_context,
        show_progress=True,
    )
    logger.info(
        "Index built with %s leaf nodes in Qdrant and %s total nodes in docstore.",
        len(leaf_nodes),
        len(all_nodes),
    )
    return index, storage_context
