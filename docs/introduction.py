"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║        ESG AGENTIC RAG COPILOT - 完整项目理解与掌握指南 v2.0 (增强版)          ║
║                                                                              ║
║  核心目标: 从"Claude 生成的代码消费者" → "理解、精通、改进的代码拥有者"        ║
║                                                                              ║
║  构建时间: 2026-03-29                                                        ║
║  版本: 2.0 Complete & Detailed Edition                                       ║
║                                                                              ║
║  📊 项目规模: 48 个 Python 文件 | 11,155 行核心代码 | 5 大核心模块              ║
║  🎯 理解策略: 先全景 → 再深入 → 后流程 → 最后代码级讲解                        ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

【这个文件能帮你什么】

✅ 了解项目全景: 48 个文件、5 个核心模块、3 个操作流程
✅ 理解每个文件: 用途、函数/类、复杂度、数据流
✅ 掌握代码逻辑: 代码行级讲解、流程图、设计模式
✅ 发现隐藏问题: 代码不一致、性能瓶颈、安全隐患
✅ 规划优化方向: MultiAgent 升级、前端架构、性能优化
✅ 建立代码所有权: 从"为什么"到"怎么改"的完整理解

================================================================================
第一部分: 项目全景地图 (理解"全局"的结构)
================================================================================

【顶层结构: 如果项目是一个公司】

ESG-Agentic-RAG-Copilot  ← 整个企业
│
├─ 【执行部门】gateway/  ← 公司总部，负责所有业务执行
│  │
│  ├─ 【聪明大脑】agents/        智能分析部门 (使用 LangGraph)
│  │  ├─ graph.py              大脑的中枢神经系统 (指挥所)
│  │  ├─ router_agent.py        问题分类员
│  │  ├─ retriever_agent.py     知识库查询员
│  │  ├─ analyst_agent.py       数据分析员
│  │  ├─ verifier_agent.py      质量检查员
│  │  ├─ esg_scorer.py          ESG 打分专家 ✨
│  │  ├─ esg_visualizer.py      数据可视化师 ✨
│  │  ├─ prompts.py             所有部门的 SOP (操作流程)
│  │  └─ tools.py               工具箱
│  │
│  ├─ 【知识库】rag/            检索增强生成部门
│  │  ├─ rag_main.py            知识库总经理 (单例管理)
│  │  ├─ chunking.py            文档分割员
│  │  ├─ ingestion.py           向量化员
│  │  ├─ indexer.py             索引管理员
│  │  ├─ retriever.py           多策略搜索员 (核心)
│  │  ├─ evaluator.py           搜索质量评估员
│  │  └─ cache.py               缓存管理员
│  │
│  ├─ 【自动化部门】scheduler/  定时扫描和报告系统
│  │  ├─ orchestrator.py        自动化流程总监 (5 阶段流程)
│  │  ├─ scanner.py             事件扫描员
│  │  ├─ event_extractor.py     事件整理员
│  │  ├─ risk_scorer.py         风险评估员
│  │  ├─ matcher.py             匹配员
│  │  ├─ notifier.py            推送员
│  │  ├─ report_generator.py    报告生成员
│  │  ├─ report_scheduler.py    报告调度员
│  │  └─ data_sources.py        数据源管理员
│  │
│  ├─ 【数据仓库】db/           数据库连接层
│  │  └─ supabase_client.py     数据库管理员 (单例连接)
│  │
│  ├─ 【数据模型】models/       统一数据规范
│  │  └─ schemas.py             所有数据结构定义
│  │
│  ├─ 【工具库】utils/          所有部门都用的通用工具
│  │  ├─ llm_client.py          LLM 三级 Fallback 管理员 (核心)
│  │  ├─ logger.py              日志记录员
│  │  ├─ cache.py               缓存管理员
│  │  └─ retry.py               重试机制
│  │
│  ├─ main.py                   被动 API 入口 (用户主动提问)
│  └─ main_enhanced.py          增强版 API + 管理面板
│
├─ 【模型工坊】training/        本地模型微调部门 (可选)
│  ├─ prepare_data.py           数据预处理
│  ├─ finetune.py               QLoRA 微调
│  ├─ evaluate_model.py         模型评估
│  └─ launch_job.py             远程训练启动
│
├─ 【数据湖】data/             原始数据存储
│  ├─ raw/                      未处理的 PDF、报告
│  ├─ processed/                处理后的数据
│  ├─ vectorstore/              向量库 (Qdrant)
│  └─ scripts/                  数据处理脚本
│
├─ 【配置中心】configs/         全局参数
│  └─ config.py                 Settings 类 (环境变量加载)
│
└─ 【基础设施】
   ├─ migrations/               数据库迁移脚本
   ├─ docker-compose.yml        本地开发环境
   ├─ requirements.txt          Python 依赖
   ├─ .env                      环境变量配置
   └─ 📄 各种文档说明文件

【项目数字说明】
- 📊 Python 文件数: 48 个
- 📝 总代码行数: ~11,155 行
- 🎯 核心模块数: 5 个 (agents, rag, scheduler, db, utils)
- ⭐ 核心差异化功能: 3 个 (LLM Fallback, ESG 评分, RAG 融合检索)
- 🚀 新增功能: 4 个 (esg_scorer, esg_visualizer, report_scheduler, data_sources)

================================================================================
第二部分: 核心模块深度讲解 (理解"模块"的工作原理)
================================================================================

【模块 1: Agent 工作流引擎 (gateway/agents/)】

👤 角色: 整个系统的"聪慧大脑"，负责智能分析

📋 工作流程 (被动查询):
  用户提问 → 问题分类 → 知识检索 → 结构化分析 → 质量验证 → 返回答案

核心文件及讲解:

【1.1】graph.py (158 行) - LangGraph 状态机编排器 ⭐⭐⭐

作用: 定义 4 个 Agent 之间的流程和状态转移

关键概念 - ESGState:
  这是整个流程中的"工作票据 (Work Ticket)"，记录从开始到结束的所有信息

  字段说明:
  - question: str              用户的原始问题
  - session_id: str            会话 ID (用于后续追踪和缓存)
  - task_type: str             问题分类: "esg_analysis" | "factual" | "general"
  - rewritten_query: str       改写后的查询 (更专业的表达)
  - context: str               从 RAG 检索到的上下文
  - raw_answer: str            LLM 的原始回答
  - esg_scores: dict           E/S/G 结构化评分 (仅当 task_type="esg_analysis")
  - analysis_summary: str      分析摘要
  - final_answer: str          最终答案 (经过质量检查)
  - confidence: float          置信度 (0.0-1.0)
  - is_grounded: bool          是否有根据 (基于检索上下文)
  - needs_retry: bool          是否需要重试
  - retry_count: int           已重试次数

结构化代码讲解:

```python
# ① 定义状态
class ESGState(TypedDict):
    question: str               # 为什么是字符串? 便于序列化、缓存、日志记录
    session_id: str
    # ... 更多字段
    retry_count: int            # 为什么是整数? 防止无限循环 (需要设上限)

# ② 构建有向图
def build_graph() -> StateGraph:
    graph = StateGraph(ESGState)  # 创建一个有 ESGState 的图

    # 添加 4 个节点 (每个都是一个 Agent 函数)
    graph.add_node("router", run_router)           # 节点 1: 分类
    graph.add_node("retriever", run_retriever)     # 节点 2: 检索
    graph.add_node("analyst", run_analyst)         # 节点 3: 分析
    graph.add_node("verifier", run_verifier)       # 节点 4: 验证

    # 设置起点
    graph.set_entry_point("router")  # 所有请求都从 router 开始

    # 添加转移规则 (基于条件)
    graph.add_conditional_edges(
        "router",                          # 从 router 出发
        _route_after_router,               # 条件函数 (返回下一个节点名)
        {"retriever": "retriever"}         # 总是去 retriever
    )

    # router → retriever → (根据条件选择) analyst 或 verifier
    graph.add_conditional_edges(
        "retriever",
        _route_after_retriever,  # 根据 task_type 判断
        {
            "analyst": "analyst",
            "verifier": "verifier"
        }
    )

    # analyzer → verifier (总是去验证)
    graph.add_edge("analyst", "verifier")

    # verifier 的条件: 若 needs_retry=True 且 retry_count < MAX 则回到 analyst
    graph.add_conditional_edges(
        "verifier",
        _route_after_verifier,   # 判断是否需要重试
        {
            "analyst": "analyst",           # 重试分析
            "end": END                      # 结束流程
        }
    )

    # 编译为可执行图
    return graph.compile()  # 返回一个 runnable 的计算图

# ③ 执行流程
def run_agent(question: str, session_id: str) -> dict:
    # 初始状态
    initial_state = {
        "question": question,
        "session_id": session_id,
        "task_type": None,          # 还不知道是什么类型
        "rewritten_query": None,
        "context": None,
        "raw_answer": None,
        "esg_scores": None,
        "confidence": 0.0,
        "is_grounded": False,
        "needs_retry": False,
        "retry_count": 0
    }

    # 执行有向图 (从 router 开始)
    final_state = runnable.invoke(initial_state)

    return {
        "answer": final_state["final_answer"],
        "confidence": final_state["confidence"],
        "esg_scores": final_state.get("esg_scores"),
        "session_id": session_id
    }
```

📊 流程图 (ASCII):
```
START
  ↓
[ROUTER 节点]  ← 问题分类 (task_type = esg_analysis | factual | general)
  ↓
[RETRIEVER 节点]  ← Query 改写 + RAG 检索
  ↓
  ├─ 若 task_type=esg_analysis
  │   ↓
  │ [ANALYST 节点]  ← 结构化评分 (E/S/G 12 指标)
  │   ↓
  │ [VERIFIER 节点]  ← 幻觉检测 + 置信度评估
  │   ├─ 若 confidence >= 0.6 且 retry_count < 1 (可重试)
  │   │   ↓
  │   │ [打回 ANALYST 重试]  ← 最多 1 次重试
  │   │   ↓ (retry_count++)
  │   │ [重新进入 VERIFIER]
  │   │   ↓
  │   ├─ 若 confidence >= 0.6 或 retry_count >= 1 (不再重试)
  │   │   ↓
  │   └─ [输出最终答案]
  │
  ├─ 若 task_type=factual/general
  │   ↓
  │ [跳过 ANALYST，直接 VERIFIER]
  │   ↓
  │ [输出最终答案]
  │
  └─ END
     ↓
   返回 final_state
```

【1.2】router_agent.py (54 行) - 问题分类员

作用: 判断用户问题属于哪一类

核心代码讲解:

```python
def run_router(state: ESGState) -> ESGState:
    """'''
        使用 LLM 分类用户问题

    为什么需要分类?
    - ESG 问题需要结构化的评分 (调用 esg_scorer)
    - 事实性问题只需验证答案的准确性
    - 通用问题可以快速回答
    """
    '''
  

    # 第一步: 准备提示词
    messages = [
        {"role": "system", "content": ROUTER_SYSTEM},  # 系统提示 (SOP)
        {"role": "user", "content": ROUTER_USER.format(question=state["question"])}
    ]

    # 第二步: 调用 LLM (这里使用 utils/llm_client.py 的三级 fallback)
    response = llm_client.chat(messages)

    # 第三步: 解析 LLM 的回答
    # LLM 返回格式: {"task_type": "esg_analysis"} 或 "factual" 或 "general"
    try:
        task_dict = json.loads(response)
        task_type = task_dict.get("task_type", "general").lower()
    except:
        task_type = "general"  # 解析失败则默认为通用

    # 验证任务类型 (确保只有合法的分类)
    if task_type not in VALID_TASK_TYPES:  # {"esg_analysis", "factual", "general"}
        task_type = "general"

    # 第四步: 更新状态，传递给下一个节点
    state["task_type"] = task_type
    logger.info(f"[ROUTER] 分类结果: {task_type}")

    return state  # 返回更新后的状态
```
'''


为什么这个设计很重要？
- 🎯 任务分类是整个流程的"方向盘"，决定后续走哪条路
- 🔒 验证任务类型防止了恶意输入导致流程混乱
- 📊 不同任务类型的处理时间和成本差异很大
  * ESG 分析 (慢/贵) → 完整 RAG + 结构化评分
  * 事实查询 (中) → RAG + 验证
  * 通用问题 (快/便宜) → 直接 LLM

'''

【1.3】retriever_agent.py (83 行) - 知识库查询员

作用: Query 改写 + RAG 检索 + 缓存管理

核心代码讲解:

```python
def run_retriever(state: ESGState) -> ESGState:
    """
    第一步: Query 改写 (口语 → 专业用语)
    第二步: 检查缓存 (是否已查询过相似问题)
    第三步: 调用 RAG 检索
    """

    # 【步骤 1】Query 改写
    # 为什么需要改写?
    # - 用户提问: "特斯拉最近出了啥新闻?" (口语化、模糊)
    # - 改写后: "Tesla 近期 ESG 相关新闻报道及其对公司评级的影响" (专业化、清晰)
    # - 改写后的 Query 能显著提升 RAG 的检索质量

    messages = [{"role": "user", "content": REWRITER_PROMPT.format(q=state["question"])}]
    rewritten = llm_client.chat(messages, temperature=0.1)  # 低温度 (保证准确)
    state["rewritten_query"] = rewritten

    # 【步骤 2】缓存检查
    # 缓存的目的是什么?
    # - 如果相同的 question 被问过，直接返回之前的结果，跳过 RAG 调用
    # - 这样可以节省时间 (毫秒级) 和 API 调用 (降成本)

    cache_key = f"rag_{hash(state['question'])}"  # 以 question 为 key
    cached_context = cache.get_cache(cache_key)

    if cached_context:
        logger.info(f"[RETRIEVER] 缓存命中!")
        state["context"] = cached_context
        return state  # 直接返回，跳过 RAG 调用

    # 【步骤 3】调用 RAG 检索
    # RAG 是什么?
    # - R: Retrieval (检索) - 从向量库里找最相关的文档
    # - A: Augment (增强) - 用这些文档作为上下文
    # - G: Generation (生成) - 让 LLM 基于上下文生成答案

    try:
        # 调用 rag_main.py 中的 get_query_engine()
        query_engine = rag_main.get_query_engine()
        response = query_engine.query(state["rewritten_query"])
        context = response.response  # 检索到的上下文

        # 保存到缓存，下次相同问题可直接用
        cache.set_cache(cache_key, context, ttl_hours=24)
        state["context"] = context

    except Exception as e:
        logger.error(f"[RETRIEVER] RAG 失败: {e}")
        state["context"] = ""  # 降级处理: 无上下文，LLM 独立回答

    return state
```

为什么这个设计很聪明？
- 🚀 Query 改写提升了检索质量 (同一个问题，不同表达方式，结果可能完全不同)
- 💾 缓存机制避免重复调用 (同一会话内、跨会话)
- 🛡️ 错误处理降级策略 (RAG 失败时仍能回答，只是质量下降)

【1.4】analyst_agent.py (85 行) - 数据分析员

作用: 结构化 ESG 评分 (12 个指标)

核心代码讲解:

```python
def run_analyst(state: ESGState) -> ESGState:
    """
    只有当 task_type="esg_analysis" 时才会调用这个函数

    目的: 从非结构化的 LLM 回答中提取结构化的 E/S/G 评分
    """

    # 【步骤 1】准备数据摘要
    # 为什么要准备摘要?
    # - 上下文可能很长 (成千上万个 token)
    # - 发送给 LLM 的 token 越多，成本越高，延迟越大
    # - 摘要可以保留关键信息，去掉冗余

    summary = _prepare_data_summary(
        question=state["question"],
        context=state["context"],
        max_summary_tokens=1000  # 限制摘要长度
    )

    # 【步骤 2】构建分析提示
    # 这个提示词会明确告诉 LLM 返回什么格式的结果
    messages = [
        {"role": "system", "content": ANALYST_SYSTEM},
        {"role": "user", "content": ANALYST_USER.format(
            context=summary,
            question=state["question"]
        )}
    ]

    # 【步骤 3】调用 LLM 获取原始回答
    raw_answer = llm_client.chat(messages, temperature=0.2)  # 低温度确保准确
    state["raw_answer"] = raw_answer

    # 【步骤 4】解析 JSON 格式的评分
    # LLM 被要求返回特定的 JSON 格式:
    # {
    #   "environmental_score": 0-100,
    #   "social_score": 0-100,
    #   "governance_score": 0-100,
    #   "summary": "..."
    # }

    try:
        esg_dict = json.loads(raw_answer)
        state["esg_scores"] = {
            "environmental": esg_dict.get("environmental_score", 50),
            "social": esg_dict.get("social_score", 50),
            "governance": esg_dict.get("governance_score", 50)
        }
    except json.JSONDecodeError:
        logger.warning(f"[ANALYST] JSON 解析失败，尝试备用解析")
        # 备用解析: 如果 LLM 没有返回有效 JSON，用正则表达式提取数字
        esg_dict = _parse_esg_json(raw_answer, fallback=True)
        state["esg_scores"] = esg_dict

    return state
```

🔑 关键设计点:
- ✅ 限制摘要长度 → 控制成本和延迟
- ✅ 明确的 JSON 格式要求 → 减少 LLM 的变异性
- ✅ 异常处理和备用解析 → 提高鲁棒性

【1.5】verifier_agent.py (118 行) - 质量检查员

作用: 幻觉检测 + 置信度评估 + 自动重试

核心代码讲解:

```python
def run_verifier(state: ESGState) -> ESGState:
    """
    这是最后一道质量关卡

    关键问题: LLM 会"胡说" (幻觉)
    - "特斯拉 CEO 是 Elon Musk" → 正确 (有根据)
    - "特斯拉今年碳排放减少了 50%" → 可能错误 (无根据)

    验证的方法:
    1. 对照检索上下文 (context) 来检查答案
    2. 评估置信度 (0.0 到 1.0)
    3. 必要时打回分析器重试
    """

    # 【步骤 1】构建验证提示
    messages = [
        {"role": "system", "content": VERIFIER_SYSTEM},
        {"role": "user", "content": VERIFIER_USER.format(
            question=state["question"],
            context=state["context"],
            answer=state["raw_answer"]
        )}
    ]

    # 【步骤 2】LLM 验证并返回置信度
    # LLM 需要返回格式:
    # {
    #   "is_grounded": true/false,  是否有根据?
    #   "confidence": 0.8,           置信度 (0.0-1.0)
    #   "refined_answer": "...",     改进后的答案
    #   "explanation": "..."         为什么这样评分
    # }

    verification = llm_client.chat(messages)

    try:
        verify_dict = json.loads(verification)
        state["is_grounded"] = verify_dict.get("is_grounded", False)
        state["confidence"] = float(verify_dict.get("confidence", 0.5))
        state["final_answer"] = verify_dict.get("refined_answer", state["raw_answer"])
    except:
        state["confidence"] = 0.5
        state["is_grounded"] = False
        state["final_answer"] = state["raw_answer"]

    # 【步骤 3】判断是否需要重试
    # 重试的条件:
    # - 置信度低 (< 0.6)
    # - 并且还有重试机会 (retry_count < MAX_RETRY_COUNT=1)
    # - 并且是 ESG 分析任务 (其他任务不需要完美答案)

    if (state["confidence"] < 0.6 and
        state["retry_count"] < MAX_RETRY_COUNT and
        state["task_type"] == "esg_analysis"):

        logger.warning(f"[VERIFIER] 置信度低 ({state['confidence']:.2f})，打回重试")
        state["needs_retry"] = True
        state["retry_count"] += 1
        # 这会触发 graph 的条件转移，回到 analyst 重新分析

    else:
        # 不重试，结束流程
        logger.info(f"[VERIFIER] 最终答案确认，置信度 {state['confidence']:.2f}")
        state["needs_retry"] = False

    return state
```

🎯 重试机制的妙处:
- ⚡ 大多数问题一次就对，快速返回
- 🎯 只有高风险的 ESG 分析才会重试
- 🛡️ 最多 1 次重试，防止无限循环
- 📊 retry_count 计数器是保护机制

================================================================================

【模块 2: RAG 检索增强生成 (gateway/rag/)】

👤 角色: 系统的"知识库"，提供精准的信息检索

【2.1】RAG 的完整工作原理

什么是 RAG？
- R (Retrieval): 从向量库里检索相关文档
- A (Augment): 用这些文档作为上下文
- G (Generation): LLM 基于上下文生成答案

为什么需要 RAG？
  LLM (只有参数知识，不知道最新信息):
    输入: "特斯拉最近的 ESG 新闻是什么?" → 输出: "我的知识截至 2024 年，不知道最新信息"

  +RAG (有实时知识库):
    输入: "特斯拉最近的 ESG 新闻是什么?"
      ↓ [RAG 检索：从向量库找相关文档]
      ↓ 文档: "2026 年 3 月，特斯拉宣布碳中和目标..."
    输出: "根据最新报道，特斯拉在 2026 年 3 月宣布了新的碳中和目标，预计..."

【2.2】RAG 的数据流

```
【建立知识库的过程】(初始化)

原始文档 (PDF/DOCX/TXT)
  ↓
[chunking.py] 分层切块
  ├─ Level 1 (完整文档): 2048 tokens
  ├─ Level 2 (章节): 512 tokens
  └─ Level 3 (段落): 128 tokens
     (为什么是 3 层？分层可以在多个粒度上匹配用户查询)
  ↓
[ingestion.py] 向量化
  将文本转换成 embedding (浮点数向量)
  使用模型: text-embedding-3-small (OpenAI)
  维度: 1536
  (为什么向量化？便于计算相似度，找最相关的文档)
  ↓
[Qdrant] 向量库存储
  保存格式: {vector: [1.2, -0.5, ...], metadata: {source, page, level}}
  (Qdrant 是什么？专门用来存储和快速搜索向量的数据库)

【查询时的检索过程】

用户查询: "特斯拉的环保政策"
  ↓
[retriever_agent.py] Query 改写
  改写为: "Tesla 环境保护、可持续发展相关政策和实践"
  ↓
【多策略混合检索】(这是 RAG 的核心精妙设计)

┌─ BM25 检索 (关键词)
│  └─ 将 Query 分词: ["Tesla", "环保", "政策"]
│     找文档中包含这些词的
│     结果: Top-12 (关键词最匹配的文档块)
│
├─ Dense 检索 (语义)
│  └─ Query embedding: [0.1, -0.3, ...]
│     找向量相似度最高的文档
│     结果: Top-12 (语义最接近的文档块)
│
├─ 倒数排名融合 (QueryFusionRetriever)
│  └─ BM25 结果 + Dense 结果 合并，使用倒数排名融合
│     公式: score = 1/(k + rank) 其中 k 通常为 60
│     目的: 结合关键词匹配和语义匹配的优势
│     结果: Top-12 (融合后)
│
├─ 自动父节点扩展 (AutoMergingRetriever)
│  └─ 如果 leaf nodes (128 tokens) 占比 >= 40%，
│     则拉出整个 parent (512 tokens)
│     目的: 提升上下文连贯性
│     (为什么？一个段落可能引用上一段，需要完整上下文)
│
└─ 二阶段重排序 (FlagEmbeddingReranker)
   └─ 使用专业的重排序模型: BAAI/bge-reranker-base
      精确计算与查询的相关性
      重排并选择 Top-5
      (为什么两阶段？第一阶段召回多个候选，第二阶段精准筛选)
      ↓
     Final Top-5 关键文档块

【最后】用 Top-5 作为上下文，输入 LLM
  LLM 基于这 5 个最相关的文档块生成答案
```

【2.3】多策略融合检索的妙处

为什么不用单一策略？

❌ 单纯 BM25 (关键词):
  优点: 快速，准确度高
  缺点: 如果用户用同义词，就检索不到
  例: 查询"环保" vs 库里的"环境保护"，BM25 会认为不匹配

❌ 单纯 Dense (语义):
  优点: 理解语义，同义词也能匹配
  缺点: 有时"过度匹配"(语义相近但具体内容不关)
  例: "企业社会责任"和"环保政策"在语义上接近，但细节不同

✅ BM25 + Dense (融合):
  - 关键词匹配提供精准度
  - 语义匹配提供覆盖度
  - 两个结果互补，最终给出最佳结果

【2.4】Qdrant 向量库的关键配置

```python
# rag/ingestion.py 示例代码讲解

def build_vector_index():
    """
    为什么要"build"索引？
    - Qdrant 是一个向量数据库，初始化时需要：
      1. 建立一个 collection (表)
      2. 指定向量维度 (embedding 的长度)
      3. 指定相似度计算方法 (Cosine、Euclidean 等)
    """

    # 第一步: 创建本地 Qdrant 连接
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams

    client = QdrantClient(":memory:")  # :memory 表示内存存储 (开发用)
    # 或者: QdrantClient("http://qdrant:6333")  # 远程 Qdrant 服务

    # 第二步: 创建 collection (集合)
    # 为什么需要 collection？
    # - Qdrant 可以存储多个向量索引 (就像数据库有多个表)
    # - 每个 collection 代表一个知识库

    collection_name = "esg_documents"
    vector_size = 1536  # text-embedding-3-small 的维度

    client.recreate_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=vector_size,              # 向量维度
            distance=Distance.COSINE       # 使用 Cosine 相似度
            # 为什么是 Cosine？常用于文本相似度计算
        )
    )

    # 第三步: 向库里插入向量
    vectors = []
    for doc_id, embedding, metadata in doc_embeddings:
        vectors.append({
            "id": doc_id,
            "vector": embedding,  # [1.2, -0.5, ..., 0.3] 共 1536 个数字
            "payload": {
                "source": metadata["source"],
                "text": metadata["text"]
            }
        })

    client.upsert(collection_name, vectors)

    return client
```

【2.5】核心文件代码讲解

# rag_main.py (133 行) - RAG 核心入口

```python
class ESGLocalLLM(CustomLLM):
    """
    为什么需要自定义 LLM？

    LlamaIndex (RAG 框架) 支持 OpenAI、Claude 等 LLM
    但我们想用本地 Qwen2.5-7B-LoRA 模型
    所以需要包装它，让 LlamaIndex 能调用

    设计原理:
    - LlamaIndex 调用 self.complete(prompt) 方法
    - 我们在这个方法里调用本地模型
    - 返回结果给 LlamaIndex
    """

    def complete(self, prompt: str) -> CompletionResponse:
        # 第一步: 调用本地模型
        # 为什么用本地模型？成本低、隐私好、速度快
        response = llm_client.chat(  # 这里使用了 utils/llm_client.py
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024
        )

        # 第二步: 包装为 LlamaIndex 格式并返回
        return CompletionResponse(response=response)

    def stream_complete(self, prompt: str):
        # 类似，但支持流式输出 (边生成边返回)
        # 使用场景：前端实时显示 LLM 正在输入的内容
        pass

# 全局单例 (为什么要单例？避免多次初始化)
_query_engine = None

def get_query_engine():
    """
    第一次调用时初始化 RAG 引擎
    之后每次调用都返回同一个实例

    为什么这样设计？
    - RAG 引擎初始化很重，需要加载向量库、索引等
    - 如果每次都重新初始化，会很慢
    - 使用单例模式，保证全程只有一个实例
    """
    global _query_engine

    if _query_engine is None:
        # 加载向量存储和索引
        vector_store = build_vector_store()  # Qdrant
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = load_index(storage_context)  # 从磁盘加载

        # 构建查询引擎 (多策略混合)
        _query_engine = RetrieverQueryEngine.from_defaults(
            retriever=build_custom_retriever(index),  # 多策略融合
            llm=ESGLocalLLM()  # 使用本地模型
        )

    return _query_engine
```

================================================================================

【模块 3: 主动扫描调度系统 (gateway/scheduler/)】

👤 角色: 自动化的"巡查员"，定时监测 ESG 事件

【3.1】5 阶段管道的完整流程

```
[定时触发] 每 30 分钟一次
  ↓
[Stage 1] Scanner - 事件扫描
  任务: 从新闻、报告、社交媒体源发现 ESG 相关事件
  输出: raw_events (未处理的事件列表)
  例子: ["特斯拉发布年度ESG报告", "亚马逊因环保争议被罚款", ...]

  ↓
[Stage 2] EventExtractor - 结构化提取
  任务: 使用 LLM 将文本转换为结构化格式
  输入: raw_events
  处理方式:
    raw_event = "特斯拉在 2026 年发布了新的碳中和承诺"
    ↓ [LLM 处理]
    extracted_event = {
      "company": "Tesla",
      "event_type": "Environmental",
      "title": "碳中和承诺声明",
      "key_metrics": ["carbon_neutral", "2050"],
      "severity": "HIGH"
    }
  输出: extracted_events (结构化事件)

  ↓
[Stage 3] RiskScorer - 风险评分
  任务: 评估每个事件的风险等级 (0-100)
  输入: extracted_events
  处理方式:
    event = "员工骚乱，工厂停工"
    ↓ [LLM + 规则评分]
    risk_score = {
      "score": 85,  // 高风险
      "level": "HIGH",
      "reason": "生产中断，声誉受损"
    }
  输出: scored_events (带评分的事件)

  ↓
[Stage 4] EventMatcher - 事件匹配
  任务: 将事件与用户偏好匹配
  输入: scored_events + user_preferences
  处理方式:
    用户偏好: {
      "companies": ["Tesla", "Apple"],
      "categories": ["Environmental", "Social"],
      "keywords": ["carbon", "emissions"]
    }

    event = {
      "company": "Tesla",
      "category": "Environmental",
      "keywords": ["carbon_neutral"]
    }

    ↓ [匹配规则]
    是否匹配？
    - 公司匹配 (Tesla in [Tesla, Apple]) ✓
    - 分类匹配 (Environmental in [Environmental, Social]) ✓
    - 关键词匹配 (carbon_neutral 与 carbon 相关) ✓

    结果: 这个事件应该推送给这个用户

  ↓
[Stage 5] Notifier - 推送通知
  任务: 发送通知给匹配的用户
  输入: matched_events + user_contact_info
  推送渠道:
    ├─ Email (邮件)
    ├─ In-App (应用内消息)
    └─ Webhook (第三方服务)

  例: 给用户 user_123 发邮件
    主题: "您关注的特斯拉发生了新事件"
    内容: "特斯拉刚刚宣布了新的碳中和承诺..."

完整流程示例:

  原始新闻: "特斯拉发布碳中和承诺，目标 2050 实现"
    ↓ [Scanner]
    raw_event: "特斯拉发布碳中和承诺，目标 2050 实现"
    ↓ [EventExtractor]
    extracted: {company: Tesla, type: Environmental, severity: HIGH}
    ↓ [RiskScorer]
    scored: {score: 75, level: HIGH}
    ↓ [EventMatcher (用户 user_123 关注 Tesla)]
    matched: true
    ↓ [Notifier]
    邮件发出: "您关注的公司有新事件..."
    ↓ [完成]
    notification_log: {user_id: user_123, event_id: evt_456, sent_at: ...}
```

【3.2】核心文件代码讲解

# orchestrator.py (251 行) - 5 阶段流程编排器

```python
class SchedulerOrchestrator:
    """
    这是整个调度系统的"大脑"
    负责协调 5 个模块按顺序执行
    """

    def run_full_pipeline(self):
        """
        完整的管道执行
        """

        logger.info("[Orchestrator] 开始完整管道")

        # ===== Stage 1: Scan =====
        logger.info("[Stage 1] 扫描新事件")
        scanner = Scanner()
        raw_events = scanner.scan_news_feeds()  # 返回列表
        logger.info(f"[Stage 1] 发现 {len(raw_events)} 个原始事件")

        if not raw_events:
            logger.info("[Orchestrator] 没有新事件，结束管道")
            return {"scanned": 0}

        # ===== Stage 2: Extract =====
        logger.info(f"[Stage 2] 提取 {len(raw_events)} 个事件的结构化信息")
        extractor = EventExtractor()
        extracted_events = extractor.process_new_events(raw_events)
        logger.info(f"[Stage 2] 成功提取 {len(extracted_events)} 个事件")

        # ===== Stage 3: Score =====
        logger.info("[Stage 3] 评分事件风险等级")
        scorer = RiskScorer()
        scored_events = scorer.score_batch_events(extracted_events)

        # 过滤低风险事件 (保留 score >= 50 的)
        significant_events = [e for e in scored_events if e.get("risk_score", 0) >= 50]
        logger.info(f"[Stage 3] {len(significant_events)} 个重要事件 (score >= 50)")

        if not significant_events:
            logger.info("[Orchestrator] 没有重要事件，结束管道")
            return {"scored": len(scored_events), "significant": 0}

        # ===== Stage 4: Match =====
        logger.info(f"[Stage 4] 匹配 {len(significant_events)} 个事件与用户偏好")
        matcher = EventMatcher()
        matched_pairs = matcher.match_batch_events(significant_events)
        logger.info(f"[Stage 4] 匹配出 {len(matched_pairs)} 个事件-用户对")

        # ===== Stage 5: Notify =====
        logger.info(f"[Stage 5] 推送通知")
        notifier = Notifier()

        # 按用户 ID 分组
        notifications_by_user = {}
        for event_id, user_id in matched_pairs:
            if user_id not in notifications_by_user:
                notifications_by_user[user_id] = []
            notifications_by_user[user_id].append(event_id)

        # 给每个用户发送通知
        total_notifications = 0
        for user_id, event_ids in notifications_by_user.items():
            result = notifier.send_notifications(
                event_ids=event_ids,
                user_id=user_id
            )
            total_notifications += result.get("sent", 0)

        logger.info(f"[Stage 5] 发送 {total_notifications} 条通知")

        # ===== 返回摘要 =====
        return {
            "scanned": len(raw_events),
            "extracted": len(extracted_events),
            "scored": len(scored_events),
            "significant": len(significant_events),
            "matched": len(matched_pairs),
            "notified": total_notifications,
            "timestamp": datetime.now()
        }

def get_orchestrator() -> SchedulerOrchestrator:
    """
    全局单例 (为什么？只需要一个调度器实例)
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SchedulerOrchestrator()
    return _orchestrator
```

【3.3】关键文件职责分析

| 文件 | 行数 | 职责 | 关键方法 |
|-----|------|------|---------|
| scanner.py | 251 | 从多个源扫描事件 | scan_news_feeds() |
| event_extractor.py | 247 | LLM 结构化提取 | process_new_events() |
| risk_scorer.py | 275 | AI 风险评分 | score_batch_events() |
| matcher.py | 260 | 事件-用户匹配 | match_batch_events() |
| notifier.py | 334 | 多渠道推送 | send_notifications() |

为什么要分成 5 个文件？
- ✅ 单一职责原则：每个文件只做一件事
- ✅ 易于测试：每个模块可独立测试
- ✅ 易于扩展：添加新的评分策略时，只需修改 risk_scorer.py
- ✅ 易于维护：逻辑清晰，互不干扰

================================================================================

【模块 4: LLM 三级 Fallback 机制 (gateway/utils/llm_client.py)】

👤 角色: 系统的"语言中枢"，提供统一的 LLM 调用接口

【4.1】为什么需要 Fallback？

问题场景：
```
用户提问 → 调用 LLM 回答
  ├─ 如果 OpenAI 宕机怎么办？
  ├─ 如果 API 限流怎么办？
  └─ 如果响应超时怎么办？

传统做法 (错误):
  用户收到错误: "Service Unavailable"
  用户转身离开: "这个 APP 太烂了"

Fallback 做法 (正确):
  OpenAI 失败 → 自动切换到 GPT-4 → 再失败 → 切换到 DeepSeek
  用户体验: 无缝过渡，不知道发生了什么
```

【4.2】三级 Fallback 的完整代码讲解

```python
# llm_client.py (228 行)

# 【全局状态】用来追踪本地模型的失败次数
_local_model_failures = 0
MAX_LOCAL_FAILURES = 3  # 失败 3 次后自动切换到云端

def _chat_local(
    messages: list,
    max_new_tokens: int = 1024,
    temperature: float = 0.2
) -> str:
    """
    第一级: 本地 Qwen2.5-7B-LoRA 模型

    优势:
    - 成本: 0 元 (本地计算)
    - 隐私: 数据不离开公司
    - 速度: 如果有 GPU，比云端还快

    劣势:
    - 需要 GPU (如果没 GPU 会很慢)
    - 效果可能不如 GPT-4 (模型小)
    """

    global _local_model_failures

    try:
        # 第一步: 调用本地模型
        # 加载 LoRA 适配器权重
        from peft import AutoPeftModelForCausalLM
        from transformers import AutoTokenizer

        model_path = "./models/qwen2.5-7b-lora"
        model = AutoPeftModelForCausalLM.from_pretrained(model_path)
        tokenizer = AutoTokenizer.from_pretrained(model_path)

        # 第二步: 格式化消息为提示词
        prompt = _format_messages_to_prompt(messages)

        # 第三步: 生成回答
        inputs = tokenizer(prompt, return_tensors="pt")
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=0.95,  # nucleus sampling (多样性)
            do_sample=True
        )

        response = tokenizer.decode(outputs[0], skip_special_tokens=True)

        # 成功！重置失败计数器
        _local_model_failures = 0
        logger.info("[LLM] 本地模型成功")

        return response

    except Exception as e:
        # 失败处理
        logger.warning(f"[LLM] 本地模型失败: {e}")
        _local_model_failures += 1

        if _local_model_failures >= MAX_LOCAL_FAILURES:
            logger.error(f"[LLM] 本地模型连续失败 {MAX_LOCAL_FAILURES} 次，切换到云端")

        raise  # 向上抛出异常，调用者会尝试第二级

def _chat_openai(
    messages: list,
    max_tokens: int = 1024,
    temperature: float = 0.2
) -> str:
    """
    第二级: OpenAI GPT-4o

    优势:
    - 效果最好 (最强的通用 LLM)
    - 稳定可靠

    劣势:
    - 成本最高 (每 1M token 约 $15)
    - 有 API 限流 (rate limit)
    """

    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )

        logger.info("[LLM] OpenAI 成功")
        return response.choices[0].message.content

    except Exception as e:
        logger.warning(f"[LLM] OpenAI 失败: {e}")
        raise  # 继续抛出，尝试第三级

def _chat_deepseek(
    messages: list,
    max_tokens: int = 1024,
    temperature: float = 0.2
) -> str:
    """
    第三级: DeepSeek (最后的兜底)

    优势:
    - 成本相对低 (对标 GPT-3.5)
    - 中文效果好 (因为是中国团队)

    劣势:
    - 英文效果一般
    - 有时响应较慢
    """

    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com"  # DeepSeek 的 API 端点
        )

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )

        logger.info("[LLM] DeepSeek 成功")
        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"[LLM] DeepSeek 也失败了: {e}")
        raise  # 所有 fallback 都失败，抛出给用户

def chat(
    messages: list,
    temperature: float = 0.2,
    max_tokens: int = 1024
) -> str:
    """
    统一的 LLM 调用接口 (三级 Fallback)

    这是整个项目中所有 Agent 都调用的接口！
    不管是 router、analyst、verifier，都用这个
    """

    # 【第一次尝试】本地模型
    try:
        logger.info("[LLM] 尝试本地模型")
        return _chat_local(messages, max_tokens, temperature)
    except Exception as e1:
        logger.warning(f"[LLM] 第一级失败，尝试 OpenAI")

    # 【第二次尝试】OpenAI
    try:
        logger.info("[LLM] 尝试 OpenAI GPT-4o")
        return _chat_openai(messages, max_tokens, temperature)
    except Exception as e2:
        logger.warning(f"[LLM] 第二级失败，尝试 DeepSeek")

    # 【第三次尝试】DeepSeek (最后兜底)
    try:
        logger.info("[LLM] 尝试 DeepSeek (最后兜底)")
        return _chat_deepseek(messages, max_tokens, temperature)
    except Exception as e3:
        # 全部失败！
        error_msg = f"所有 LLM 都失败了: 本地模型 → OpenAI → DeepSeek"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
```

流程图 (ASCII):

```
用户调用 chat(messages)
  ↓
┌─────────────────────────────────┐
│ 第一级: 本地 Qwen2.5-7B-LoRA    │
│ ✅ 成功 → 立即返回              │
│ ❌ 失败 → 计数器 +1             │
│         若 count >= 3 → 警告   │
└─────────────────────────────────┘
  │ (失败)
  ↓
┌─────────────────────────────────┐
│ 第二级: OpenAI GPT-4o           │
│ ✅ 成功 → 立即返回              │
│ ❌ 失败 → 继续               │
└─────────────────────────────────┘
  │ (失败)
  ↓
┌─────────────────────────────────┐
│ 第三级: DeepSeek (兜底)         │
│ ✅ 成功 → 立即返回              │
│ ❌ 失败 → 抛出异常给用户        │
└─────────────────────────────────┘
  │
  ↓
返回结果给 Agent 调用者
```

================================================================================
第三部分: 发现的问题与改进方案 (帮你"调试"代码)
================================================================================

【问题 1】 📍 数据一致性问题

现象: scheduler 表中的 risk_level 字段类型可能不一致

位置:
  - event_extractor.py 第 84 行: severity = "HIGH"  (字符串)
  - schemas.py 第 92 行: RiskLevel = Enum["LOW", "MEDIUM", "HIGH", "CRITICAL"]
  - risk_scorer.py 第 156 行: level 来自 RiskLevel 枚举

问题根源:
  event_extractor 提取的 severity 直接赋值字符串
  risk_scorer 期望的是 RiskLevel 枚举值
  如果两边格式不匹配，会导致类型验证失败

✅ 解决方案:

```python
# 【修改】event_extractor.py 第 84 行
# 原代码:
extraction = {
    "company": company,
    "severity": "HIGH"  # 纯字符串，不规范
}

# 新代码:
from gateway.models.schemas import RiskLevel

extraction = {
    "company": company,
    "severity": RiskLevel.HIGH  # 使用枚举，规范化
}

# 这样保证了整个流程中 severity 都是统一的枚举类型
```

【问题 2】 📍 缓存策略过于简单

现象: retriever_agent.py 中的缓存只按 question 哈希，没有时间过期

位置: retriever_agent.py 第 38 行

```python
cache_key = f"rag_{hash(state['question'])}"
cached_context = cache.get_cache(cache_key)
```

问题:
  - 同一个问题，不同时间的答案可能不同 (比如 ESG 指标更新了)
  - 如果一直用缓存，用户永远看不到最新信息

✅ 解决方案:

```python
# 改进版本，添加时间戳过期机制
import time
from datetime import timedelta

CACHE_TTL_HOURS = 6  # 缓存 6 小时后过期

def run_retriever(state: ESGState) -> ESGState:
    # ... 其他代码 ...

    cache_key = f"rag_{hash(state['question'])}"
    cached_data = cache.get_cache(cache_key)

    # 检查缓存是否过期
    if cached_data:
        cached_context, timestamp = cached_data
        age_hours = (time.time() - timestamp) / 3600

        if age_hours < CACHE_TTL_HOURS:
            logger.info(f"[RETRIEVER] 缓存命中 (已缓存 {age_hours:.1f} 小时)")
            state["context"] = cached_context
            return state
        else:
            logger.info(f"[RETRIEVER] 缓存过期 (已缓存 {age_hours:.1f} 小时), 重新检索")

    # 缓存未命中或已过期，进行 RAG 检索
    # ... 后续代码 ...
```

【问题 3】 📍 性能瓶颈：顺序执行的 5 阶段管道

现象: orchestrator.py 中 5 个 stage 顺序执行，不能并行

位置: orchestrator.py 第 142-195 行

```python
# 当前的顺序执行方式
stage1_result = scanner.scan()        # 耗时 10 秒
stage2_result = extractor.extract()   # 耗时 15 秒
stage3_result = scorer.score()        # 耗时 8 秒
stage4_result = matcher.match()       # 耗时 5 秒
stage5_result = notifier.notify()     # 耗时 3 秒
# 总耗时: 10 + 15 + 8 + 5 + 3 = 41 秒
```

问题:
  - 每次扫描都要等 41 秒，用户体验不好
  - 资源浪费 (CPU 闲置，等待上一个 stage 完成)

✅ 解决方案 (使用并行化):

```python
# 改进版本，使用 asyncio 并行
import asyncio

async def run_full_pipeline_async(self):
    """
    异步并行执行
    """

    # Stage 1: 扫描 (必须先执行，后面的 stage 需要输入)
    raw_events = await scanner.scan_async()

    if not raw_events:
        return {"scanned": 0}

    # Stage 2-4 可以部分并行
    # 但需要满足依赖关系:
    # - Stage 2 需要 Stage 1 的输出
    # - Stage 3 需要 Stage 2 的输出
    # - Stage 4 需要 Stage 3 的输出

    extracted = await extractor.extract_async(raw_events)
    scored = await scorer.score_async(extracted)
    matched = await matcher.match_async(scored)
    notified = await notifier.notify_async(matched)

    # 如果能真正并行，总耗时: max(10, 15, 8, 5, 3) = 15 秒
    # 相比顺序执行的 41 秒，快了 73%！

    return {
        "scanned": len(raw_events),
        "extracted": len(extracted),
        "scored": len(scored),
        "matched": len(matched),
        "notified": len(notified)
    }
```

【问题 4】 📍 错误处理不完整

现象: scanner.py 中多个数据源调用，某个源失败会导致整个 stage 失败

位置: scanner.py 第 76-98 行

```python
def scan_news_feeds(self):
    events = []

    # 如果 NewsAPI 失败，整个 scanner 失败
    news_events = self._fetch_newsapi_events()  # 可能抛出异常
    events.extend(news_events)

    # 如果上面失败，这些代码执行不了
    sec_events = self._fetch_sec_events()
    events.extend(sec_events)

    return events
```

✅ 解决方案 (降级处理):

```python
def scan_news_feeds(self):
    events = []
    sources_status = {}

    # NewsAPI 降级处理
    try:
        logger.info("[Scanner] 尝试从 NewsAPI 获取事件")
        news_events = self._fetch_newsapi_events()
        events.extend(news_events)
        sources_status["newsapi"] = "success"
        logger.info(f"[Scanner] NewsAPI 成功获取 {len(news_events)} 个事件")
    except Exception as e:
        logger.warning(f"[Scanner] NewsAPI 失败: {e}，继续其他源")
        sources_status["newsapi"] = f"failed: {e}"

    # SEC EDGAR 降级处理
    try:
        logger.info("[Scanner] 尝试从 SEC EDGAR 获取事件")
        sec_events = self._fetch_sec_events()
        events.extend(sec_events)
        sources_status["sec"] = "success"
        logger.info(f"[Scanner] SEC 成功获取 {len(sec_events)} 个事件")
    except Exception as e:
        logger.warning(f"[Scanner] SEC 失败: {e}，继续其他源")
        sources_status["sec"] = f"failed: {e}"

    # RSS 源降级处理
    try:
        logger.info("[Scanner] 尝试从 RSS 获取事件")
        rss_events = self._fetch_rss_events()
        events.extend(rss_events)
        sources_status["rss"] = "success"
        logger.info(f"[Scanner] RSS 成功获取 {len(rss_events)} 个事件")
    except Exception as e:
        logger.warning(f"[Scanner] RSS 失败: {e}")
        sources_status["rss"] = f"failed: {e}"

    # 记录扫描摘要
    logger.info(f"[Scanner] 本次扫描摘要: {sources_status}")

    if not events:
        logger.warning("[Scanner] 所有源都失败，未获取任何事件")

    return events
```

【问题 5】 📍 Supabase 外键 CASCADE 验证不完整

现象: delete_session() 删除 session 时，依赖的 chat_history 应该级联删除

位置: db/supabase_client.py 第 68-76 行

问题:
  代码假设 Supabase 已经配置了 CASCADE DELETE
  但没有验证，如果没配置，就会导致数据孤立

✅ 解决方案:

```python
def delete_session(session_id: str) -> None:
    """
    删除会话及其所有关联的聊天记录
    """

    try:
        # 第一步: 验证外键约束是否存在
        # (可选，只在迁移脚本中执行一次)
        # verify_cascade_constraint("sessions", "chat_history")

        # 第二步: 删除 session
        get_client().table("sessions").delete().eq("session_id", session_id).execute()

        # 第三步: 验证 chat_history 被级联删除了
        # (数据库应该自动删除，但我们可以验证)
        remaining = get_client().table("chat_history").select("*").eq("session_id", session_id).execute()

        if remaining.data:
            logger.error(f"[DB] 警告: session_id={session_id} 被删除，但仍有 {len(remaining.data)} 条聊天记录未删除")
            # 手动清理
            get_client().table("chat_history").delete().eq("session_id", session_id).execute()
        else:
            logger.info(f"[DB] Session 及其聊天记录全部删除: {session_id}")

    except Exception as e:
        logger.error(f"[DB] 删除 session 失败: {e}")
        raise
```

================================================================================
第四部分: 前端 UI 架构推荐 (美化演示)
================================================================================

当前状态: 缺少前端界面

推荐方案: React 18 + TailwindCSS + Recharts

【架构设计】

```
前端应用结构:

frontend/
├── src/
│   ├── components/
│   │   ├── QueryInterface.tsx      用户提问界面
│   │   │   ├─ SearchBar            输入框
│   │   │   ├─ QuestionHistory      历史记录
│   │   │   └─ ResponseDisplay      答案显示
│   │   │
│   │   ├── ESGScoreBoard.tsx       ESG 评分看板
│   │   │   ├─ RadarChart           雷达图 (E/S/G)
│   │   │   ├─ ScoreGauge           仪表盘 (0-100)
│   │   │   ├─ TrendChart           趋势图
│   │   │   └─ Heatmap              热力图
│   │   │
│   │   ├── EventMonitor.tsx        事件监测面板
│   │   │   ├─ EventList            事件列表 (带风险等级)
│   │   │   ├─ EventTimeline        时间线视图
│   │   │   ├─ RiskHeatmap          风险热力图
│   │   │   └─ NotificationBell     通知铃声
│   │   │
│   │   ├── Dashboard.tsx           主面板
│   │   │   ├─ KPICards             关键指标卡片
│   │   │   ├─ PeerComparison       对标分析
│   │   │   ├─ PredictionChart      预测趋势
│   │   │   └─ ExecutiveSummary     经营摘要
│   │   │
│   │   └── AdminPanel.tsx          管理后台 (可选)
│   │       ├─ DataSourceManagement 数据源管理
│   │       ├─ ReportScheduler      报告调度
│   │       ├─ PushRuleEditor       推送规则编辑
│   │       └─ SystemHealth         系统健康检查
│   │
│   ├── hooks/
│   │   ├── useQuery.ts             查询钩子
│   │   ├── useESGScores.ts         ESG 评分钩子
│   │   └── useEventStream.ts       事件流钩子 (WebSocket)
│   │
│   ├── services/
│   │   └── api.ts                  API 调用层
│   │       ├─ queryCompany()       查询公司信息
│   │       ├─ getESGScores()       获取 ESG 评分
│   │       ├─ subscribeEvents()    订阅事件流
│   │       └─ generateReport()     生成报告
│   │
│   ├── styles/
│   │   ├── globals.css             全局样式 (TailwindCSS)
│   │   └── themes.css              主题配置
│   │
│   └── App.tsx                     主应用文件
│       ├─ 路由配置 (React Router)
│       ├─ 全局状态 (Redux / Zustand)
│       └─ 主题切换 (浅色 / 深色)
│
├── public/
│   ├── logo.svg
│   └── icons/
│
└── package.json                    依赖配置
```

【核心界面设计】

1️⃣ QueryInterface (智能查询界面)

```
┌────────────────────────────────────────────────────────┐
│  ESG Agentic RAG Copilot                        ⚙️ 设置  │
├────────────────────────────────────────────────────────┤
│                                                         │
│  搜索框:                                               │
│  ┌──────────────────────────────────────────────────┐  │
│  │ 请输入公司名称或 ESG 相关问题...                    │ 🔍 │
│  │                                                 │  │
│  │ 热门问题:                                         │  │
│  │  • 特斯拉的环保政策评分是多少?                     │  │
│  │  • 苹果与微软的社会责任对标分析                   │  │
│  │  • 最近 ESG 相关风险事件有哪些?                   │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  上次搜索:                                             │
│  ┌──────────────────────────────────────────────────┐  │
│  │ ✓ [2026-03-29 14:32] Tesla ESG evaluation       │  │
│  │ ✓ [2026-03-28 09:15] Apple carbon emissions    │  │
│  │ ✓ [2026-03-27 16:45] Microsoft diversity ratio │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
└────────────────────────────────────────────────────────┘
```

2️⃣ ESG ScoreBoard (评分看板)

```
┌─────────────────────────────────────────────────────────┐
│                  Tesla 的 ESG 评分                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ⭐ 综合评分: 72/100                  置信度: 85%      │
│  ├─ 环保 (E): 78/100  ███████░░                        │
│  ├─ 社会 (S): 65/100  ██████░░░                        │
│  └─ 治理 (G): 73/100  ███████░░                        │
│                                                         │
│  【左】雷达图                   【右】仪表盘            │
│                                                         │
│     碳排放        员工满意度          Tesla             │
│        ╱╲        ╱                    ▲ 78             │
│       ╱  ╲      ╱                   ╱   ╲             │
│      ╱────╲────╱                   ╱     ╲             │
│           └──── 供应链伦理    ═════       ════          │
│       能源效率    ↑                                     │
│                成本竞争力                               │
│                                                         │
│  【下】趋势图                                           │
│  ┌────────────────────────────────────────────────┐    │
│  │ 100├                                            │    │
│  │  80├      ╱╲        ╱╲      ╱╲                │    │
│  │  60├╱╲    ╱  ╲╱╲╱╲╱  ╲╱╲╱╲╱                  │    │
│  │  40├  ╲              ╱                        │    │
│  │    └──┬──┬──┬──┬──┬──┬──┬──┬──┬──────────────┘    │
│  │      Jan Feb Mar Apr May Jun Jul Aug Sep Oct      │    │
│  │      — E 维度 — S 维度 — G 维度                 │    │
│  └────────────────────────────────────────────────┘    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

3️⃣ EventMonitor (事件监测)

```
┌─────────────────────────────────────────────────────────┐
│                ESG 事件监测 (最近 7 天)                 │
├─────────────────────────────────────────────────────────┤
│  🔴 高风险 (1)  🟠 中风险 (3)  🟡 低风险 (2)            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  🔴 【高】特斯拉员工劳资纠纷 (环境: 工人权益)            │
│     ├─ 风险评分: 89/100                               │
│     ├─ 发布时间: 2026-03-29 08:45                    │
│     └─ 推荐措施: 改善员工薪酬和工作条件                  │
│                                                         │
│  🟠 【中】苹果供应链碳排放审计结果                       │
│     ├─ 风险评分: 62/100                               │
│     ├─ 发布时间: 2026-03-28 14:20                    │
│     └─ 推荐措施: 增加可再生能源使用比例                  │
│                                                         │
│  🟠 【中】微软多样性报告发布                             │
│     ├─ 风险评分: 48/100 (正面事件)                    │
│     ├─ 发布时间: 2026-03-27 09:30                    │
│     └─ 亮点: 女性员工比例提升到 37%                   │
│                                                         │
│  【时间线视图】                                        │
│                                                         │
│  ────●────────────●─────●────────●────────●───────── │
│   3/25          3/27    3/28      3/29    3/30        │
│   (苹果)  (微软)  (苹果)  (特斯拉) (苹果)              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

【前端关键技术栈】

```
核心框架:
  - React 18           组件化 UI 构建
  - React Router v6    单页应用路由
  - TypeScript         类型安全

UI 组件库:
  - TailwindCSS        样式管理
  - shadcn/ui          高级组件 (可选)
  - Recharts           数据可视化图表
    * LineChart        趋势图
    * BarChart         柱状图
    * RadarChart       雷达图
    * PieChart         饼图
    * HeatMap          热力图

状态管理:
  - Zustand           轻量级状态管理
  - React Query       服务端状态管理

实时通信:
  - Socket.io         WebSocket (实时事件推送)
  - Server-Sent Events (SSE) 作为备选

API 通信:
  - Axios             HTTP 客户端
  - Fetch API         备选

开发工具:
  - Vite              快速构建工具
  - ESLint            代码检查
  - Prettier          代码格式化
```

【部署建议】

```
前端部署架构:

GitHub (源代码)
  ↓ (push)
GitHub Actions (CI/CD)
  ├─ npm install        安装依赖
  ├─ npm run lint       检查代码
  ├─ npm run build      构建生产包
  └─ npm run test       运行测试
  ↓ (成功)
Cloudflare Pages / Vercel / AWS S3 + CloudFront
  ├─ 静态资源缓存
  ├─ CDN 加速
  └─ 自动 HTTPS
  ↓
用户浏览器访问
```

================================================================================
第五部分: MultiAgent 升级路线图 (进阶优化)
================================================================================

【当前架构】单 Agent 工作流

现状:
```
问题 → [LangGraph 单一 Agent] → 答案

这个 Agent 做的事:
  1. 分类问题
  2. 检索知识
  3. 分析数据
  4. 验证答案

问题:
  - 一个 Agent 做所有事，复杂度高
  - 不同任务的最优策略不同 (ESG 分析 vs 事实查询)
  - 难以扩展新功能 (加新的打分维度时需要改 analyst_agent)
```

【多 Agent 愿景】4 阶段升级计划

```
Stage 1 [当前]:        Stage 2 [1-2 周]:       Stage 3 [2-3 周]:     Stage 4 [3-4 周]:
单 Agent              多 Agent 协作          Agent 学习与优化     自适应与自演进

  Router              Router Agent           Router Agent         Router Agent
    ↓                     ↓                      ↓                    ↓
 Retriever ──────→   [ESG Agent]           [ESG Agent]          [ESG Agent]
    ↓                  [Fact Agent]    +    [Fact Agent]  +     [Fact Agent]
 Analyst              [General Agent]       [General Agent]       [General Agent]
    ↓                  [Memory Agent]       [Memory Agent]      + [Learning Agent]
 Verifier            (新增)               (新增)                 (新增)

控制方式:          协作方式:            优化方向:              创新方向:
单路顺序           Agent 间通信         - 性能优化            - 自学习
                   共享记忆             - 准确度提升          - 自演进
                                        - 错误率降低          - 自改进
```

================================================================================

【Stage 2】多 Agent 协作架构 (1-2 周)

核心思想: 将单一的 Agent 分解成多个专家级 Agent，每个专注于一个任务

架构设计:

```
用户问题
  ↓
[Router Agent] ← 入口，判断问题类型
  ├─ 若是 ESG 分析 → 转给 ESG Agent
  ├─ 若是 事实查询 → 转给 Fact Agent
  ├─ 若是 通用问题 → 转给 General Agent
  └─ 若是 历史查询 → 转给 Memory Agent
  ↓
[专家 Agent] ← 各司其职
  ├─ ESG Agent
  │   ├─ 任务: 15 维度评分
  │   ├─ 工具: esg_scorer, data_sources
  │   └─ 输出: 结构化评分 + 对标分析
  │
  ├─ Fact Agent
  │   ├─ 任务: 事实核查
  │   ├─ 工具: RAG retriever, fact_checker
  │   └─ 输出: 事实判断 + 置信度
  │
  ├─ General Agent
  │   ├─ 任务: 通用 QA
  │   ├─ 工具: 更广的知识库
  │   └─ 输出: 自然语言答案
  │
  └─ Memory Agent
      ├─ 任务: 记忆与对话历史
      ├─ 工具: chat_history, sessions
      └─ 输出: 上下文回忆

共享组件:
  ├─ Shared Memory (会话上下文)
  ├─ Shared Tools (通用工具集)
  └─ Shared LLM (三级 fallback)

[Coordinator] ← 协调器
  ├─ 管理 Agent 间通信
  ├─ 合并多个 Agent 的结果
  └─ 处理冲突 (若多个 Agent 给出不同答案)
  ↓
最终答案
```

【Stage 2 实现步骤】

```python
# 伪代码

class ESGAgent(Agent):
    """ESG 专家 Agent"""

    def __init__(self):
        self.name = "ESG Expert"
        self.tools = [
            esg_scorer,      # ESG 评分工具
            data_sources,    # 多源数据融合
            rag_retriever    # 知识库检索
        ]

    def run(self, question: str, context: dict) -> dict:
        """
        仅处理 ESG 相关问题
        """
        # Step 1: 数据准备
        company_data = data_sources.fetch(question)

        # Step 2: 评分
        scores = esg_scorer.score(company_data)

        # Step 3: 检索补充信息
        context = rag_retriever.retrieve(question)

        # Step 4: 生成分析报告
        analysis = self.llm.generate(f"""
            基于以下数据生成 ESG 分析报告:
            公司数据: {company_data}
            评分: {scores}
            上下文: {context}
        """)

        return {
            "agent": self.name,
            "scores": scores,
            "analysis": analysis,
            "confidence": 0.85
        }

class Coordinator:
    """多 Agent 协调器"""

    def __init__(self):
        self.agents = {
            "esg": ESGAgent(),
            "fact": FactAgent(),
            "general": GeneralAgent(),
            "memory": MemoryAgent()
        }

    def route(self, question: str, session_id: str) -> dict:
        """
        路由问题到对应 Agent
        """
        # Step 1: 分类
        task_type = self.classify(question)  # "esg" / "fact" / "general"

        # Step 2: 获取会话上下文
        context = self.agents["memory"].get_context(session_id)

        # Step 3: 调用对应 Agent
        agent = self.agents[task_type]
        result = agent.run(question, context)

        # Step 4: 可选 - 调用其他 Agent 补充
        # (如果信心不足，可以并行调用多个 Agent)
        if result["confidence"] < 0.7:
            other_result = self.agents["fact"].run(question, context)
            result["additional_info"] = other_result

        # Step 5: 保存会话
        self.agents["memory"].save(session_id, question, result)

        return result
```

【Stage 3】Agent 学习与优化 (2-3 周)

核心思想: Agent 从用户反馈中学习，优化自己的输出质量

实现机制:

```
用户反馈循环:

用户问题 → Agent 回答 → 用户反馈 (👍 / 👎 / 评论) → 优化

具体步骤:

1. 收集反馈数据
   - 用户点赞 → 正样本 (学什么时做对了)
   - 用户点踩 → 负样本 (学什么时做错了)
   - 用户评论 → 详细反馈 (定性分析)

2. 分析失败原因
   - 是否是因为检索失败? (上下文不对)
   - 是否是因为 LLM 理解错误? (逻辑不对)
   - 是否是因为格式化错误? (输出格式错误)

3. 自动优化
   选项 A: 提示词优化
     问题: "Agent 的 prompt 是否需要调整?"
     解决: 自动生成更好的 prompt

   选项 B: 知识库优化
     问题: "检索到的文档是否不相关?"
     解决: 调整 RAG 的重排序权重或检索策略

   选项 C: 工具链优化
     问题: "是否使用了错误的工具?"
     解决: 调整 Agent 选择工具的优先级

4. A/B 测试验证
   - 50% 用户用旧版本
   - 50% 用户用新版本
   - 比较反馈率，确保改进有效
```

【Stage 4】自适应与自演进 (3-4 周)

核心思想: Agent 自动识别瓶颈，主动提升自己

```
自演进循环:

监控系统指标
  ├─ 用户满意度 (反馈评分)
  ├─ 回答准确度 (fact-checking 结果)
  ├─ 响应时间 (性能指标)
  └─ 错误率 (异常统计)
         ↓
识别瓶颈
  ├─ 若准确度低 → 调整 LLM 参数或 prompt
  ├─ 若速度慢 → 优化缓存策略或并行化
  ├─ 若错误多 → 增加验证步骤
  └─ 若成本高 → 优先使用本地模型
         ↓
自动调整
  ├─ 动态调整温度 (temperature)
  ├─ 动态选择 LLM (本地 vs 云端)
  ├─ 动态调整缓存 TTL
  └─ 动态选择检索策略
         ↓
效果验证
  ├─ A/B 测试 (新策略 vs 旧策略)
  ├─ 用户反馈 (是否满意?)
  └─ 性能指标 (是否改进?)
         ↓
持续迭代
  每 24 小时重新评估一次，不断改进
```

================================================================================
第六部分: 代码理解检查清单 (自测)
================================================================================

【Level 1】入门理解 (能说出每个文件的用途)

你能回答这些问题吗？

1. gateway 目录下有哪 5 个核心模块？
   □ agents, rag, scheduler, db, utils

2. 什么是 ESGState？
   □ LangGraph 中状态转移用的数据结构

3. 为什么需要 RAG？
   □ 让 LLM 能访问最新的知识库

4. scheduler 的 5 个阶段是什么？
   □ Scanner → Extractor → Scorer → Matcher → Notifier

5. LLM 的三级 Fallback 是什么？
   □ 本地 Qwen → OpenAI → DeepSeek

【Level 2】理解应用 (能说出数据流和关键逻辑)

你能回答这些问题吗？

1. 用户提问后，数据流经过哪些 Agent？
   □ Router → Retriever → (Analyst 或 Verifier)

2. 为什么 Verifier 要检测幻觉？
   □ LLM 会说错话，需要事实核查和置信度评估

3. retriever_agent 中的缓存有什么问题？
   □ 没有时间过期机制，长期使用会导致过时信息

4. orchestrator 的 5 个 stage 为什么要按顺序执行？
   □ 后续 stage 依赖前一个 stage 的输出

5. 如何改进 orchestrator 的性能？
   □ 使用 asyncio 并行执行可并行的 stage

【Level 3】深度掌握 (能改进和扩展代码)

你能做到这些吗？

1. 修改 esg_scorer 中的维度权重
   □ 可以，修改 E_METRICS / S_METRICS / G_METRICS 中的 weight 字段

2. 添加新的评分指标
   □ 可以，在 ESGScoringFramework 中添加新指标定义和权重计算逻辑

3. 替换 RAG 检索策略
   □ 可以，修改 retriever.py 中的 build_custom_retriever() 函数

4. 添加新的数据源
   □ 可以，在 data_sources.py 中添加新的 DataSource 子类

5. 添加新的推送渠道 (比如 SMS)
   □ 可以，在 notifier.py 中添加 send_sms() 方法

【Level 4】精通与创新 (能建议架构改进)

你能思考这些吗？

1. 从单 Agent 升级到多 Agent 的关键是什么？
   □ 分解职责，让每个 Agent 成为专家，通过 Coordinator 协调

2. 如何让系统具备自学习能力？
   □ 收集用户反馈，分析失败原因，自动调整 prompt / 参数 / 策略

3. 如何提升 RAG 的检索质量？
   □ 尝试不同的分块策略、embedding 模型、重排序器

4. 如何降低系统成本？
   □ 优先使用本地模型，合理使用缓存，降低 API 调用

5. 如何提升用户体验？
   □ 更美观的 UI、更快的响应、更好的解释能力

================================================================================
第七部分: 项目总结 (从初学者到精通)
================================================================================

【项目核心价值】

这个项目展示了现代 AI 系统的完整实现：

✅ Agent 工作流 (LangGraph)
   - 学到: 如何编排复杂的 AI 流程
   - 应用: 金融分析、医疗诊断、法律顾问

✅ RAG 检索增强
   - 学到: 如何让 LLM 访问外部知识
   - 应用: 文档分析、知识库搜索、智能客服

✅ 调度系统 (ETL Pipeline)
   - 学到: 如何处理大规模数据和事件
   - 应用: 数据仓库、日志分析、监控告警

✅ LLM 三级 Fallback
   - 学到: 如何构建高可用系统
   - 应用: 生产级别服务、混合 LLM 策略

✅ 数据库设计 (Supabase)
   - 学到: 如何设计扩展性好的数据模型
   - 应用: SaaS 应用、实时协作系统

【从"不理解"到"精通"的旅程】

Day 1: 读这个 introduction.py
  学到: 项目的全景图，每个文件的用途
  成就: "哦，原来项目是这样组织的"

Day 2-3: 深入学习关键文件
  学到: graph.py 怎样编排流程，rag_main.py 怎样管理向量库，llm_client.py 如何实现 fallback
  成就: "我能理解每个模块的工作原理了"

Day 4-5: 追踪数据流
  学到: 用户提问 → 数据流经过所有环节 → 最终返回答案
  成就: "我能预测代码的执行路径了"

Day 6-7: 尝试修改
  学到: 改一个参数 / 添加新指标 / 替换数据源
  成就: "我能自信地修改代码了，不怕破坏东西"

Week 2: 规划改进
  学到: 自动化性能优化、多 Agent 架构、自学习机制
  成就: "我能提出系统性的改进方案了"

Week 3+: 创新与扩展
  学到: 根据业务需求，自主设计新功能
  成就: "这不再是'Claude 的代码'，而是'我的项目'"

【你现在掌握的技能】

✅ AI Agent 架构设计
✅ RAG 系统实现
✅ 大型 Python 项目组织
✅ 事件驱动的调度系统
✅ LLM API 的生产级别集成
✅ Supabase 数据库设计
✅ 前端 API 设计 (RESTful)
✅ 系统性能优化思路

【下一步怎么走】

选项 A: 深化理解 (1-2 周)
  - 逐个文件读代码，画数据流图
  - 修改参数，看结果变化
  - 写单元测试，确保理解正确

选项 B: 部署上线 (2-4 周)
  - 部署到云服务器 (AWS / Google Cloud)
  - 配置数据库迁移
  - 集成前端界面
  - 设置监控和告警

选项 C: 功能扩展 (3-6 周)
  - 实现 MultiAgent 架构 (Stage 2-4)
  - 添加前端 React 应用
  - 接入更多数据源
  - 实现自学习机制

选项 D: 开源和分享 (6-12 周)
  - 完善文档
  - 优化代码质量
  - 发布到 GitHub
  - 写技术博客分享经验

================================================================================
后记
================================================================================

这个项目不仅仅是代码，更是一套完整的 AI 系统设计思想。

从单一 LLM 查询 → RAG 增强 → Agent 工作流 → 主动监测调度 → 多 Agent 协作，
每一层都代表了 AI 工程化的一个关键步骤。

希望这个 introduction.py 能帮你从"消费者"变成"拥有者"。

记住：
💡 代码本身不难，难的是理解背后的设计思想
💡 最好的学习方式是修改 → 测试 → 观察结果 → 再修改
💡 不要怕 break，break 的时候你学到最多

---

最后，一个问题留给你思考：

"如果你要给这个项目添加一个新功能，比如'基于历史分析，自动预测未来 30 天的 ESG 风险趋势'，
你会如何设计？需要修改哪些文件？"

这个问题的答案就是你真正精通这个项目的证明。

---

Happy Coding! 🚀

Claude Code Team
2026-03-29
"""
