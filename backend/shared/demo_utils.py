"""
Utility functions for demos
"""
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession


async def cleanup_demo_data(db: AsyncSession):
    """Clean up all demo data from ML routing and AB testing tables"""
    from backend.shared.ml_routing_models import (
        CostOptimizationRule,
        MLRoutingModel,
        ModelPerformanceHistory,
        RoutingDecision,
        RoutingPolicy,
        LLMModel
    )
    from backend.shared.ab_testing_models import (
        ABMetric,
        ABAssignment,
        ABVariant,
        ABExperiment
    )
    from backend.shared.analytics_models import (
        DashboardWidget,
        Dashboard
    )
    from backend.shared.whitelabel_models import (
        PartnerApiKey,
        Commission,
        PartnerCustomer,
        WhiteLabelBranding,
        Partner
    )

    # Delete AB testing data in reverse order of dependencies
    await db.execute(delete(ABMetric))
    await db.execute(delete(ABAssignment))
    await db.execute(delete(ABVariant))
    await db.execute(delete(ABExperiment))

    # Delete analytics data
    await db.execute(delete(DashboardWidget))
    await db.execute(delete(Dashboard))

    # Delete ML routing data in reverse order of dependencies
    await db.execute(delete(CostOptimizationRule))
    await db.execute(delete(ModelPerformanceHistory))
    await db.execute(delete(RoutingDecision))
    await db.execute(delete(RoutingPolicy))
    await db.execute(delete(LLMModel))

    # Delete whitelabel data in reverse order of dependencies
    await db.execute(delete(PartnerApiKey))
    await db.execute(delete(Commission))
    await db.execute(delete(PartnerCustomer))
    await db.execute(delete(WhiteLabelBranding))
    await db.execute(delete(Partner))

    await db.commit()
