import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from qdrant_client import QdrantClient, AsyncQdrantClient
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.vector_stores.qdrant import QdrantVectorStore

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "esg_docs"  #一个叫 esgdocs 的向量数据表 / 向量集合


def _get_qdrant_client() -> tuple[QdrantClient, AsyncQdrantClient]:
    try:
        client = QdrantClient(url=QDRANT_URL, timeout=3)
        client.get_collections() #它不是单纯创建对象，而是主动发一个请求测试 Qdrant 是否真的可用
        aclient = AsyncQdrantClient(url=QDRANT_URL)
        print(f"Connected to Qdrant at {QDRANT_URL}")
        return client, aclient
    except Exception:
        print("Local Qdrant not reachable — using in-memory store.")
        return QdrantClient(":memory:"), AsyncQdrantClient(":memory:")


def build_index(all_nodes: list, leaf_nodes: list) -> tuple[VectorStoreIndex, StorageContext]:
    """
    Build a VectorStoreIndex on leaf_nodes (stored in Qdrant),
    with all_nodes in the docstore so AutoMergingRetriever can merge up.  这是为了支持"检索后向上合并"。

    Returns:
        index           — built on leaf nodes
        storage_context — holds both vector store and docstore
    """
    client, aclient = _get_qdrant_client()

    vector_store = QdrantVectorStore(
        client=client,
        aclient=aclient,
        collection_name=COLLECTION_NAME,
    )
    docstore = SimpleDocumentStore()  #新建一个文档存储器，节点对象仓库
    docstore.add_documents(all_nodes) #里面除了文本，还有结构信息。

    storage_context = StorageContext.from_defaults(
        vector_store=vector_store,
        docstore=docstore,
    )

    index = VectorStoreIndex(
        leaf_nodes,
        storage_context=storage_context,
        show_progress=True,
    )
    print(f"Index built — {len(leaf_nodes)} leaf nodes in Qdrant, {len(all_nodes)} total nodes in docstore.")
    return index, storage_context

'''
1. collection 是 Qdrant 里的一个"向量集合 / 向量表"，不是一个点
2. esg_docs 只是这个 collection 的名字，表示里面存的是 ESG 文档相关向量
3. vector_store 负责存向量和做相似度检索
4. docstore 负责存节点对象、原文本、层级关系
5. storage_context 是把 vector_store 和 docstore 打包起来的存储上下文
6. index 建立在节点之上，检索时先查向量，再根据节点信息拿回原文和结构，必要时再向上合并
'''