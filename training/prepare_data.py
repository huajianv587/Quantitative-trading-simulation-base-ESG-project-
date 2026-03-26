"""
prepare_data.py
---------------
从 DocStore 读取所有 leaf chunk，调用 DeepSeek 为每个 chunk 生成 3 个 QA 对，
清洗过滤后输出 Qwen2.5 ChatML 格式 JSONL，并划分 train / val。

输出文件（默认路径）：
    data/processed/train.jsonl
    data/processed/val.jsonl

每行格式（ChatML / messages 格式）：
    {
      "messages": [
        {"role": "system",    "content": "You are an ESG analyst..."},
        {"role": "user",      "content": "<question>"},
        {"role": "assistant", "content": "<answer>"}
      ]
    }

用法：
    python training/prepare_data.py
    python training/prepare_data.py --workers 4 --val-ratio 0.1 --max-chunks 50
"""

import os
import sys
import json
import time
import argparse
import re
import random
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm

# ── 路径设置 ────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
sys.path.insert(0, str(PROJECT_ROOT / "gateway" / "rag"))

PERSIST_DIR   = str(PROJECT_ROOT / "storage" / "docstore")
DEFAULT_TRAIN = str(PROJECT_ROOT / "data" / "processed" / "train.jsonl")
DEFAULT_VAL   = str(PROJECT_ROOT / "data" / "processed" / "val.jsonl")

SYSTEM_CONTENT = (
    "You are an expert ESG (Environmental, Social, Governance) analyst. "
    "Answer questions accurately and concisely based on the provided context."
)

# ── DeepSeek 客户端 ─────────────────────────────────────────────────────────
def get_deepseek_client() -> OpenAI:
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY not set in .env")
    return OpenAI(api_key=key, base_url="https://api.deepseek.com")


# ── 加载 leaf nodes ─────────────────────────────────────────────────────────
def load_leaf_nodes() -> list[dict]:
    """
    从 SimpleDocumentStore 直接读取 leaf chunk，不依赖 Qdrant。
    返回 [{"id": ..., "text": ..., "source": ...}, ...]
    """
    from llama_index.core.storage.docstore import SimpleDocumentStore
    from llama_index.core.node_parser import get_leaf_nodes

    print(f"[DocStore] Loading from {PERSIST_DIR} ...")
    docstore = SimpleDocumentStore.from_persist_dir(PERSIST_DIR)
    all_nodes = list(docstore.docs.values())
    print(f"[DocStore] Total nodes: {len(all_nodes)}")

    leaf_nodes = get_leaf_nodes(all_nodes)
    print(f"[DocStore] Leaf nodes (128-token chunks): {len(leaf_nodes)}")

    return [
        {
            "id":     node.node_id,
            "text":   node.get_content().strip(),
            "source": node.metadata.get("file_name", "unknown"),
        }
        for node in leaf_nodes
        if node.get_content().strip()
    ]


# ── Prompt ───────────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """You are an expert ESG analyst.
Given a text chunk, generate exactly 3 high-quality question-answer pairs for fine-tuning.

Rules:
- Questions must be directly answerable from the chunk
- Answers must be concise (1-3 sentences) and grounded in the chunk
- Do NOT copy the question verbatim into the answer
- Cover different aspects if possible (facts, reasons, comparisons)
- Output valid JSON only, no extra text

Output format:
[
  {"question": "...", "answer": "..."},
  {"question": "...", "answer": "..."},
  {"question": "...", "answer": "..."}
]"""

_USER_TEMPLATE = "Text chunk:\n\"\"\"\n{text}\n\"\"\"\n\nGenerate 3 QA pairs:"


# ── DeepSeek 调用（含重试）───────────────────────────────────────────────────
def generate_qa_pairs(
    client: OpenAI,
    chunk: dict,
    retries: int = 3,
    backoff: float = 2.0,
) -> list[dict]:
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user",   "content": _USER_TEMPLATE.format(text=chunk["text"])},
                ],
                temperature=0.7,
                max_tokens=1024,
                response_format={"type": "json_object"} if attempt == 0 else None,
            )
            raw = resp.choices[0].message.content.strip()
            return _parse_and_filter(raw, chunk)

        except Exception as e:
            if attempt < retries - 1:
                time.sleep(backoff ** attempt)
            else:
                print(f"\n[WARN] Chunk {chunk['id'][:8]} failed: {e}")
                return []
    return []


# ── 解析 & 清洗 ──────────────────────────────────────────────────────────────
_MIN_Q = 15
_MAX_Q = 300
_MIN_A = 20


def _parse_and_filter(raw: str, chunk: dict) -> list[dict]:
    """解析 JSON，过滤低质量 QA，转换为 ChatML messages 格式。"""
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    data = v
                    break
            else:
                data = []
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            return []
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            return []

    results = []
    context  = chunk["text"]
    ctx_words = set(context.lower().split())

    for item in data:
        if not isinstance(item, dict):
            continue
        q = str(item.get("question", "")).strip()
        a = str(item.get("answer",   "")).strip()

        # 长度过滤
        if not (_MIN_Q <= len(q) <= _MAX_Q):
            continue
        if len(a) < _MIN_A:
            continue
        # 答案不能与问题完全一样
        if q.lower().rstrip("?") == a.lower():
            continue
        # 答案词汇至少 3 个与 context 重叠（宽松验证）
        if len(set(a.lower().split()) & ctx_words) < 3:
            continue
        # 补问号
        if not q.endswith("?"):
            q = q.rstrip(".") + "?"

        # ── 转 ChatML messages 格式 ──────────────────────────────
        results.append({
            "messages": [
                {"role": "system",    "content": SYSTEM_CONTENT},
                {"role": "user",      "content": q},
                {"role": "assistant", "content": a},
            ],
            "_chunk_id": chunk["id"],   # 仅用于断点续跑，训练前可删除
        })

    return results


# ── train / val 划分 ─────────────────────────────────────────────────────────
def split_and_save(
    records: list[dict],
    train_path: str,
    val_path: str,
    val_ratio: float,
    seed: int = 42,
) -> None:
    random.seed(seed)
    random.shuffle(records)

    n_val   = max(1, int(len(records) * val_ratio))
    val_set = records[:n_val]
    trn_set = records[n_val:]

    for path, dataset in [(train_path, trn_set), (val_path, val_set)]:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for row in dataset:
                # 去掉辅助字段再写出
                out = {k: v for k, v in row.items() if not k.startswith("_")}
                f.write(json.dumps(out, ensure_ascii=False) + "\n")

    print(f"[Split] train: {len(trn_set)}  val: {len(val_set)}")
    print(f"  → {train_path}")
    print(f"  → {val_path}")


# ── 主流程 ───────────────────────────────────────────────────────────────────
def main(
    train_path: str,
    val_path:   str,
    workers:    int,
    val_ratio:  float,
    max_chunks: int | None,
):
    client = get_deepseek_client()
    chunks = load_leaf_nodes()

    if max_chunks:
        chunks = chunks[:max_chunks]
        print(f"[INFO] Debug mode: using {max_chunks} chunks")

    # 断点续跑：收集已写入的 _chunk_id
    done_ids: set[str] = set()
    tmp_path = Path(train_path).with_suffix(".tmp.jsonl")
    if tmp_path.exists():
        with open(tmp_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    if "_chunk_id" in obj:
                        done_ids.add(obj["_chunk_id"])
                except json.JSONDecodeError:
                    pass
        print(f"[Resume] {len(done_ids)} chunks already done, skipping")

    pending = [c for c in chunks if c["id"] not in done_ids]
    print(f"[INFO] {len(pending)} chunks to process, {workers} worker(s)")

    all_records: list[dict] = []

    # 读取已有临时结果
    if tmp_path.exists():
        with open(tmp_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    all_records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    with open(tmp_path, "a", encoding="utf-8") as ftmp:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(generate_qa_pairs, client, chunk): chunk
                for chunk in pending
            }
            with tqdm(total=len(pending), unit="chunk") as pbar:
                for future in as_completed(futures):
                    pairs = future.result()
                    for p in pairs:
                        ftmp.write(json.dumps(p, ensure_ascii=False) + "\n")
                        all_records.append(p)
                    ftmp.flush()
                    pbar.set_postfix(qa=len(all_records))
                    pbar.update(1)

    print(f"\n[Done] {len(all_records)} QA pairs total")

    # 划分 & 写出最终文件
    split_and_save(all_records, train_path, val_path, val_ratio)

    # 清理临时文件
    tmp_path.unlink(missing_ok=True)


# ── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate ChatML QA data from DocStore via DeepSeek")
    parser.add_argument("--train",      default=DEFAULT_TRAIN,  help="Train JSONL output path")
    parser.add_argument("--val",        default=DEFAULT_VAL,    help="Val JSONL output path")
    parser.add_argument("--workers",    type=int,   default=2,  help="Parallel API workers")
    parser.add_argument("--val-ratio",  type=float, default=0.1,help="Validation split ratio")
    parser.add_argument("--max-chunks", type=int,   default=None, help="Limit chunks (debug)")
    args = parser.parse_args()

    main(
        train_path=args.train,
        val_path=args.val,
        workers=args.workers,
        val_ratio=args.val_ratio,
        max_chunks=args.max_chunks,
    )
