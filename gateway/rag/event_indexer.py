# event_indexer.py — Scheduler 事件 → Qdrant 向量库 桥接模块
# 职责：将 orchestrator 提取完成的 ExtractedEvent 异步写入 Qdrant
# 不阻塞主流程：后台线程执行，Supabase 与 Qdrant 双写并行

import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

# 保证从任意工作目录导入时，gateway.* 和 rag/* 都可访问
_project_root = Path(__file__).resolve().parents[2]
_rag_dir = Path(__file__).resolve().parent
for _p in [str(_project_root), str(_rag_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from llama_index.core import Document

from gateway.utils.logger import get_logger

logger = get_logger(__name__)

# 并发写入保护锁（Qdrant insert_nodes 非线程安全）
_lock = threading.Lock()


# ── 文档构建 ────────────────────────────────────────────────────────────────

def _build_document(event: dict) -> Document:
    """
    将 Supabase extracted_events 行 转换为 LlamaIndex Document。

    文本结构对检索友好：先放关键字段（company/type），再放描述，
    最后拼 key_metrics，方便语义匹配。
    """
    # key_metrics 在数据库中可能是 JSON 字符串
    raw_metrics = event.get("key_metrics") or {}
    if isinstance(raw_metrics, str):
        try:
            raw_metrics = json.loads(raw_metrics)
        except Exception:
            raw_metrics = {}

    metrics_text = ""
    if raw_metrics:
        lines = [f"  {k}: {v}" for k, v in raw_metrics.items() if v and v != "N/A"]
        if lines:
            metrics_text = "\nKey Metrics:\n" + "\n".join(lines)

    text = (
        f"Company: {event.get('company', 'Unknown')}\n"
        f"Event Type: {event.get('event_type', 'other')}\n"
        f"Impact Area: {event.get('impact_area', 'E')}\n"
        f"Severity: {event.get('severity', 'low')}\n"
        f"Title: {event.get('title', '')}\n"
        f"Description: {event.get('description', '')}"
        f"{metrics_text}"
    )

    return Document(
        text=text,
        metadata={
            "extracted_event_id": str(event.get("id", "")),
            "original_event_id": str(event.get("original_event_id", "")),
            "company": event.get("company", ""),
            "event_type": event.get("event_type", "other"),
            "impact_area": event.get("impact_area", "E"),
            "severity": event.get("severity", "low"),
            "source": "scheduler",
            "indexed_at": datetime.now(timezone.utc).isoformat(),
        },
        excluded_llm_metadata_keys=["extracted_event_id", "original_event_id", "indexed_at"],
        excluded_embed_metadata_keys=["extracted_event_id", "original_event_id", "indexed_at"],
    )


# ── 公共接口 ─────────────────────────────────────────────────────────────────

def index_events_async(event_ids: list[str]) -> None:
    """
    异步将已提取事件写入 Qdrant。
    在后台 daemon 线程中执行，不阻塞 orchestrator 主流程。

    Args:
        event_ids: extracted_events 表的 ID 列表（orchestrator stage 2 返回的 saved_ids）
    """
    if not event_ids:
        return

    thread = threading.Thread(
        target=_index_events_worker,
        args=(event_ids,),
        daemon=True,
        name="rag-indexer",
    )
    thread.start()
    logger.info(f"[EventIndexer] Async RAG indexing started for {len(event_ids)} event(s)")


# ── 后台工作函数 ──────────────────────────────────────────────────────────────

def _index_events_worker(event_ids: list[str]) -> None:
    """后台线程：从 Supabase 读事件 → 构建 Document → 切块 → 写入 Qdrant"""
    try:
        # ── 1. 从 Supabase 读取已提取的事件行 ───────────────────────────────
        from gateway.db.supabase_client import get_client
        db = get_client()
        resp = db.table("extracted_events").select("*").in_("id", event_ids).execute()
        events = resp.data

        if not events:
            logger.warning("[EventIndexer] No extracted events found in Supabase, skipping RAG indexing")
            return

        logger.info(f"[EventIndexer] Building documents for {len(events)} event(s)...")

        # ── 2. 转换为 LlamaIndex Document ────────────────────────────────────
        documents = [_build_document(e) for e in events]

        # ── 3. 分层切块（复用 rag/chunking.py 的层级切块逻辑）───────────────
        from chunking import chunk_documents
        all_nodes, leaf_nodes = chunk_documents(documents)

        # ── 4. 写入 Qdrant（加锁，防止多个 30min 周期并发写冲突）──────────
        with _lock:
            from rag_main import get_index_and_storage
            index, storage_context = get_index_and_storage()

            from indexer import insert_nodes
            insert_nodes(index, storage_context, all_nodes, leaf_nodes)

        logger.info(
            f"[EventIndexer] Done — {len(events)} event(s) → "
            f"{len(leaf_nodes)} leaf nodes inserted into Qdrant"
        )

    except Exception as e:
        logger.error(f"[EventIndexer] RAG indexing failed: {e}", exc_info=True)
