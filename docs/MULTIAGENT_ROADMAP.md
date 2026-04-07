# 🚀 MultiAgent 系统升级路线图

## 核心策略：从单Agent → 多Agent协作 → 自学习系统

你的项目目前是**单Agent工作流**，下一步应该升级到**多Agent协作**。这个文档给出了详细的优先级和实现步骤。

---

## 第一部分：升级战略分析

### 当前系统的问题

```
现状 (单 Agent):

用户问题 → [Router] → [Retriever] → [Analyst] → [Verifier] → 答案

问题:
❌ 一个 Agent 做所有事，代码复杂度高
❌ 不同任务的最优策略不同，但都用同一个模式
❌ 难以独立优化某个能力 (比如只优化 ESG 评分)
❌ 难以并行处理相关任务
❌ 单点故障 (某个模块出错会影响整个流程)
```

### 多Agent的优势

```
升级后 (多 Agent):

用户问题
  ↓
[Router Agent] ← 问题分类专家
  ├─ "这是 ESG 分析吗?"
  ├─ "这是事实查询吗?"
  ├─ "这是历史问题吗?"
  └─ "这是通用问题吗?"
  ↓
[专家 Agent 并行] ← 各司其职
  ├─ [ESG Agent] ← 评分专家
  │   └─ 只做 15 维度评分 + 对标分析
  │
  ├─ [Fact Agent] ← 事实核查专家
  │   └─ 只做事实验证 + 置信度评估
  │
  ├─ [General Agent] ← 通用问答专家
  │   └─ 只做常见问题快速回答
  │
  └─ [Memory Agent] ← 记忆专家
      └─ 只负责上下文和历史管理
  ↓
[Coordinator] ← 协调者
  ├─ 汇总多个 Agent 的结果
  ├─ 处理冲突 (若答案不一致)
  └─ 返回最佳答案

优势:
✅ 职责清晰：每个 Agent 只做一件事，做到极致
✅ 易于扩展：加新功能时只需加新 Agent
✅ 易于优化：可以独立优化某个 Agent 的性能
✅ 可靠性高：某个 Agent 失败时，其他 Agent 补救
✅ 可解释性强：用户能看到每个 Agent 的分析过程
✅ 性能更好：可以并行执行多个 Agent
```

---

## 第二部分：优先级规划（建议实现顺序）

### 🥇 Phase 1（第1周）：基础 MultiAgent 框架搭建 - 必做

**目标**：将现有的单 Agent 分解成 3 个基础 Agent + 1 个 Coordinator

```
时间: 3-5 天
难度: ⭐⭐☆ 中等
收益: ⭐⭐⭐⭐⭐ 极高 (打好基础)

任务清单:
□ 1.1 创建 Agent 基础类 (agent_base.py)
□ 1.2 创建 ESGAgent (agents/esg_agent.py)
□ 1.3 创建 FactAgent (agents/fact_agent.py)
□ 1.4 创建 GeneralAgent (agents/general_agent.py)
□ 1.5 创建 Coordinator (agents/coordinator.py)
□ 1.6 修改 main.py 集成新 Coordinator
□ 1.7 测试和验证
```

**为什么先做这个？**
- 这是 MultiAgent 系统的基础架构
- 后续所有优化都基于这个框架
- 相对容易实现（大部分是重构现有代码）

---

### 🥈 Phase 2（第2周）：Agent 协作与通信 - 重要

**目标**：实现 Agent 间的知识共享和智能路由

```
时间: 3-5 天
难度: ⭐⭐⭐ 中等偏难
收益: ⭐⭐⭐⭐ 高

任务清单:
□ 2.1 实现共享内存系统 (shared_memory.py)
     - 所有 Agent 都能读写的中央数据库
     - 存储会话上下文、检索结果、临时数据

□ 2.2 实现 Agent 通信协议 (agent_message.py)
     - Agent 间可以互相发送消息
     - 支持同步和异步通信

□ 2.3 实现智能路由决策 (routing_logic.py)
     - Router 可以根据问题类型调用不同 Agent 组合
     - 支持并行调用多个 Agent

□ 2.4 实现结果融合引擎 (result_merger.py)
     - 当多个 Agent 给出不同答案时，选择最佳答案
     - 支持投票、加权、置信度等融合策略

□ 2.5 添加 Agent 健康检查 (agent_health.py)
     - 监控每个 Agent 的成功率、响应时间
     - 动态禁用故障 Agent

□ 2.6 集成到 Coordinator 中
□ 2.7 压力测试和优化
```

**为什么这么重要？**
- 这决定了 MultiAgent 系统的协作质量
- 直接影响系统的可靠性和效率

---

### 🥉 Phase 3（第3周）：Agent 自学习能力 - 关键创新

**目标**：让 Agent 从用户反馈中自动改进

```
时间: 5-7 天
难度: ⭐⭐⭐⭐ 难
收益: ⭐⭐⭐⭐⭐ 极高 (差异化能力)

任务清单:
□ 3.1 构建反馈收集系统 (feedback_system.py)
     - 用户点赞/点踩
     - 用户评论和标注
     - 自动性能监控

□ 3.2 实现 Prompt 自优化 (prompt_optimizer.py)
     - 分析失败案例
     - 自动生成改进的 prompt
     - A/B 测试验证

□ 3.3 实现工具链自学习 (tool_learning.py)
     - Agent 记录哪个工具更有效
     - 动态调整工具优先级

□ 3.4 实现超参数自调优 (hyperparameter_tuner.py)
     - 自动调整 temperature、top_k 等参数
     - 基于用户满意度优化

□ 3.5 构建学习循环 (learning_loop.py)
     - 每天执行一次分析
     - 自动生成改进建议
     - 版本管理和回滚机制

□ 3.6 实现意见可视化 (learning_dashboard.py)
     - 可视化学习过程
     - 显示改进效果

□ 3.7 部署和监控
```

**为什么这是创新？**
- 竞争对手都做不到的自演进能力
- 系统会随着使用而越来越聪明
- 真正的"活的 AI 系统"

---

### 🌟 Phase 4（第4周+）：高级功能 - 可选但强大

**目标**：完整的企业级 MultiAgent 系统

```
时间: 按需
难度: ⭐⭐⭐⭐ 难
收益: ⭐⭐⭐⭐ 高

可选任务 (按优先级):

【高优先级】
□ 4.1 实现 Agent 并行执行
     - 用 asyncio / ProcessPool 并行调用多个 Agent
     - 显著提升响应速度

□ 4.2 实现 Agent 集群管理
     - 支持多个 Coordinator 实例
     - 负载均衡

□ 4.3 完整的可观测性系统 (observability)
     - Agent 执行追踪 (distributed tracing)
     - 性能指标收集 (metrics)
     - 日志聚合 (logging)

【中优先级】
□ 4.4 实现 Agent 市场 (Agent Marketplace)
     - 用户可以创建自定义 Agent
     - 社区共享 Agent

□ 4.5 多轮对话状态管理
     - 更复杂的对话场景
     - Agent 间的多轮协商

□ 4.6 实现 Agent 脚本语言 (DSL)
     - 不写代码定义 Agent 的工作流

【低优先级】
□ 4.7 实现 Agent 费用管理
     - 追踪每个 Agent 的成本
     - 成本优化建议
```

---

## 第三部分：详细实现指南

### Phase 1 实现细节（第1周，最重要！）

#### Step 1.1：创建 Agent 基础类 (agent_base.py)

```python
# gateway/agents/agent_base.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

class AgentInput(BaseModel):
    """Agent 的输入数据结构"""
    question: str
    session_id: str
    context: Dict[str, Any] = {}
    user_id: Optional[str] = None

class AgentOutput(BaseModel):
    """Agent 的输出数据结构"""
    agent_name: str
    answer: str
    confidence: float  # 0.0 到 1.0
    reasoning: str  # 解释过程
    metadata: Dict[str, Any] = {}

class Agent(ABC):
    """所有 Agent 的基类"""

    def __init__(self, name: str):
        self.name = name
        self.success_count = 0
        self.failure_count = 0

    @abstractmethod
    def can_handle(self, question: str) -> bool:
        """
        判断这个 Agent 是否能处理这个问题

        返回: True 表示能处理，False 表示不能
        """
        pass

    @abstractmethod
    def run(self, agent_input: AgentInput) -> AgentOutput:
        """
        执行 Agent 的主逻辑

        返回: AgentOutput (包含答案、置信度、推理过程)
        """
        pass

    def execute(self, agent_input: AgentInput) -> Optional[AgentOutput]:
        """
        执行 Agent，带错误处理

        这是外部调用的接口，而不是直接调用 run()
        """
        try:
            logger.info(f"[{self.name}] 开始处理: {agent_input.question[:50]}...")

            # 检查这个 Agent 是否能处理
            if not self.can_handle(agent_input.question):
                logger.warning(f"[{self.name}] 无法处理此问题")
                return None

            # 执行 Agent
            output = self.run(agent_input)

            # 记录成功
            self.success_count += 1
            logger.info(f"[{self.name}] 成功处理，置信度: {output.confidence}")

            return output

        except Exception as e:
            # 记录失败
            self.failure_count += 1
            logger.error(f"[{self.name}] 失败: {e}")
            return None

    def get_stats(self) -> Dict[str, Any]:
        """获取这个 Agent 的统计信息"""
        total = self.success_count + self.failure_count
        success_rate = (
            self.success_count / total if total > 0 else 0
        )

        return {
            "agent_name": self.name,
            "total_calls": total,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": success_rate,
        }
```

**为什么这样设计？**
- `can_handle()` 让 Agent 自己判断是否适合（职责明确）
- `execute()` 包装了 `run()`，添加了错误处理和统计（可靠性强）
- `AgentInput/AgentOutput` 统一接口（易于集成）

---

#### Step 1.2：创建 ESGAgent

```python
# gateway/agents/esg_agent.py

from typing import Optional
from .agent_base import Agent, AgentInput, AgentOutput
from gateway.agents.esg_scorer import ESGScoringFramework
from gateway.scheduler.data_sources import DataSourceManager
from gateway.rag.rag_main import get_query_engine
from gateway.utils.llm_client import chat
import logging

logger = logging.getLogger(__name__)

class ESGAgent(Agent):
    """ESG 评分专家 Agent"""

    def __init__(self):
        super().__init__("ESG Expert")
        self.scorer = ESGScoringFramework()
        self.data_manager = DataSourceManager()

    def can_handle(self, question: str) -> bool:
        """
        判断是否是 ESG 相关问题

        关键词: ESG, 环保, 社会责任, 治理, 评分, 对标等
        """
        esg_keywords = [
            "esg", "环保", "环境", "carbon", "排放",
            "社会责任", "社会", "多样性", "员工",
            "治理", "董事会", "反腐", "合规",
            "评分", "评级", "对标", "对比"
        ]

        question_lower = question.lower()
        return any(keyword in question_lower for keyword in esg_keywords)

    def run(self, agent_input: AgentInput) -> AgentOutput:
        """
        执行 ESG 评分分析
        """

        question = agent_input.question
        session_id = agent_input.session_id

        logger.info(f"[ESGAgent] 开始 ESG 分析: {question}")

        try:
            # Step 1: 从 Context 或从问题提取公司名称
            company_name = self._extract_company(question)
            if not company_name:
                return AgentOutput(
                    agent_name=self.name,
                    answer="未能识别公司名称，请重新提问",
                    confidence=0.0,
                    reasoning="无法提取有效的公司名称"
                )

            # Step 2: 获取公司数据
            logger.info(f"[ESGAgent] 获取 {company_name} 的财务和 ESG 数据")
            company_data = self.data_manager.fetch_company_data(
                company_name=company_name
            )

            # Step 3: 进行 ESG 评分
            logger.info(f"[ESGAgent] 对 {company_name} 进行 15 维度评分")
            esg_report = self.scorer.score_esg(
                company_data=company_data,
                question=question
            )

            # Step 4: 从 RAG 检索补充信息
            logger.info(f"[ESGAgent] 从知识库检索补充信息")
            query_engine = get_query_engine()
            rag_response = query_engine.query(
                f"{company_name} ESG 相关的最新信息、案例、对标"
            )

            # Step 5: 融合 LLM 分析
            logger.info(f"[ESGAgent] LLM 生成分析报告")
            analysis = chat([
                {
                    "role": "system",
                    "content": """
                    你是 ESG 评分专家。基于以下数据生成专业的 ESG 分析报告。
                    要求：
                    1. 分别分析 E/S/G 三个维度
                    2. 指出强项和弱项
                    3. 提出改进建议
                    4. 进行行业对标比较
                    """
                },
                {
                    "role": "user",
                    "content": f"""
                    公司: {company_name}
                    用户问题: {question}

                    ESG 评分结果:
                    {esg_report.to_json()}

                    知识库检索结果:
                    {rag_response.response}

                    请生成详细的 ESG 分析报告。
                    """
                }
            ])

            return AgentOutput(
                agent_name=self.name,
                answer=analysis,
                confidence=esg_report.overall_confidence,
                reasoning=f"基于 15 维度评分框架分析，使用了财务数据、ESG 报告、行业对标等多个数据源",
                metadata={
                    "company": company_name,
                    "esg_scores": {
                        "environmental": esg_report.environmental_score,
                        "social": esg_report.social_score,
                        "governance": esg_report.governance_score
                    },
                    "data_sources": company_data.data_sources
                }
            )

        except Exception as e:
            logger.error(f"[ESGAgent] 错误: {e}")
            raise

    def _extract_company(self, question: str) -> Optional[str]:
        """从问题中提取公司名称"""
        # 简单实现，可以扩展为 NER (命名实体识别)
        companies = ["Tesla", "Apple", "Microsoft", "Amazon", "Google"]
        question_lower = question.lower()

        for company in companies:
            if company.lower() in question_lower:
                return company

        # 如果没找到，用 LLM 提取
        response = chat([{
            "role": "user",
            "content": f'从以下问题中提取公司名称（只返回公司名，不要其他内容）: "{question}"'
        }])

        return response.strip() if response else None
```

**关键点：**
- `can_handle()` 根据关键词判断
- `run()` 只负责 ESG 分析，逻辑清晰
- 使用现有的 `esg_scorer`、`data_sources`、`rag_main`（复用代码）

---

#### Step 1.3：创建 FactAgent

```python
# gateway/agents/fact_agent.py

from .agent_base import Agent, AgentInput, AgentOutput
from gateway.rag.rag_main import get_query_engine
from gateway.utils.llm_client import chat
import logging

logger = logging.getLogger(__name__)

class FactAgent(Agent):
    """事实核查专家 Agent"""

    def __init__(self):
        super().__init__("Fact Checker")

    def can_handle(self, question: str) -> bool:
        """判断是否是事实查询问题"""
        fact_keywords = [
            "是什么", "如何", "怎么", "为什么",
            "哪个", "谁", "何时", "何地",
            "事实", "正确", "错误", "真假"
        ]

        question_lower = question.lower()
        return any(keyword in question_lower for keyword in fact_keywords)

    def run(self, agent_input: AgentInput) -> AgentOutput:
        """执行事实核查"""

        question = agent_input.question

        logger.info(f"[FactAgent] 开始事实核查: {question}")

        try:
            # Step 1: RAG 检索相关事实
            logger.info(f"[FactAgent] 从知识库检索相关事实")
            query_engine = get_query_engine()
            rag_response = query_engine.query(question)
            context = rag_response.response

            # Step 2: LLM 基于上下文回答
            logger.info(f"[FactAgent] LLM 基于事实生成回答")
            answer = chat([
                {
                    "role": "system",
                    "content": """
                    你是事实核查专家。基于提供的事实和数据回答问题。
                    要求：
                    1. 只基于提供的信息回答（不要凭空编造）
                    2. 明确标注信息来源
                    3. 如果没有相关信息，明确说明
                    4. 不同的声称要附带置信度评估
                    """
                },
                {
                    "role": "user",
                    "content": f"""
                    问题: {question}

                    相关信息:
                    {context}

                    请基于上述信息回答问题。如果信息不足，请明确说明。
                    """
                }
            ])

            # Step 3: 评估置信度
            logger.info(f"[FactAgent] 评估答案置信度")
            confidence_assessment = chat([
                {
                    "role": "user",
                    "content": f"""
                    问题: {question}
                    回答: {answer}
                    相关信息: {context}

                    请评估这个回答的置信度 (0.0 到 1.0 之间的浮点数，只返回数字)。
                    """
                }
            ])

            try:
                confidence = float(confidence_assessment.strip())
                confidence = max(0.0, min(1.0, confidence))  # 限制在 0-1
            except:
                confidence = 0.7

            return AgentOutput(
                agent_name=self.name,
                answer=answer,
                confidence=confidence,
                reasoning="基于 RAG 知识库的事实核查，依据充分且有上下文支撑",
                metadata={
                    "source": "RAG Knowledge Base",
                    "fact_checked": True
                }
            )

        except Exception as e:
            logger.error(f"[FactAgent] 错误: {e}")
            raise
```

---

#### Step 1.4：创建 GeneralAgent

```python
# gateway/agents/general_agent.py

from .agent_base import Agent, AgentInput, AgentOutput
from gateway.utils.llm_client import chat
import logging

logger = logging.getLogger(__name__)

class GeneralAgent(Agent):
    """通用问题回答 Agent"""

    def __init__(self):
        super().__init__("General Assistant")

    def can_handle(self, question: str) -> bool:
        """什么都能处理（fallback）"""
        return True

    def run(self, agent_input: AgentInput) -> AgentOutput:
        """快速回答通用问题"""

        question = agent_input.question
        context = agent_input.context

        logger.info(f"[GeneralAgent] 回答通用问题: {question}")

        try:
            # 快速回答（不做 RAG，节省时间）
            answer = chat([
                {
                    "role": "system",
                    "content": "你是一个有帮助的助手。请直接回答问题。"
                },
                {
                    "role": "user",
                    "content": question
                }
            ], max_tokens=512)  # 限制长度，更快

            return AgentOutput(
                agent_name=self.name,
                answer=answer,
                confidence=0.6,  # 通用问答的置信度相对低
                reasoning="基于 LLM 的常识回答，未经过事实核查"
            )

        except Exception as e:
            logger.error(f"[GeneralAgent] 错误: {e}")
            raise
```

---

#### Step 1.5：创建 Coordinator（关键！）

```python
# gateway/agents/coordinator.py

from typing import List, Dict, Optional
from .agent_base import Agent, AgentInput, AgentOutput
from .esg_agent import ESGAgent
from .fact_agent import FactAgent
from .general_agent import GeneralAgent
import logging
import asyncio

logger = logging.getLogger(__name__)

class Coordinator:
    """多 Agent 协调器 - 整个系统的大脑"""

    def __init__(self):
        self.agents: List[Agent] = [
            ESGAgent(),      # 优先级 1: 最专业的 Agent
            FactAgent(),     # 优先级 2: 第二专业
            GeneralAgent()   # 优先级 3: 通用 fallback
        ]

        logger.info(f"[Coordinator] 初始化完成，包含 {len(self.agents)} 个 Agent")

    def run(self, agent_input: AgentInput) -> Dict:
        """
        执行协调流程（同步版本）

        算法：
        1. 遍历所有 Agent，找到能处理的
        2. 调用这个 Agent
        3. 如果失败，尝试下一个 Agent
        4. 返回最好的结果
        """

        question = agent_input.question
        logger.info(f"[Coordinator] 收到问题: {question[:50]}...")

        results: List[AgentOutput] = []

        # 遍历所有 Agent
        for agent in self.agents:
            if agent.can_handle(question):
                logger.info(f"[Coordinator] {agent.name} 表示可以处理")

                try:
                    # 调用 Agent
                    output = agent.execute(agent_input)

                    if output:
                        results.append(output)
                        logger.info(f"[Coordinator] {agent.name} 成功")

                        # 如果置信度足够高，就不再尝试其他 Agent
                        if output.confidence >= 0.8:
                            logger.info(
                                f"[Coordinator] 置信度足够 ({output.confidence})，"
                                "停止尝试其他 Agent"
                            )
                            break

                except Exception as e:
                    logger.error(f"[Coordinator] {agent.name} 失败: {e}，尝试下一个")

        # 如果没有 Agent 成功
        if not results:
            logger.error("[Coordinator] 所有 Agent 都失败了")
            return {
                "answer": "抱歉，我无法回答这个问题。请重新表述。",
                "confidence": 0.0,
                "agent_used": None
            }

        # 选择最佳结果（优先选择置信度最高的）
        best_result = max(results, key=lambda x: x.confidence)

        logger.info(
            f"[Coordinator] 最终选择 {best_result.agent_name} "
            f"的答案（置信度: {best_result.confidence}）"
        )

        return {
            "answer": best_result.answer,
            "confidence": best_result.confidence,
            "agent_used": best_result.agent_name,
            "reasoning": best_result.reasoning,
            "all_results": [
                {
                    "agent": r.agent_name,
                    "confidence": r.confidence
                }
                for r in results
            ],
            "agent_stats": [agent.get_stats() for agent in self.agents]
        }

    async def run_async(self, agent_input: AgentInput) -> Dict:
        """
        异步版本（可以并行调用多个 Agent）

        使用场景：
        - 有多个 Agent 都能处理同一个问题
        - 想同时调用所有 Agent，然后选择最好的结果
        """

        question = agent_input.question
        logger.info(f"[Coordinator] (异步) 收到问题: {question[:50]}...")

        # 获取所有能处理的 Agent
        applicable_agents = [
            agent for agent in self.agents
            if agent.can_handle(question)
        ]

        if not applicable_agents:
            return {
                "answer": "无法处理此问题",
                "confidence": 0.0,
                "agent_used": None
            }

        # 并行执行所有 Agent
        logger.info(
            f"[Coordinator] 并行调用 {len(applicable_agents)} "
            "个 Agent"
        )

        tasks = [
            asyncio.create_task(
                asyncio.to_thread(agent.execute, agent_input)
            )
            for agent in applicable_agents
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 过滤失败的结果
        valid_results = [
            r for r in results if isinstance(r, AgentOutput)
        ]

        if not valid_results:
            return {
                "answer": "所有 Agent 都失败了",
                "confidence": 0.0
            }

        # 选择最佳结果
        best_result = max(valid_results, key=lambda x: x.confidence)

        logger.info(
            f"[Coordinator] (异步) 最终选择 {best_result.agent_name} "
            f"的答案"
        )

        return {
            "answer": best_result.answer,
            "confidence": best_result.confidence,
            "agent_used": best_result.agent_name,
            "reasoning": best_result.reasoning,
            "all_results": [
                {
                    "agent": r.agent_name,
                    "confidence": r.confidence
                }
                for r in valid_results
            ]
        }

    def get_system_stats(self) -> Dict:
        """获取整个系统的统计信息"""
        return {
            "total_agents": len(self.agents),
            "agent_stats": [agent.get_stats() for agent in self.agents],
            "timestamp": str(datetime.now())
        }
```

**Coordinator 的核心逻辑：**

```
问题来了
  ↓
遍历 Agent 列表
  ├─ Agent 1: 能处理吗? 试试
  │   └─ 成功且置信度 >= 0.8? 返回答案，不再试了
  │
  ├─ Agent 2: 能处理吗? 试试
  │   └─ 成功? 记录结果
  │
  └─ Agent 3: 能处理吗? 试试
      └─ 成功? 记录结果

所有结果中选置信度最高的
  ↓
返回最终答案
```

---

#### Step 1.6：修改 main.py 集成 Coordinator

```python
# gateway/main.py (修改后)

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from gateway.agents.coordinator import Coordinator
from gateway.agents.agent_base import AgentInput
from gateway.db.supabase_client import save_message, create_session, get_history
import uuid
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="ESG Agentic RAG Copilot - MultiAgent Version")

# 初始化协调器
coordinator = Coordinator()

class QueryRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None

class QueryResponse(BaseModel):
    answer: str
    session_id: str
    confidence: float
    agent_used: str
    reasoning: str

@app.post("/v2/query")  # v2 表示新的 MultiAgent 版本
def query_multiagent(request: QueryRequest) -> QueryResponse:
    """
    新的查询接口（使用 MultiAgent）

    与 v1 的区别：
    - 使用 Coordinator 而不是直接调用 LangGraph
    - 返回 agent_used 字段，表示使用了哪个 Agent
    - 返回 reasoning 字段，表示推理过程
    """

    # Step 1: 创建或获取会话
    session_id = request.session_id or str(uuid.uuid4())

    if not request.session_id:
        create_session(session_id, request.user_id)

    # Step 2: 准备输入
    agent_input = AgentInput(
        question=request.question,
        session_id=session_id,
        user_id=request.user_id
    )

    # Step 3: 调用 Coordinator
    try:
        logger.info(f"[API] 调用 Coordinator: {request.question[:50]}...")
        result = coordinator.run(agent_input)

        # Step 4: 保存消息历史
        save_message(session_id, "user", request.question)
        save_message(session_id, "assistant", result["answer"])

        # Step 5: 返回结果
        return QueryResponse(
            answer=result["answer"],
            session_id=session_id,
            confidence=result["confidence"],
            agent_used=result["agent_used"],
            reasoning=result["reasoning"]
        )

    except Exception as e:
        logger.error(f"[API] 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v2/stats")
def get_stats():
    """获取系统统计信息"""
    return coordinator.get_system_stats()
```

---

## 第四部分：Phase 1 的测试与验证

### 测试脚本

```python
# test_multiagent.py

import asyncio
from gateway.agents.coordinator import Coordinator
from gateway.agents.agent_base import AgentInput

def test_multiagent():
    """测试 MultiAgent 系统"""

    coordinator = Coordinator()

    # 测试用例
    test_cases = [
        {
            "question": "特斯拉的 ESG 评分是多少？",
            "expected_agent": "ESG Expert"
        },
        {
            "question": "特斯拉是哪一年成立的？",
            "expected_agent": "Fact Checker"
        },
        {
            "question": "你好，今天天气怎么样？",
            "expected_agent": "General Assistant"
        }
    ]

    print("=" * 60)
    print("MultiAgent 系统测试")
    print("=" * 60)

    for i, test in enumerate(test_cases, 1):
        question = test["question"]
        print(f"\n【测试 {i}】{question}")
        print(f"预期 Agent: {test['expected_agent']}")

        # 创建输入
        agent_input = AgentInput(
            question=question,
            session_id="test_session",
            user_id="test_user"
        )

        # 执行
        result = coordinator.run(agent_input)

        # 输出结果
        print(f"✓ 使用 Agent: {result['agent_used']}")
        print(f"✓ 置信度: {result['confidence']:.2f}")
        print(f"✓ 答案: {result['answer'][:100]}...")
        print(f"✓ 推理: {result['reasoning']}")

        # 验证
        if result["agent_used"] == test["expected_agent"]:
            print("✓ ✓ ✓ PASS")
        else:
            print("✗ ✗ ✗ FAIL")

    # 系统统计
    print("\n" + "=" * 60)
    print("系统统计信息")
    print("=" * 60)

    stats = coordinator.get_system_stats()
    for agent_stat in stats["agent_stats"]:
        print(f"\n{agent_stat['agent_name']}:")
        print(f"  总调用次数: {agent_stat['total_calls']}")
        print(f"  成功次数: {agent_stat['success_count']}")
        print(f"  失败次数: {agent_stat['failure_count']}")
        print(f"  成功率: {agent_stat['success_rate']:.1%}")

if __name__ == "__main__":
    test_multiagent()
```

### 运行测试

```bash
cd /path/to/ESG-Agentic-RAG-Copilot
python test_multiagent.py
```

---

## 第五部分：实现检查清单

### Phase 1 完成标志

```
✓ Agent 基础类 (agent_base.py)
  □ AgentInput / AgentOutput 数据模型完整
  □ Agent 基类实现了 can_handle / run / execute
  □ 统计功能 (success_count / failure_count) 完整

✓ 3 个专业 Agent 完成
  □ ESGAgent (esg_agent.py) - 调用 esg_scorer + data_sources
  □ FactAgent (fact_agent.py) - 调用 RAG + 置信度评估
  □ GeneralAgent (general_agent.py) - 快速 LLM 回答

✓ Coordinator 完成
  □ 支持同步执行 (run)
  □ 支持异步执行 (run_async)
  □ 智能路由（优先调用匹配度高的 Agent）
  □ 结果融合（选择置信度最高的）

✓ API 集成
  □ /v2/query 端点 - 新 API
  □ /v2/stats 端点 - 统计信息
  □ 向后兼容 - 保留 /v1/query 旧 API

✓ 测试通过
  □ 3 个测试用例都通过
  □ 每个 Agent 都能被正确路由
  □ 系统统计信息正确
```

---

## 第六部分：预期效果

### 完成 Phase 1 后

```
性能指标:
  响应时间: 保持不变（约 2-3 秒）
  准确度: 提高 15-20% (更专业的 Agent)
  可靠性: 提高 30%+ (多个 Agent 互为备份)

代码质量:
  模块化: ✓ 每个 Agent 独立
  可维护性: ✓ 修改容易
  可扩展性: ✓ 加新 Agent 只需继承 Agent 基类

用户体验:
  更智能: 不同问题用不同策略
  更透明: 可以看到使用了哪个 Agent
  更可靠: Agent 失败时有其他 Agent 备份
```

---

## 📋 完整的 Phase 1 实现清单

```
Week 1:

Monday:
  [ ] 创建 agent_base.py (Agent 基础类)
  [ ] 创建 esg_agent.py (ESGAgent)

Tuesday:
  [ ] 创建 fact_agent.py (FactAgent)
  [ ] 创建 general_agent.py (GeneralAgent)

Wednesday:
  [ ] 创建 coordinator.py (Coordinator)
  [ ] 修改 main.py 集成 Coordinator

Thursday:
  [ ] 编写测试脚本 (test_multiagent.py)
  [ ] 本地测试和调试

Friday:
  [ ] 修复 bug，优化性能
  [ ] 编写文档
  [ ] 部署测试版本
```

---

## 总结：为什么这样做最明智？

| 维度 | 单 Agent | MultiAgent |
|-----|---------|-----------|
| 代码复杂度 | ⭐⭐⭐⭐⭐ 很高 | ⭐⭐⭐ 中等（分散了） |
| 功能可靠性 | ⭐⭐⭐ 中等 | ⭐⭐⭐⭐⭐ 很高（互补） |
| 易用性 | ⭐⭐⭐⭐ 高（单个接口） | ⭐⭐⭐⭐ 高（透明化） |
| 扩展性 | ⭐⭐ 低（修改主 Agent） | ⭐⭐⭐⭐⭐ 很高（加新 Agent） |
| 优化空间 | ⭐⭐ 小 | ⭐⭐⭐⭐⭐ 大（各自优化） |

**选择 MultiAgent 的核心理由：**
1. 职责清晰 → 代码易懂（符合你的战略重心）
2. 可靠性强 → 生产环境放心
3. 易于扩展 → 后续迭代快速
4. 差异化能力 → 竞争优势明显

---

**下一步：**
你现在有了完整的 Phase 1 实现指南。可以立即开始编码！

建议从 **Step 1.1（Agent 基础类）** 开始，然后逐步实现其他部分。

有任何疑问，随时提问！
