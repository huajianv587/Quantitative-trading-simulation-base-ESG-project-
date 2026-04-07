# retriever_agent.py — 检索 Agent
# 职责：query 改写 → 调用 RAG 引擎检索 → 返回上下文和初步答案
# 是 analyst 和 verifier 的数据来源，context 质量直接影响后续分析质量

from gateway.utils.llm_client import chat
from gateway.utils.logger import get_logger
from gateway.utils.cache import get_cache, set_cache   # 缓存：同一问题不重复调用 RAG
from gateway.rag.rag_main import get_query_engine       # 复用已有 RAG 引擎
from gateway.rag.text_quality import clean_document_text, make_text_fingerprint, score_text_quality, truncate_text
from gateway.agents.prompts import (
    RETRIEVER_REWRITE_SYSTEM,
    RETRIEVER_REWRITE_USER,
)

logger = get_logger(__name__)
MAX_CONTEXT_NODES = 6
MIN_CONTEXT_QUALITY_SCORE = 0.28
MAX_CONTEXT_NODE_CHARS = 1800


def _rewrite_query(question: str) -> str:
    """
    用 LLM 把用户口语化问题改写成更适合向量检索的专业表达。
    改写失败时直接返回原始问题（不影响主流程）。
    """
    messages = [
        {"role": "system", "content": RETRIEVER_REWRITE_SYSTEM},
        {"role": "user",   "content": RETRIEVER_REWRITE_USER.format(question=question)},
    ]
    try:
        rewritten = chat(messages, temperature=0.0, max_tokens=128).strip()
        logger.info(f"[Retriever] Rewritten query: {rewritten[:80]}...")
        return rewritten
    except Exception as e:
        logger.warning(f"[Retriever] Query rewrite failed: {e}, using original.")
        return question    # 失败降级：用原始问题继续，不中断流程


def _hydrate_cached_result(state: dict, question: str, cached: object) -> dict:
    if isinstance(cached, dict):
        return {
            **state,
            "rewritten_query": cached.get("rewritten_query", question),
            "context": cached.get("context", ""),
            "raw_answer": cached.get("raw_answer", ""),
        }

    return {**state, "rewritten_query": question, "context": "", "raw_answer": str(cached)}


def _build_context_from_source_nodes(source_nodes: list, raw_answer: str) -> tuple[str, int, int]:
    selected_chunks: list[str] = []
    fallback_chunks: list[str] = []
    seen_fingerprints: set[str] = set()
    dropped_count = 0

    for node in source_nodes:
        raw_text = node.get_content() if hasattr(node, "get_content") else str(node)
        cleaned_text = truncate_text(
            clean_document_text(raw_text, min_line_score=0.20),
            MAX_CONTEXT_NODE_CHARS,
        )
        if not cleaned_text:
            dropped_count += 1
            continue

        fingerprint = make_text_fingerprint(cleaned_text)
        if fingerprint and fingerprint in seen_fingerprints:
            dropped_count += 1
            continue
        if fingerprint:
            seen_fingerprints.add(fingerprint)

        if score_text_quality(cleaned_text) >= MIN_CONTEXT_QUALITY_SCORE:
            selected_chunks.append(cleaned_text)
        elif len(fallback_chunks) < 2:
            fallback_chunks.append(cleaned_text)
        else:
            dropped_count += 1
            continue

        if len(selected_chunks) >= MAX_CONTEXT_NODES:
            break

    chunks = selected_chunks or fallback_chunks
    if chunks:
        return "\n\n---\n\n".join(chunks[:MAX_CONTEXT_NODES]), len(chunks[:MAX_CONTEXT_NODES]), dropped_count

    cleaned_answer = truncate_text(
        clean_document_text(raw_answer, min_line_score=0.16),
        MAX_CONTEXT_NODE_CHARS,
    )
    return cleaned_answer or raw_answer, 0, dropped_count


def run_retriever(state: dict) -> dict:
    """
    检索 Agent：query 改写 → RAG 检索 → 返回上下文和答案。

    输入 state 字段:
        question (str): 用户问题

    输出 state 字段:
        rewritten_query (str): 改写后的检索 query
        context (str):         检索到的原始段落（供 analyst/verifier 引用）
        raw_answer (str):      RAG 直接生成的初步答案
    """
    question = state["question"]

    # ── 缓存检查：命中则跳过整个检索流程 ─────────────────────────────────
    cached = get_cache(question)
    if cached:
        logger.info("[Retriever] Cache hit, skipping retrieval.")
        return _hydrate_cached_result(state, question, cached)

    # ── Query 改写 ────────────────────────────────────────────────────────
    rewritten_query = _rewrite_query(question)

    # ── RAG 检索 ──────────────────────────────────────────────────────────
    try:
        engine = get_query_engine()
        response = engine.query(rewritten_query)
        raw_answer = str(response)

        # source_nodes 是 LlamaIndex 返回的检索到的原始段落节点
        source_nodes = getattr(response, "source_nodes", [])
        if source_nodes:
            context, kept_count, dropped_count = _build_context_from_source_nodes(
                source_nodes,
                raw_answer,
            )
        else:
            kept_count = 0
            dropped_count = 0
            context = truncate_text(
                clean_document_text(raw_answer, min_line_score=0.16),
                MAX_CONTEXT_NODE_CHARS,
            ) or raw_answer

        set_cache(question, {
            "rewritten_query": rewritten_query,
            "context": context,
            "raw_answer": raw_answer,
        })
        logger.info(
            "[Retriever] Retrieved %s source nodes, kept %s high-quality chunks, dropped %s noisy chunks.",
            len(source_nodes),
            kept_count,
            dropped_count,
        )

    except Exception as e:
        logger.error(f"[Retriever] RAG query failed: {e}")
        raw_answer = f"Retrieval failed: {e}"
        context = ""

    return {**state, "rewritten_query": rewritten_query, "context": context, "raw_answer": raw_answer}
