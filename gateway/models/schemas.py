# schemas.py — 数据模型定义
# 定义整个系统中的主要数据结构：事件、偏好、风险评分等

from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum


# ── ESG 事件模型 ──────────────────────────────────────────────────────────

class ESGEventType(str, Enum):
    """ESG 事件类型"""
    EMISSION_REDUCTION = "emission_reduction"      # E - 减排承诺
    RENEWABLE_ENERGY = "renewable_energy"          # E - 可再生能源
    WATER_MANAGEMENT = "water_management"          # E - 水资源管理
    SAFETY_INCIDENT = "safety_incident"            # S - 安全事故
    DIVERSITY_INITIATIVE = "diversity_initiative"  # S - 多样性计划
    COMMUNITY_ENGAGEMENT = "community_engagement"  # S - 社区参与
    GOVERNANCE_CHANGE = "governance_change"        # G - 治理变革
    COMPLIANCE_VIOLATION = "compliance_violation"  # G - 合规违规
    CORRUPTION_ALLEGATION = "corruption_allegation"# G - 腐败指控
    OTHER = "other"


class RiskLevel(str, Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ESGEvent(BaseModel):
    """ESG 事件（扫描到的原始信息）"""
    id: Optional[str] = None
    title: str                          # 事件标题
    description: str                    # 事件描述
    company: str                        # 相关公司
    event_type: ESGEventType            # 事件类型
    source: str                         # 数据来源（如：API、新闻、报告）
    source_url: Optional[str] = None    # 源链接
    detected_at: datetime               # 检测时间
    raw_content: str                    # 原始内容（用于后续分析）

    class Config:
        use_enum_values = True


class ExtractedEvent(BaseModel):
    """提取后的结构化事件"""
    id: Optional[str] = None
    original_event_id: str              # 关联的原始事件
    title: str
    description: str
    company: str
    event_type: ESGEventType
    key_metrics: dict                   # 关键指标 {"carbon_reduction": "30%", ...}
    impact_area: str                    # 影响领域（E/S/G）
    severity: RiskLevel                 # 严重程度（初步评估）
    created_at: datetime

    class Config:
        use_enum_values = True


# ── 用户偏好模型 ──────────────────────────────────────────────────────────

class UserPreference(BaseModel):
    """用户的 ESG 关注偏好"""
    id: Optional[str] = None
    user_id: str
    interested_companies: list[str]     # 关注的公司清单
    interested_categories: list[str]    # 关注的 ESG 类别 ["E", "S", "G"]
    risk_threshold: RiskLevel           # 仅推送高于该风险等级的事件
    keywords: list[str]                 # 关键词过滤（任意关键词命中则推送）
    notification_channels: list[str]    # 推送渠道 ["email", "in_app", "webhook"]
    created_at: datetime
    updated_at: datetime


# ── 风险评分模型 ──────────────────────────────────────────────────────────

class RiskScore(BaseModel):
    """AI 风险评分结果"""
    id: Optional[str] = None
    event_id: str                       # 关联的事件 ID
    risk_level: RiskLevel               # 风险等级
    score: float                        # 风险分数 0.0-100.0
    reasoning: str                      # 打分理由
    affected_dimensions: dict           # 受影响的 ESG 维度及权重
    {"environmental": 0.6, "social": 0.3, "governance": 0.1}
    recommendation: str                 # 建议操作
    created_at: datetime

    class Config:
        use_enum_values = True


# ── 通知记录模型 ──────────────────────────────────────────────────────────

class Notification(BaseModel):
    """推送给用户的通知"""
    id: Optional[str] = None
    user_id: str
    event_id: str
    title: str
    content: str
    severity: RiskLevel
    channels: list[str]                 # 推送渠道
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    status: str                         # "pending", "sent", "failed"

    class Config:
        use_enum_values = True


# ── 扫描任务状态 ──────────────────────────────────────────────────────────

class ScanJob(BaseModel):
    """扫描任务的执行记录"""
    id: Optional[str] = None
    job_type: str                       # "news", "reports", "updates"
    status: str                         # "running", "completed", "failed"
    started_at: datetime
    completed_at: Optional[datetime] = None
    events_found: int
    errors: Optional[list[str]] = None
    last_cursor: Optional[str] = None   # 分页游标，用于下次扫描的断点续传


# ── ESG 报告相关模型 ────────────────────────────────────────────────────────

class ESGReport(BaseModel):
    """ESG 报告"""
    id: Optional[str] = None
    report_type: str                    # "daily", "weekly", "monthly"
    title: str
    period_start: datetime
    period_end: datetime
    data: dict                          # 完整报告数据（JSON）
    generated_at: datetime
    created_at: datetime = None


class CompanyDataSnapshot(BaseModel):
    """企业数据快照（缓存）"""
    id: Optional[str] = None
    company_name: str
    ticker: Optional[str] = None
    industry: Optional[str] = None
    esg_score_report: dict              # ESG评分报告（JSON）
    financial_metrics: dict             # 财务指标（JSON）
    external_ratings: dict              # 外部评分（JSON）
    snapshot_date: str                  # YYYY-MM-DD
    last_updated: datetime


class ReportPushHistory(BaseModel):
    """报告推送历史"""
    id: Optional[str] = None
    report_id: str
    user_id: str
    push_channels: list[str]
    push_status: str                    # "sent", "failed", "pending"
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    click_through: bool = False
    feedback_score: Optional[int] = None  # 1-5
    created_at: datetime = None


class PushRule(BaseModel):
    """推送规则"""
    id: Optional[str] = None
    rule_name: str
    condition: str                      # Python表达式
    target_users: str                   # "all", "holders", "followers", "analysts"
    push_channels: list[str]
    priority: int
    template_id: str
    enabled: bool = True
    created_at: datetime = None
    updated_at: datetime = None


class UserReportSubscription(BaseModel):
    """用户报告订阅"""
    id: Optional[str] = None
    user_id: str
    report_types: list[str]             # ["daily", "weekly", "monthly"]
    companies: list[str]
    alert_threshold: dict               # {"esg_score": 40, "change": -5}
    push_channels: list[str]
    frequency: str                      # "immediate", "daily", "weekly"
    subscribed_at: datetime
    updated_at: datetime = None
