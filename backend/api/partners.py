"""
White Label Partners API - Stub Endpoints

Returns empty data until partner management is fully implemented.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/partners", tags=["partners"])


@router.get("")
async def list_partners():
    """List all white-label partners."""
    return []


@router.get("/{partner_id}/branding")
async def get_partner_branding(partner_id: int):
    """Get branding configuration for a partner."""
    return []


@router.get("/{partner_id}/customers")
async def get_partner_customers(partner_id: int):
    """Get customers for a partner."""
    return []


@router.get("/{partner_id}/stats")
async def get_partner_stats(partner_id: int):
    """Get stats for a partner."""
    return {
        "total_revenue": 0,
        "total_commission": 0,
        "total_customers": 0,
        "active_customers": 0,
    }
