"""
Agent Policy Service

Policy enforcement engine for agent governance.
Enforces cost caps, data access rules, compliance policies, and retention policies.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import uuid4
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from backend.shared.agent_registry_models import (
    AgentRegistry, AgentPolicy,
    PolicyType, EnforcementLevel,
    PolicyCreate, PolicyResponse
)
from backend.shared.audit_logger import get_audit_logger
from backend.shared.audit_models import AuditEventType, AuditSeverity

logger = logging.getLogger(__name__)


class PolicyViolation(Exception):
    """Exception raised when policy is violated"""
    def __init__(self, policy_name: str, message: str, details: Dict[str, Any]):
        self.policy_name = policy_name
        self.message = message
        self.details = details
        super().__init__(f"Policy violation: {policy_name} - {message}")


class AgentPolicyService:
    """
    Agent Policy Service

    Features:
    - Cost cap enforcement
    - Data access restrictions
    - Approval requirements
    - Retention policies
    - Compliance rules
    - Automatic violation detection
    """

    def __init__(self):
        try:
            self.audit_logger = get_audit_logger()
        except RuntimeError:
            # Audit logger not initialized (demo mode)
            self.audit_logger = None

    async def create_policy(
        self,
        policy_data: PolicyCreate,
        organization_id: str,
        created_by: str,
        db: AsyncSession
    ) -> PolicyResponse:
        """
        Create a new governance policy.

        Args:
            policy_data: Policy configuration
            organization_id: Organization ID
            created_by: User creating the policy
            db: Database session

        Returns:
            Created policy
        """
        logger.info(f"Creating policy: {policy_data.policy_name}")

        # Validate policy rules based on type
        self._validate_policy_rules(policy_data.policy_type, policy_data.rules)

        # Create policy
        policy = AgentPolicy(
            policy_id=policy_data.policy_id,
            organization_id=organization_id,
            policy_name=policy_data.policy_name,
            description=policy_data.description,
            policy_type=policy_data.policy_type,
            applies_to=policy_data.applies_to,
            scope_value=policy_data.scope_value,
            rules=policy_data.rules,
            enforcement_level=policy_data.enforcement_level,
            violations_count=0,
            created_by=created_by,
            created_at=datetime.now(),
            is_active=True
        )

        db.add(policy)
        await db.commit()
        await db.refresh(policy)

        # Audit log
        if self.audit_logger:
            await self.audit_logger.log_event(
            event_type=AuditEventType.POLICY_CREATED,
            user_id=created_by,
            organization_id=organization_id,
            resource_type="agent_policy",
            resource_id=policy.policy_id,
            details={
                "policy_name": policy.policy_name,
                "policy_type": policy.policy_type,
                "enforcement_level": policy.enforcement_level,
                "applies_to": policy.applies_to
            },
            severity=AuditSeverity.INFO,
            db=db
        )

        logger.info(f"✓ Policy created: {policy.policy_id}")
        return self._to_response(policy)

    async def check_agent_compliance(
        self,
        agent_id: str,
        db: AsyncSession,
        action: Optional[str] = None
    ) -> List[PolicyResponse]:
        """
        Check if agent complies with all applicable policies.

        Args:
            agent_id: Agent to check
            db: Database session
            action: Optional specific action being validated

        Returns:
            List of violated policies

        Raises:
            PolicyViolation: If policy is violated and enforcement is blocking
        """
        # Get agent
        agent_stmt = select(AgentRegistry).where(AgentRegistry.agent_id == agent_id)
        agent_result = await db.execute(agent_stmt)
        agent = agent_result.scalar_one_or_none()

        if not agent:
            raise ValueError(f"Agent '{agent_id}' not found")

        # Get applicable policies
        policies = await self._get_applicable_policies(agent, db)

        violations = []
        for policy in policies:
            is_compliant, violation_details = await self._check_policy(agent, policy, db)

            if not is_compliant:
                # Record violation
                policy.violations_count += 1
                await db.commit()

                # Audit log
                await self.audit_logger.log_event(
                    event_type=AuditEventType.POLICY_VIOLATED,
                    user_id=agent.owner_user_id,
                    organization_id=agent.organization_id,
                    resource_type="agent",
                    resource_id=agent.agent_id,
                    details={
                        "policy_id": policy.policy_id,
                        "policy_name": policy.policy_name,
                        "violation_details": violation_details
                    },
                    severity=AuditSeverity.WARNING,
                    db=db
                )

                violations.append(policy)

                # If blocking enforcement, raise exception
                if policy.enforcement_level == EnforcementLevel.BLOCKING:
                    raise PolicyViolation(
                        policy_name=policy.policy_name,
                        message=f"Agent '{agent.name}' violates policy",
                        details=violation_details
                    )

        return [self._to_response(policy) for policy in violations]

    async def get_policy(
        self,
        policy_id: str,
        db: AsyncSession
    ) -> Optional[PolicyResponse]:
        """Get policy by ID"""
        stmt = select(AgentPolicy).where(AgentPolicy.policy_id == policy_id)
        result = await db.execute(stmt)
        policy = result.scalar_one_or_none()

        if not policy:
            return None

        return self._to_response(policy)

    async def get_organization_policies(
        self,
        organization_id: str,
        db: AsyncSession,
        active_only: bool = True
    ) -> List[PolicyResponse]:
        """Get all policies for organization"""
        stmt = select(AgentPolicy).where(
            AgentPolicy.organization_id == organization_id
        )

        if active_only:
            stmt = stmt.where(AgentPolicy.is_active == True)

        stmt = stmt.order_by(AgentPolicy.created_at.desc())

        result = await db.execute(stmt)
        policies = result.scalars().all()

        return [self._to_response(policy) for policy in policies]

    async def update_policy(
        self,
        policy_id: str,
        rules: Dict[str, Any],
        enforcement_level: Optional[str],
        db: AsyncSession,
        updated_by: str
    ) -> PolicyResponse:
        """Update policy rules or enforcement level"""
        stmt = select(AgentPolicy).where(AgentPolicy.policy_id == policy_id)
        result = await db.execute(stmt)
        policy = result.scalar_one_or_none()

        if not policy:
            raise ValueError(f"Policy '{policy_id}' not found")

        # Validate new rules
        self._validate_policy_rules(policy.policy_type, rules)

        policy.rules = rules
        if enforcement_level:
            policy.enforcement_level = enforcement_level
        policy.updated_at = datetime.now()

        await db.commit()
        await db.refresh(policy)

        # Audit log
        if self.audit_logger:
            await self.audit_logger.log_event(
            event_type=AuditEventType.POLICY_UPDATED,
            user_id=updated_by,
            organization_id=policy.organization_id,
            resource_type="agent_policy",
            resource_id=policy.policy_id,
            details={
                "policy_name": policy.policy_name,
                "new_rules": rules,
                "enforcement_level": enforcement_level
            },
            severity=AuditSeverity.INFO,
            db=db
        )

        return self._to_response(policy)

    async def deactivate_policy(
        self,
        policy_id: str,
        db: AsyncSession,
        deactivated_by: str
    ) -> None:
        """Deactivate a policy"""
        stmt = select(AgentPolicy).where(AgentPolicy.policy_id == policy_id)
        result = await db.execute(stmt)
        policy = result.scalar_one_or_none()

        if not policy:
            raise ValueError(f"Policy '{policy_id}' not found")

        policy.is_active = False
        policy.updated_at = datetime.now()

        await db.commit()

        # Audit log
        if self.audit_logger:
            await self.audit_logger.log_event(
            event_type=AuditEventType.POLICY_DELETED,
            user_id=deactivated_by,
            organization_id=policy.organization_id,
            resource_type="agent_policy",
            resource_id=policy.policy_id,
            details={"policy_name": policy.policy_name},
            severity=AuditSeverity.WARNING,
            db=db
        )

    async def _get_applicable_policies(
        self,
        agent: AgentRegistry,
        db: AsyncSession
    ) -> List[AgentPolicy]:
        """Get all policies that apply to this agent"""
        stmt = select(AgentPolicy).where(
            and_(
                AgentPolicy.organization_id == agent.organization_id,
                AgentPolicy.is_active == True,
                or_(
                    AgentPolicy.applies_to == "all_agents",
                    and_(
                        AgentPolicy.applies_to == "team",
                        AgentPolicy.scope_value == agent.owner_team_id
                    ),
                    and_(
                        AgentPolicy.applies_to == "category",
                        AgentPolicy.scope_value == agent.category
                    ),
                    and_(
                        AgentPolicy.applies_to == "specific_agent",
                        AgentPolicy.scope_value == agent.agent_id
                    )
                )
            )
        )

        result = await db.execute(stmt)
        return result.scalars().all()

    async def _check_policy(
        self,
        agent: AgentRegistry,
        policy: AgentPolicy,
        db: AsyncSession
    ) -> tuple[bool, Dict[str, Any]]:
        """
        Check if agent complies with specific policy.

        Returns:
            (is_compliant, violation_details)
        """
        if policy.policy_type == PolicyType.COST_CAP:
            return self._check_cost_cap_policy(agent, policy)

        elif policy.policy_type == PolicyType.DATA_ACCESS:
            return self._check_data_access_policy(agent, policy)

        elif policy.policy_type == PolicyType.APPROVAL_REQUIRED:
            return self._check_approval_policy(agent, policy)

        elif policy.policy_type == PolicyType.RETENTION:
            return self._check_retention_policy(agent, policy)

        elif policy.policy_type == PolicyType.COMPLIANCE:
            return self._check_compliance_policy(agent, policy)

        else:
            logger.warning(f"Unknown policy type: {policy.policy_type}")
            return True, {}

    def _check_cost_cap_policy(
        self,
        agent: AgentRegistry,
        policy: AgentPolicy
    ) -> tuple[bool, Dict[str, Any]]:
        """Check cost cap policy"""
        max_cost = Decimal(str(policy.rules.get("max_cost_per_month_usd", 0)))

        if agent.total_cost_usd > max_cost:
            return False, {
                "current_cost": float(agent.total_cost_usd),
                "max_cost": float(max_cost),
                "overage": float(agent.total_cost_usd - max_cost)
            }

        return True, {}

    def _check_data_access_policy(
        self,
        agent: AgentRegistry,
        policy: AgentPolicy
    ) -> tuple[bool, Dict[str, Any]]:
        """Check data access policy"""
        allowed_sources = set(policy.rules.get("allowed_data_sources", []))
        agent_sources = set(agent.data_sources_allowed or [])

        # Check if agent accesses any disallowed sources
        disallowed = agent_sources - allowed_sources

        if disallowed:
            return False, {
                "disallowed_sources": list(disallowed),
                "allowed_sources": list(allowed_sources)
            }

        return True, {}

    def _check_approval_policy(
        self,
        agent: AgentRegistry,
        policy: AgentPolicy
    ) -> tuple[bool, Dict[str, Any]]:
        """Check approval requirement policy"""
        requires_approval = policy.rules.get("require_approval", False)

        if requires_approval and not agent.approved_by:
            return False, {
                "reason": "Agent requires approval but is not approved"
            }

        return True, {}

    def _check_retention_policy(
        self,
        agent: AgentRegistry,
        policy: AgentPolicy
    ) -> tuple[bool, Dict[str, Any]]:
        """Check data retention policy"""
        # Check if agent has been inactive for too long
        max_inactive_days = policy.rules.get("max_inactive_days", 90)

        if agent.last_active_at:
            days_inactive = (datetime.now() - agent.last_active_at).days
            if days_inactive > max_inactive_days:
                return False, {
                    "days_inactive": days_inactive,
                    "max_allowed": max_inactive_days,
                    "last_active": agent.last_active_at.isoformat()
                }

        return True, {}

    def _check_compliance_policy(
        self,
        agent: AgentRegistry,
        policy: AgentPolicy
    ) -> tuple[bool, Dict[str, Any]]:
        """Check compliance policy (e.g., HIPAA, SOC 2)"""
        # Check if agent accessing PII has proper sensitivity classification
        required_sensitivity = policy.rules.get("required_sensitivity_for_pii")

        if required_sensitivity:
            sensitivity_levels = ["public", "internal", "confidential", "restricted"]
            agent_level = sensitivity_levels.index(agent.sensitivity)
            required_level = sensitivity_levels.index(required_sensitivity)

            if agent_level < required_level:
                return False, {
                    "current_sensitivity": agent.sensitivity,
                    "required_sensitivity": required_sensitivity,
                    "reason": "Sensitivity level too low for PII access"
                }

        return True, {}

    def _validate_policy_rules(self, policy_type: str, rules: Dict[str, Any]) -> None:
        """Validate policy rules based on type"""
        if policy_type == PolicyType.COST_CAP:
            if "max_cost_per_month_usd" not in rules:
                raise ValueError("Cost cap policy requires 'max_cost_per_month_usd' rule")

        elif policy_type == PolicyType.DATA_ACCESS:
            if "allowed_data_sources" not in rules:
                raise ValueError("Data access policy requires 'allowed_data_sources' rule")

        elif policy_type == PolicyType.RETENTION:
            if "max_inactive_days" not in rules:
                raise ValueError("Retention policy requires 'max_inactive_days' rule")

    def _to_response(self, policy: AgentPolicy) -> PolicyResponse:
        """Convert ORM model to Pydantic response"""
        return PolicyResponse(
            policy_id=policy.policy_id,
            organization_id=policy.organization_id,
            policy_name=policy.policy_name,
            description=policy.description,
            policy_type=policy.policy_type,
            applies_to=policy.applies_to,
            scope_value=policy.scope_value,
            rules=policy.rules,
            enforcement_level=policy.enforcement_level,
            violations_count=policy.violations_count,
            created_by=policy.created_by,
            created_at=policy.created_at,
            updated_at=policy.updated_at,
            is_active=policy.is_active
        )


# Singleton instance
_agent_policy_service: Optional[AgentPolicyService] = None


def get_agent_policy_service() -> AgentPolicyService:
    """Get singleton AgentPolicyService instance"""
    global _agent_policy_service
    if _agent_policy_service is None:
        _agent_policy_service = AgentPolicyService()
    return _agent_policy_service
