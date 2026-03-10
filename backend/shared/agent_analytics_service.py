"""
Agent Analytics Service

Provides cost tracking, usage analytics, and reporting for AI agents.
Supports team-level, category-level, and agent-level analysis.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import uuid4
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from pydantic import BaseModel

from backend.shared.agent_registry_models import (
    AgentRegistry, AgentUsageLog
)

logger = logging.getLogger(__name__)


class CostBreakdown(BaseModel):
    """Cost breakdown by dimension"""
    dimension: str  # team, category, agent, user
    dimension_value: str
    agent_count: int
    total_cost_usd: float
    total_executions: int
    avg_cost_per_execution: float
    avg_response_time_ms: Optional[int]
    success_rate: Optional[float]


class AgentCostAnalytics(BaseModel):
    """Detailed cost analytics for an agent"""
    agent_id: str
    agent_name: str
    category: Optional[str]
    owner_team_id: Optional[str]
    total_cost_usd: float
    total_executions: int
    cost_per_execution: float
    avg_response_time_ms: Optional[int]
    success_rate: Optional[float]
    last_30_days_cost: float
    last_7_days_cost: float
    cost_trend: str  # increasing, decreasing, stable


class UsageLogEntry(BaseModel):
    """Individual usage log entry"""
    log_id: str
    agent_id: str
    agent_name: str
    execution_id: str
    user_id: str
    team_id: Optional[str]
    execution_time_ms: int
    tokens_used: int
    cost_usd: float
    success: bool
    data_sources_accessed: Optional[List[str]]
    pii_accessed: bool
    executed_at: datetime

    class Config:
        from_attributes = True


class AgentAnalyticsService:
    """
    Agent Analytics Service

    Features:
    - Cost tracking and reporting
    - Usage analytics by team, category, agent
    - Trend analysis
    - Top spenders identification
    - PII access auditing
    - Custom time-range reports
    """

    def __init__(self):
        pass

    async def log_agent_usage(
        self,
        agent_id: str,
        execution_id: str,
        user_id: str,
        team_id: Optional[str],
        execution_time_ms: int,
        tokens_used: int,
        cost_usd: Decimal,
        success: bool,
        data_sources_accessed: Optional[List[str]],
        pii_accessed: bool,
        db: AsyncSession
    ) -> UsageLogEntry:
        """
        Log agent execution for analytics.

        Args:
            agent_id: Agent that was executed
            execution_id: Workflow execution ID
            user_id: User who triggered execution
            team_id: Team ID (optional)
            execution_time_ms: Execution time in milliseconds
            tokens_used: Number of LLM tokens used
            cost_usd: Execution cost in USD
            success: Whether execution succeeded
            data_sources_accessed: List of data sources accessed
            pii_accessed: Whether PII was accessed
            db: Database session

        Returns:
            Logged usage entry
        """
        # Get agent name
        agent_stmt = select(AgentRegistry).where(AgentRegistry.agent_id == agent_id)
        agent_result = await db.execute(agent_stmt)
        agent = agent_result.scalar_one_or_none()

        if not agent:
            logger.warning(f"Agent '{agent_id}' not found for usage logging")
            agent_name = "Unknown"
        else:
            agent_name = agent.name

        # Create usage log
        log_entry = AgentUsageLog(
            log_id=str(uuid4())[:16],
            agent_id=agent_id,
            execution_id=execution_id,
            user_id=user_id,
            team_id=team_id,
            execution_time_ms=execution_time_ms,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            success=success,
            data_sources_accessed=data_sources_accessed,
            pii_accessed=pii_accessed,
            executed_at=datetime.now()
        )

        db.add(log_entry)
        await db.commit()
        await db.refresh(log_entry)

        return UsageLogEntry(
            log_id=log_entry.log_id,
            agent_id=log_entry.agent_id,
            agent_name=agent_name,
            execution_id=log_entry.execution_id,
            user_id=log_entry.user_id,
            team_id=log_entry.team_id,
            execution_time_ms=log_entry.execution_time_ms,
            tokens_used=log_entry.tokens_used,
            cost_usd=float(log_entry.cost_usd),
            success=log_entry.success,
            data_sources_accessed=log_entry.data_sources_accessed,
            pii_accessed=log_entry.pii_accessed,
            executed_at=log_entry.executed_at
        )

    async def get_cost_by_team(
        self,
        organization_id: str,
        db: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[CostBreakdown]:
        """Get cost breakdown by team"""
        stmt = select(
            AgentRegistry.owner_team_id.label("team_id"),
            func.count(func.distinct(AgentRegistry.agent_id)).label("agent_count"),
            func.sum(AgentRegistry.total_cost_usd).label("total_cost"),
            func.sum(AgentRegistry.total_executions).label("total_executions"),
            func.avg(AgentRegistry.avg_response_time_ms).label("avg_response_time"),
            func.avg(AgentRegistry.success_rate).label("avg_success_rate")
        ).where(
            AgentRegistry.organization_id == organization_id
        ).group_by(AgentRegistry.owner_team_id).order_by(desc("total_cost"))

        result = await db.execute(stmt)
        rows = result.all()

        breakdowns = []
        for row in rows:
            team_id = row.team_id or "unassigned"
            total_cost = float(row.total_cost or 0)
            total_executions = row.total_executions or 0
            avg_cost_per_exec = total_cost / total_executions if total_executions > 0 else 0

            breakdowns.append(CostBreakdown(
                dimension="team",
                dimension_value=team_id,
                agent_count=row.agent_count,
                total_cost_usd=total_cost,
                total_executions=total_executions,
                avg_cost_per_execution=avg_cost_per_exec,
                avg_response_time_ms=row.avg_response_time,
                success_rate=float(row.avg_success_rate) if row.avg_success_rate else None
            ))

        return breakdowns

    async def get_cost_by_category(
        self,
        organization_id: str,
        db: AsyncSession
    ) -> List[CostBreakdown]:
        """Get cost breakdown by agent category"""
        stmt = select(
            AgentRegistry.category.label("category"),
            func.count(AgentRegistry.agent_id).label("agent_count"),
            func.sum(AgentRegistry.total_cost_usd).label("total_cost"),
            func.sum(AgentRegistry.total_executions).label("total_executions"),
            func.avg(AgentRegistry.avg_response_time_ms).label("avg_response_time"),
            func.avg(AgentRegistry.success_rate).label("avg_success_rate")
        ).where(
            AgentRegistry.organization_id == organization_id
        ).group_by(AgentRegistry.category).order_by(desc("total_cost"))

        result = await db.execute(stmt)
        rows = result.all()

        breakdowns = []
        for row in rows:
            category = row.category or "uncategorized"
            total_cost = float(row.total_cost or 0)
            total_executions = row.total_executions or 0
            avg_cost_per_exec = total_cost / total_executions if total_executions > 0 else 0

            breakdowns.append(CostBreakdown(
                dimension="category",
                dimension_value=category,
                agent_count=row.agent_count,
                total_cost_usd=total_cost,
                total_executions=total_executions,
                avg_cost_per_execution=avg_cost_per_exec,
                avg_response_time_ms=row.avg_response_time,
                success_rate=float(row.avg_success_rate) if row.avg_success_rate else None
            ))

        return breakdowns

    async def get_top_expensive_agents(
        self,
        organization_id: str,
        db: AsyncSession,
        limit: int = 10
    ) -> List[AgentCostAnalytics]:
        """Get top N most expensive agents"""
        stmt = select(AgentRegistry).where(
            AgentRegistry.organization_id == organization_id
        ).order_by(desc(AgentRegistry.total_cost_usd)).limit(limit)

        result = await db.execute(stmt)
        agents = result.scalars().all()

        analytics = []
        for agent in agents:
            # Calculate recent costs
            last_30_days_cost = await self._get_agent_cost_for_period(
                agent.agent_id,
                days=30,
                db=db
            )
            last_7_days_cost = await self._get_agent_cost_for_period(
                agent.agent_id,
                days=7,
                db=db
            )

            # Determine cost trend
            cost_trend = self._determine_cost_trend(
                last_7_days_cost,
                last_30_days_cost,
                float(agent.total_cost_usd)
            )

            cost_per_exec = (
                float(agent.total_cost_usd) / agent.total_executions
                if agent.total_executions > 0 else 0
            )

            analytics.append(AgentCostAnalytics(
                agent_id=agent.agent_id,
                agent_name=agent.name,
                category=agent.category,
                owner_team_id=agent.owner_team_id,
                total_cost_usd=float(agent.total_cost_usd),
                total_executions=agent.total_executions,
                cost_per_execution=cost_per_exec,
                avg_response_time_ms=agent.avg_response_time_ms,
                success_rate=float(agent.success_rate) if agent.success_rate else None,
                last_30_days_cost=last_30_days_cost,
                last_7_days_cost=last_7_days_cost,
                cost_trend=cost_trend
            ))

        return analytics

    async def get_agent_usage_logs(
        self,
        agent_id: str,
        db: AsyncSession,
        limit: int = 100,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[UsageLogEntry]:
        """Get usage logs for specific agent"""
        stmt = select(AgentUsageLog).where(AgentUsageLog.agent_id == agent_id)

        if start_date:
            stmt = stmt.where(AgentUsageLog.executed_at >= start_date)
        if end_date:
            stmt = stmt.where(AgentUsageLog.executed_at <= end_date)

        stmt = stmt.order_by(desc(AgentUsageLog.executed_at)).limit(limit)

        result = await db.execute(stmt)
        logs = result.scalars().all()

        # Get agent name
        agent_stmt = select(AgentRegistry).where(AgentRegistry.agent_id == agent_id)
        agent_result = await db.execute(agent_stmt)
        agent = agent_result.scalar_one_or_none()
        agent_name = agent.name if agent else "Unknown"

        return [
            UsageLogEntry(
                log_id=log.log_id,
                agent_id=log.agent_id,
                agent_name=agent_name,
                execution_id=log.execution_id,
                user_id=log.user_id,
                team_id=log.team_id,
                execution_time_ms=log.execution_time_ms,
                tokens_used=log.tokens_used,
                cost_usd=float(log.cost_usd),
                success=log.success,
                data_sources_accessed=log.data_sources_accessed,
                pii_accessed=log.pii_accessed,
                executed_at=log.executed_at
            )
            for log in logs
        ]

    async def get_pii_access_audit(
        self,
        organization_id: str,
        db: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[UsageLogEntry]:
        """Get audit trail of PII access"""
        # Get agents for this organization
        agent_stmt = select(AgentRegistry.agent_id).where(
            AgentRegistry.organization_id == organization_id
        )
        agent_result = await db.execute(agent_stmt)
        agent_ids = [row[0] for row in agent_result.all()]

        # Get PII access logs
        stmt = select(AgentUsageLog).where(
            and_(
                AgentUsageLog.agent_id.in_(agent_ids),
                AgentUsageLog.pii_accessed == True
            )
        )

        if start_date:
            stmt = stmt.where(AgentUsageLog.executed_at >= start_date)
        if end_date:
            stmt = stmt.where(AgentUsageLog.executed_at <= end_date)

        stmt = stmt.order_by(desc(AgentUsageLog.executed_at)).limit(limit)

        result = await db.execute(stmt)
        logs = result.scalars().all()

        # Get agent names
        agent_names = {}
        for log in logs:
            if log.agent_id not in agent_names:
                agent_stmt = select(AgentRegistry).where(AgentRegistry.agent_id == log.agent_id)
                agent_result = await db.execute(agent_stmt)
                agent = agent_result.scalar_one_or_none()
                agent_names[log.agent_id] = agent.name if agent else "Unknown"

        return [
            UsageLogEntry(
                log_id=log.log_id,
                agent_id=log.agent_id,
                agent_name=agent_names.get(log.agent_id, "Unknown"),
                execution_id=log.execution_id,
                user_id=log.user_id,
                team_id=log.team_id,
                execution_time_ms=log.execution_time_ms,
                tokens_used=log.tokens_used,
                cost_usd=float(log.cost_usd),
                success=log.success,
                data_sources_accessed=log.data_sources_accessed,
                pii_accessed=log.pii_accessed,
                executed_at=log.executed_at
            )
            for log in logs
        ]

    async def _get_agent_cost_for_period(
        self,
        agent_id: str,
        days: int,
        db: AsyncSession
    ) -> float:
        """Get agent cost for the last N days"""
        cutoff_date = datetime.now() - timedelta(days=days)

        stmt = select(func.sum(AgentUsageLog.cost_usd)).where(
            and_(
                AgentUsageLog.agent_id == agent_id,
                AgentUsageLog.executed_at >= cutoff_date
            )
        )

        result = await db.execute(stmt)
        total_cost = result.scalar()

        return float(total_cost) if total_cost else 0.0

    def _determine_cost_trend(
        self,
        last_7_days_cost: float,
        last_30_days_cost: float,
        total_cost: float
    ) -> str:
        """Determine cost trend (increasing, decreasing, stable)"""
        if last_7_days_cost == 0 or last_30_days_cost == 0:
            return "stable"

        # Calculate weekly average
        weekly_avg_from_30_days = last_30_days_cost / 4.0
        recent_weekly_cost = last_7_days_cost

        # Compare recent week to average
        if recent_weekly_cost > weekly_avg_from_30_days * 1.2:
            return "increasing"
        elif recent_weekly_cost < weekly_avg_from_30_days * 0.8:
            return "decreasing"
        else:
            return "stable"


# Singleton instance
_agent_analytics_service: Optional[AgentAnalyticsService] = None


def get_agent_analytics_service() -> AgentAnalyticsService:
    """Get singleton AgentAnalyticsService instance"""
    global _agent_analytics_service
    if _agent_analytics_service is None:
        _agent_analytics_service = AgentAnalyticsService()
    return _agent_analytics_service
