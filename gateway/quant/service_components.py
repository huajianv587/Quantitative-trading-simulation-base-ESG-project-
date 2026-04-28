from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class MarketDataComponent:
    owner: Any

    def daily_bars(self, symbol: str, **kwargs):
        return self.owner._get_daily_bars(symbol, **kwargs)

    def status(self) -> dict[str, Any]:
        return self.owner.market_data.status()


@dataclass
class DashboardComponent:
    owner: Any

    def overview(self) -> dict[str, Any]:
        return self.owner.build_platform_overview()

    def summary(self, provider: str = "auto") -> dict[str, Any]:
        return self.owner.build_dashboard_summary(provider=provider)

    def secondary(self, provider: str = "auto") -> dict[str, Any]:
        return self.owner.build_dashboard_secondary(provider=provider)

    def chart(self, *, symbol: str | None = None, timeframe: str = "1D", provider: str = "auto") -> dict[str, Any]:
        return self.owner.build_dashboard_chart(symbol=symbol, timeframe=timeframe, provider=provider)


@dataclass
class ExecutionComponent:
    owner: Any

    def create_plan(self, **kwargs) -> dict[str, Any]:
        return self.owner.create_execution_plan(**kwargs)

    def controls(self) -> dict[str, Any]:
        return self.owner.get_execution_controls()

    def monitor(self, **kwargs) -> dict[str, Any]:
        return self.owner.build_execution_monitor(**kwargs)


@dataclass
class PaperWorkflowComponent:
    owner: Any

    def run_strategy_workflow(self, **kwargs) -> dict[str, Any]:
        return self.owner.run_hybrid_paper_strategy_workflow(**kwargs)

    def performance_report(self, **kwargs) -> dict[str, Any]:
        return self.owner.build_paper_performance_report(**kwargs)

    def promotion_report(self, **kwargs) -> dict[str, Any]:
        return self.owner.build_promotion_report(**kwargs)

    def observability(self, **kwargs) -> dict[str, Any]:
        return self.owner.build_paper_workflow_observability(**kwargs)


@dataclass
class QuantServiceComponents:
    market_data: MarketDataComponent
    dashboard: DashboardComponent
    execution: ExecutionComponent
    paper_workflow: PaperWorkflowComponent

    @classmethod
    def from_owner(cls, owner: Any) -> "QuantServiceComponents":
        return cls(
            market_data=MarketDataComponent(owner),
            dashboard=DashboardComponent(owner),
            execution=ExecutionComponent(owner),
            paper_workflow=PaperWorkflowComponent(owner),
        )
