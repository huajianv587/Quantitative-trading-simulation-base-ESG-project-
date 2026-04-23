from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ESGEventType(str, Enum):
    EMISSION_REDUCTION = "emission_reduction"
    RENEWABLE_ENERGY = "renewable_energy"
    WATER_MANAGEMENT = "water_management"
    SAFETY_INCIDENT = "safety_incident"
    DIVERSITY_INITIATIVE = "diversity_initiative"
    COMMUNITY_ENGAGEMENT = "community_engagement"
    GOVERNANCE_CHANGE = "governance_change"
    COMPLIANCE_VIOLATION = "compliance_violation"
    CORRUPTION_ALLEGATION = "corruption_allegation"
    OTHER = "other"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class _EnumValueModel(BaseModel):
    model_config = ConfigDict(use_enum_values=True)


class ESGEvent(_EnumValueModel):
    id: Optional[str] = None
    title: str
    description: str
    company: str
    event_type: ESGEventType
    source: str
    source_url: Optional[str] = None
    detected_at: datetime
    raw_content: str


class ExtractedEvent(_EnumValueModel):
    id: Optional[str] = None
    original_event_id: str
    title: str
    description: str
    company: str
    event_type: ESGEventType
    key_metrics: dict[str, Any] = Field(default_factory=dict)
    impact_area: str
    severity: RiskLevel
    created_at: datetime


class UserPreference(BaseModel):
    id: Optional[str] = None
    user_id: str
    interested_companies: list[str] = Field(default_factory=list)
    interested_categories: list[str] = Field(default_factory=list)
    risk_threshold: RiskLevel
    keywords: list[str] = Field(default_factory=list)
    notification_channels: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class RiskScore(_EnumValueModel):
    id: Optional[str] = None
    event_id: str
    risk_level: RiskLevel
    score: float
    reasoning: str
    affected_dimensions: dict[str, float] = Field(default_factory=dict)
    recommendation: str
    created_at: datetime


class Notification(_EnumValueModel):
    id: Optional[str] = None
    user_id: str
    event_id: str
    title: str
    content: str
    severity: RiskLevel
    channels: list[str] = Field(default_factory=list)
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    status: str


class ScanJob(BaseModel):
    id: Optional[str] = None
    job_type: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    events_found: int
    events_saved: int = 0
    errors: Optional[list[str]] = None
    last_cursor: Optional[str] = None
    source_summary: dict[str, Any] = Field(default_factory=dict)
    blocked_reason: Optional[str] = None
    next_actions: list[str] = Field(default_factory=list)
    checkpoint_state: dict[str, Any] = Field(default_factory=dict)


class SchedulerBlockedState(BaseModel):
    status: str = "blocked"
    block_reason: str
    next_actions: list[str] = Field(default_factory=list)


class ScanSourceState(BaseModel):
    lane: str
    source_key: str
    company_key: str
    checkpoint_value: dict[str, Any] = Field(default_factory=dict)
    last_status: str = "idle"
    blocked_reason: Optional[str] = None
    events_found: int = 0
    events_saved: int = 0
    updated_at: Optional[datetime] = None


class ScanLaneResult(BaseModel):
    lane: str
    status: str
    events_found: int = 0
    events_saved: int = 0
    source_status: dict[str, Any] = Field(default_factory=dict)
    blocked_reason: Optional[str] = None
    next_actions: list[str] = Field(default_factory=list)
    checkpoint: dict[str, Any] = Field(default_factory=dict)


class TrackedCompanyUniverse(BaseModel):
    tracked_companies: list[str] = Field(default_factory=list)
    portfolio_companies: list[str] = Field(default_factory=list)
    blocked_reason: Optional[str] = None
    next_actions: list[str] = Field(default_factory=list)


class ESGReport(BaseModel):
    id: Optional[str] = None
    report_type: str
    title: str
    period_start: datetime
    period_end: datetime
    data: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime
    created_at: Optional[datetime] = None


class CompanyDataSnapshot(BaseModel):
    id: Optional[str] = None
    company_name: str
    ticker: Optional[str] = None
    industry: Optional[str] = None
    esg_score_report: dict[str, Any] = Field(default_factory=dict)
    financial_metrics: dict[str, Any] = Field(default_factory=dict)
    external_ratings: dict[str, Any] = Field(default_factory=dict)
    snapshot_date: str
    last_updated: datetime


class ReportPushHistory(BaseModel):
    id: Optional[str] = None
    report_id: str
    user_id: str
    push_channels: list[str] = Field(default_factory=list)
    push_status: str
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    click_through: bool = False
    feedback_score: Optional[int] = None
    created_at: Optional[datetime] = None


class PushRule(BaseModel):
    id: Optional[str] = None
    rule_name: str
    condition: str
    target_users: str
    push_channels: list[str] = Field(default_factory=list)
    priority: int
    template_id: str
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserReportSubscription(BaseModel):
    id: Optional[str] = None
    user_id: str
    report_types: list[str] = Field(default_factory=list)
    companies: list[str] = Field(default_factory=list)
    alert_threshold: dict[str, Any] = Field(default_factory=dict)
    push_channels: list[str] = Field(default_factory=list)
    frequency: str
    subscribed_at: datetime
    updated_at: Optional[datetime] = None
