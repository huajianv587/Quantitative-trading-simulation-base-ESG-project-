from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class QueryRequest(BaseModel):
    session_id: str
    question: str


class QueryResponse(BaseModel):
    session_id: str
    question: str
    answer: str


class AnalyzeRequest(BaseModel):
    session_id: str = ""
    question: str


class ESGScoreRequest(BaseModel):
    company: str
    ticker: Optional[str] = None
    include_visualization: bool = True
    peers: Optional[List[str]] = None
    historical_data: bool = False


class ReportGenerateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    report_type: str
    companies: List[str]
    async_: bool = Field(default=True, alias="async")
    include_peer_comparison: bool = False


class DataSyncRequest(BaseModel):
    sources: Optional[List[str]] = None
    companies: List[str]
    force_refresh: bool = False


class CreatePushRuleRequest(BaseModel):
    rule_name: str
    condition: str
    target_users: str
    push_channels: List[str]
    priority: int
    template_id: str


class UserReportSubscribeRequest(BaseModel):
    report_types: List[str]
    companies: List[str]
    alert_threshold: Optional[Dict[str, Any]] = None
    push_channels: List[str]
    frequency: str = "daily"


class PushRuleTestRequest(BaseModel):
    test_user_id: str
    mock_report: Dict[str, Any]
