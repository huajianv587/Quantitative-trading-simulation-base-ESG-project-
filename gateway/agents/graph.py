# graph.py — LangGraph 主工作流状态机
# 职责：把 4 个 Agent 串联成完整的有向图，管理数据流转和条件路由
#
# 整体流程：
#   用户问题 → router → retriever → [analyst(仅ESG分析)] → verifier → 返回结果
#                                                              ↑
#                                              需要重试时打回 analyst
#
# LangGraph 核心概念：
#   State  — 贯穿整个图的共享数据结构，每个节点读取并更新它
#   Node   — 图中的处理单元，就是普通 Python 函数，接收 state 返回新 state
#   Edge   — 节点之间的连接，分固定边和条件边两种

from typing import TypedDict

try:
    from langgraph.graph import StateGraph, END    # StateGraph: 带状态的有向图; END: 终止节点
except Exception:  # pragma: no cover - optional runtime dependency
    StateGraph = None
    END = "__end__"

from gateway.agents.router_agent    import run_router
from gateway.agents.retriever_agent import run_retriever
from gateway.agents.analyst_agent   import run_analyst
from gateway.agents.verifier_agent  import run_verifier
from gateway.utils.logger import get_logger

logger = get_logger(__name__)


class _FallbackCompiledGraph:
    """LangGraph-free sequential executor for local runtime fallback."""

    def invoke(self, state: dict) -> dict:
        current_state = run_router(dict(state))
        current_state = run_retriever(current_state)

        if current_state.get("task_type") == "esg_analysis":
            current_state = run_analyst(current_state)

        while True:
            current_state = run_verifier(current_state)
            if not current_state.get("needs_retry", False):
                return current_state
            logger.info("[Graph] Fallback executor retrying analyst step")
            current_state = run_analyst(current_state)


# ── State Schema ──────────────────────────────────────────────────────────
# TypedDict 定义 state 的字段和类型，相当于整个图的「共享内存」结构
# 每个 Agent 从 state 读取输入，把输出写回 state，通过 {**state, "新字段": 值} 传递
class ESGState(TypedDict):
    question:         str    # 用户原始问题（贯穿全流程不变）
    session_id:       str    # 会话 ID（用于对话历史关联）
    task_type:        str    # router 输出：esg_analysis | factual | general
    rewritten_query:  str    # retriever 改写后的 query
    context:          str    # 检索到的 ESG 报告段落（analyst/verifier 的核查依据）
    raw_answer:       str    # retriever 直接生成的答案
    esg_scores:       dict   # analyst 的结构化 E/S/G 评分（12个指标）
    analysis_summary: str    # analyst 的 2-3 句执行摘要
    final_answer:     str    # verifier 验证后的最终答案
    confidence:       float  # verifier 置信度 0.0-1.0
    is_grounded:      bool   # 答案是否有据可查（无幻觉）
    needs_retry:      bool   # verifier 是否要求重试
    retry_count:      int    # 已重试次数（防止死循环）


# ── 路由条件函数 ──────────────────────────────────────────────────────────
# 条件边：根据 state 的当前值决定下一个节点
# 返回值必须是 add_conditional_edges 第三个参数（mapping）里的 key

def _route_after_router(state: ESGState) -> str:
    """router 之后：所有类型都先走 retriever 检索。"""
    return "retriever"


def _route_after_retriever(state: ESGState) -> str:
    """
    retriever 之后的分叉：
    - esg_analysis → analyst（需要结构化打分）
    - factual/general → verifier（直接验证 raw_answer）
    """
    if state.get("task_type") == "esg_analysis":
        return "analyst"
    return "verifier"


def _route_after_verifier(state: ESGState) -> str:
    """
    verifier 之后的分叉：
    - needs_retry=True → 打回 analyst 重新分析
    - needs_retry=False → END 结束整个图
    """
    if state.get("needs_retry", False):
        logger.info("[Graph] Verifier requested retry → analyst")
        return "analyst"
    return END    # END 是 LangGraph 的内置终止标记


# ── 构建图 ────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    if StateGraph is None:
        logger.warning("[Graph] langgraph unavailable, using sequential fallback executor.")
        return _FallbackCompiledGraph()

    graph = StateGraph(ESGState)    # 创建带 ESGState 类型约束的图

    # 注册节点：节点名（字符串） → 处理函数
    graph.add_node("router",    run_router)
    graph.add_node("retriever", run_retriever)
    graph.add_node("analyst",   run_analyst)
    graph.add_node("verifier",  run_verifier)

    # 设置入口节点（第一个被调用的节点）
    graph.set_entry_point("router")

    # 固定边：analyst → verifier（analyst 完成后必须经过 verifier 验证）
    graph.add_edge("analyst", "verifier")

    # 条件边：根据函数返回值动态决定下一个节点
    # 第三个参数是 mapping：函数返回值 → 节点名
    graph.add_conditional_edges("router",    _route_after_router,    {"retriever": "retriever"})
    graph.add_conditional_edges("retriever", _route_after_retriever, {"analyst": "analyst", "verifier": "verifier"})
    graph.add_conditional_edges("verifier",  _route_after_verifier,  {"analyst": "analyst", END: END})

    return graph.compile()    # compile() 验证图的合法性并返回可执行对象


# ── 全局单例 ──────────────────────────────────────────────────────────────
# 图的编译有一定开销，用单例避免重复编译
_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
        logger.info("[Graph] ESG agent graph compiled.")
    return _graph


# ── 统一调用入口 ──────────────────────────────────────────────────────────

def run_agent(question: str, session_id: str = "") -> dict:
    """
    主入口：传入用户问题，返回完整的 agent 执行结果。

    返回 dict 包含:
        final_answer     (str):   最终答案
        esg_scores       (dict):  E/S/G 结构化评分（esg_analysis 类型才有）
        confidence       (float): 置信度 0.0-1.0
        task_type        (str):   路由结果
        analysis_summary (str):   执行摘要

    用法:
        from gateway.agents.graph import run_agent
        result = run_agent("分析微软2023年ESG表现")
        print(result["final_answer"])
        print(result["esg_scores"])
    """
    # 初始化 state，所有字段都要有默认值（TypedDict 要求）
    initial_state: ESGState = {
        "question":         question,
        "session_id":       session_id,
        "task_type":        "",
        "rewritten_query":  "",
        "context":          "",
        "raw_answer":       "",
        "esg_scores":       {},
        "analysis_summary": "",
        "final_answer":     "",
        "confidence":       0.0,
        "is_grounded":      False,
        "needs_retry":      False,
        "retry_count":      0,
    }

    graph  = get_graph()
    result = graph.invoke(initial_state)    # invoke() 执行整个图，返回最终 state

    logger.info(
        f"[Graph] Done — task={result.get('task_type')}, "
        f"confidence={result.get('confidence', 0):.2f}"
    )
    return result
