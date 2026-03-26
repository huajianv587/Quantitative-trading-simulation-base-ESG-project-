import sys
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from llama_index.core.evaluation import (
    FaithfulnessEvaluator,
    RelevancyEvaluator,
    AnswerRelevancyEvaluator,
    BatchEvalRunner,
)
from llama_index.llms.openai import OpenAI
from llama_index.core.query_engine import RetrieverQueryEngine

# 用 GPT-4o-mini 做评判，成本低且足够准确
_JUDGE_LLM = OpenAI(model="gpt-4o-mini", temperature=0)

# ESG 场景默认测试问题集
DEFAULT_QUESTIONS = [
    "该公司的环境评分（Environmental Score）是多少？",
    "该公司在碳排放管理上采取了哪些措施？",
    "该公司的社会责任（Social）评分如何？",
    "董事会中女性成员的比例是多少？",
    "该公司是否有明确的净零排放承诺，目标年份是哪年？",
    "该公司的 ESG 综合评级相比同行处于什么水平？",
    "供应链中的劳工标准合规情况如何？",
    "该公司在水资源管理方面的具体指标是什么？",
]


# ---------------------------------------------------------------------------
# 单次评估
# ---------------------------------------------------------------------------

def evaluate(
    query_engine: RetrieverQueryEngine,
    questions: list[str] | None = None,
) -> list[dict]:
    """
    对 query_engine 跑一批问题，返回每条的三项评分：
      - Faithfulness    回答是否忠实于检索到的文本（抗幻觉）
      - Relevancy       检索到的节点是否与问题相关
      - AnswerRelevancy 回答内容是否切题

    questions — 不传则使用 DEFAULT_QUESTIONS
    """
    questions = questions or DEFAULT_QUESTIONS

    faithfulness_eval   = FaithfulnessEvaluator(llm=_JUDGE_LLM)
    relevancy_eval      = RelevancyEvaluator(llm=_JUDGE_LLM)
    answer_relevancy_eval = AnswerRelevancyEvaluator(llm=_JUDGE_LLM)

    runner = BatchEvalRunner(
        evaluators={
            "faithfulness":     faithfulness_eval,
            "relevancy":        relevancy_eval,
            "answer_relevancy": answer_relevancy_eval,
        },
        workers=4,
        show_progress=True,
    )

    eval_results = runner.evaluate_queries(
        query_engine=query_engine,
        queries=questions,
    )

    results = []
    for i, q in enumerate(questions):
        faithfulness     = eval_results["faithfulness"][i]
        relevancy        = eval_results["relevancy"][i]
        answer_relevancy = eval_results["answer_relevancy"][i]

        results.append({
            "question":         q,
            "answer":           faithfulness.response or "",  # BatchEvalRunner 已存好答案
            "faithfulness":     "YES" if faithfulness.passing     else "NO",
            "relevancy":        "YES" if relevancy.passing        else "NO",
            "answer_relevancy": "YES" if answer_relevancy.passing else "NO",
        })

    return results


# ---------------------------------------------------------------------------
# 汇总报告
# ---------------------------------------------------------------------------

def report(results: list[dict]) -> dict:
    """
    汇总评估结果，输出通过率。
    """
    total = len(results)
    faith_pass  = sum(1 for r in results if r["faithfulness"]     == "YES")
    relev_pass  = sum(1 for r in results if r["relevancy"]        == "YES")
    answer_pass = sum(1 for r in results if r["answer_relevancy"] == "YES")

    summary = {
        "total_questions":     total,
        "faithfulness_pass":   f"{faith_pass}/{total}  ({faith_pass/total:.0%})",
        "relevancy_pass":      f"{relev_pass}/{total}  ({relev_pass/total:.0%})",
        "answer_relevancy_pass": f"{answer_pass}/{total}  ({answer_pass/total:.0%})",
        "details":             results,
    }
    return summary


# ---------------------------------------------------------------------------
# 保存报告到文件
# ---------------------------------------------------------------------------

def save_report(summary: dict, output_path: str | None = None) -> str:
    path = Path(output_path) if output_path else (
        Path(__file__).resolve().parents[2] / "evaluation" / "rag_eval_report.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"Report saved → {path}")
    return str(path)
