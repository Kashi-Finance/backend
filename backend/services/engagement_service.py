"""
Engagement Service - Streak and Gamification Features

This service handles all engagement-related functionality including:
- Financial logging streak tracking
- Streak freeze management
- Gamification stats and achievements
- Budget Health Score calculation

Architecture:
- Uses RPC functions for streak calculations (DB-side logic)
- Provides typed Python wrappers for API layer
- All DB operations respect RLS via user's Supabase client
- Returns Pydantic models for type safety and API consistency
"""

import logging
from typing import Any, List, cast
from datetime import date

from supabase import Client

from backend.schemas.engagement import (
    BudgetScoreBreakdown,
    BudgetScoreResponse,
    StreakStatusResponse,
    StreakUpdateResponse,
)

logger = logging.getLogger(__name__)


# =========================================================
# Service Functions
# =========================================================

async def update_streak_after_activity(
    supabase_client: Client,
    user_id: str
) -> StreakUpdateResponse:
    """
    Update user's streak after a financial activity (transaction or invoice).
    
    This should be called AFTER successfully creating a transaction or invoice.
    The function uses an RPC call to handle all streak logic atomically.
    
    Args:
        supabase_client: Authenticated Supabase client (user's session)
        user_id: The user's UUID
    
    Returns:
        StreakUpdateResponse with updated streak stats and flags
    
    Raises:
        Exception: If RPC call fails
    """
    logger.info(f"Updating streak for user_id={user_id}")
    
    try:
        response = supabase_client.rpc(
            "update_user_streak",
            {"p_user_id": user_id}
        ).execute()
        
        data = response.data
        if data and isinstance(data, list) and len(data) > 0:
            row = cast(dict[str, Any], data[0])
            result = StreakUpdateResponse(
                current_streak=int(row.get("current_streak", 0)),
                longest_streak=int(row.get("longest_streak", 0)),
                streak_continued=bool(row.get("streak_continued", False)),
                streak_frozen=bool(row.get("streak_frozen", False)),
                new_personal_best=bool(row.get("new_personal_best", False))
            )
            
            logger.info(
                f"Streak updated for user_id={user_id}: "
                f"current={result.current_streak}, "
                f"continued={result.streak_continued}, "
                f"frozen={result.streak_frozen}, "
                f"new_pb={result.new_personal_best}"
            )
            
            return result
        else:
            logger.error(f"No data returned from update_user_streak for user_id={user_id}")
            raise Exception("Failed to update streak: no data returned")
    
    except Exception as e:
        logger.error(f"Error updating streak for user_id={user_id}: {e}")
        raise


async def get_streak_status(
    supabase_client: Client,
    user_id: str
) -> StreakStatusResponse:
    """
    Get current streak status for a user.
    
    Use this to display streak information in the UI, including
    risk indicators and freeze availability.
    
    Args:
        supabase_client: Authenticated Supabase client (user's session)
        user_id: The user's UUID
    
    Returns:
        StreakStatusResponse with current streak data and risk assessment
    
    Raises:
        Exception: If RPC call fails
    """
    logger.debug(f"Getting streak status for user_id={user_id}")
    
    try:
        response = supabase_client.rpc(
            "get_user_streak",
            {"p_user_id": user_id}
        ).execute()
        
        data = response.data
        if data and isinstance(data, list) and len(data) > 0:
            row = cast(dict[str, Any], data[0])
            
            # Parse last_activity_date
            last_activity_raw = row.get("last_activity_date")
            last_activity: date | None = None
            if last_activity_raw:
                if isinstance(last_activity_raw, str):
                    last_activity = date.fromisoformat(last_activity_raw)
                elif isinstance(last_activity_raw, date):
                    last_activity = last_activity_raw
            
            return StreakStatusResponse(
                current_streak=int(row.get("current_streak", 0)),
                longest_streak=int(row.get("longest_streak", 0)),
                last_activity_date=last_activity,
                streak_freeze_available=bool(row.get("streak_freeze_available", True)),
                streak_at_risk=bool(row.get("streak_at_risk", False)),
                days_until_streak_break=row.get("days_until_streak_break")
            )
        else:
            logger.error(f"No data returned from get_user_streak for user_id={user_id}")
            raise Exception("Failed to get streak status: no data returned")
    
    except Exception as e:
        logger.error(f"Error getting streak status for user_id={user_id}: {e}")
        raise


async def get_streak_from_profile(
    supabase_client: Client,
    user_id: str
) -> dict[str, Any]:
    """
    Get streak fields directly from profile table.
    
    This is a lightweight alternative to get_streak_status() when you
    only need the raw values without risk calculations.
    
    Args:
        supabase_client: Authenticated Supabase client
        user_id: The user's UUID
    
    Returns:
        Dict with streak fields from profile
    """
    try:
        response = supabase_client.table("profile").select(
            "current_streak, longest_streak, last_activity_date, "
            "streak_freeze_available, streak_freeze_used_this_week"
        ).eq("user_id", user_id).execute()
        
        if response.data and len(response.data) > 0:
            return cast(dict[str, Any], response.data[0])
        else:
            # Return defaults for new users
            return {
                "current_streak": 0,
                "longest_streak": 0,
                "last_activity_date": None,
                "streak_freeze_available": True,
                "streak_freeze_used_this_week": False
            }
    
    except Exception as e:
        logger.error(f"Error fetching streak from profile for user_id={user_id}: {e}")
        raise


# =========================================================
# Budget Health Score Functions
# =========================================================

def _calculate_individual_budget_score(utilization: float) -> int:
    """
    Calculate score for a single budget based on utilization.
    
    Scoring logic:
    - 0-75% utilization = 100 points (on track)
    - 75-100% utilization = linear decrease from 100 to 75
    - Over 100% = penalty (minimum 0)
    
    Args:
        utilization: Consumption ratio (consumed / limit)
    
    Returns:
        Score from 0 to 100
    """
    if utilization <= 0.75:
        return 100
    elif utilization <= 1.0:
        # Linear decrease: at 75% = 100, at 100% = 75
        return int(100 - (utilization - 0.75) * 100)
    else:
        # Over budget penalty: rapidly decreases from 75 down to 0
        penalty_score = int(50 - (utilization - 1.0) * 100)
        return max(0, penalty_score)


def _get_budget_status(utilization: float) -> str:
    """
    Determine budget status based on utilization.
    
    Args:
        utilization: Consumption ratio (consumed / limit)
    
    Returns:
        Status string: 'on_track', 'warning', or 'over'
    """
    if utilization <= 0.75:
        return "on_track"
    elif utilization <= 1.0:
        return "warning"
    else:
        return "over"


def _generate_score_message(
    score: int,
    on_track: int,
    warning: int,
    over: int,
    total: int
) -> str:
    """Generate human-readable message based on score and budget stats."""
    if total == 0:
        return "No budgets to track. Create a budget to start monitoring your spending!"
    
    if score == 100:
        return f"Perfect! All {total} budgets are on track. 🎉"
    elif score >= 80:
        if over == 0:
            return f"Great job! {on_track} of {total} budgets are on track."
        else:
            return f"Good progress! {on_track} of {total} budgets are on track, but {over} need attention."
    elif score >= 60:
        return f"Moderate progress. {warning + over} of {total} budgets need attention."
    elif score >= 40:
        return f"Budget health needs work. {over} budgets are over limit."
    else:
        return f"Budget health is critical. {over} of {total} budgets are over limit. Consider adjusting your spending."


async def get_budget_health_score(
    supabase_client: Client,
    user_id: str
) -> BudgetScoreResponse:
    """
    Calculate the overall budget health score for a user.
    
    The score is 0-100 based on budget adherence across all active budgets.
    
    Args:
        supabase_client: Authenticated Supabase client (user's session)
        user_id: The user's UUID
    
    Returns:
        BudgetScoreResponse with overall score and per-budget breakdown
    
    Raises:
        Exception: If database query fails
    """
    logger.info(f"Calculating budget health score for user_id={user_id}")
    
    try:
        # Fetch all active budgets with their categories
        response = supabase_client.table("budget").select(
            "id, name, limit_amount, cached_consumption, "
            "budget_category(category:category_id(name))"
        ).eq("user_id", user_id).eq("is_active", True).is_("deleted_at", "null").execute()
        
        budgets_data = response.data or []
        
        if not budgets_data:
            # No budgets = perfect score but no breakdown
            return BudgetScoreResponse(
                score=100,
                trend="stable",
                budgets_on_track=0,
                budgets_warning=0,
                budgets_over=0,
                total_budgets=0,
                breakdown=[],
                perfect_week=False,
                message="No budgets to track. Create a budget to start monitoring your spending!"
            )
        
        breakdown: List[BudgetScoreBreakdown] = []
        scores: List[int] = []
        on_track_count = 0
        warning_count = 0
        over_count = 0
        
        for budget_raw in budgets_data:
            budget = cast(dict[str, Any], budget_raw)
            budget_id = str(budget["id"])
            budget_name = str(budget["name"])
            limit_amount = float(budget["limit_amount"])
            consumed = float(budget.get("cached_consumption", 0) or 0)
            
            # Get category name if available
            category_name = None
            budget_categories = budget.get("budget_category", [])
            if budget_categories and isinstance(budget_categories, list) and len(budget_categories) > 0:
                cat_data = budget_categories[0].get("category")
                if cat_data:
                    category_name = cat_data.get("name")
            
            # Calculate utilization and score
            if limit_amount > 0:
                utilization = consumed / limit_amount
            else:
                utilization = 0.0
            
            budget_score = _calculate_individual_budget_score(utilization)
            status = _get_budget_status(utilization)
            
            # Count by status
            if status == "on_track":
                on_track_count += 1
            elif status == "warning":
                warning_count += 1
            else:
                over_count += 1
            
            scores.append(budget_score)
            
            breakdown.append(BudgetScoreBreakdown(
                budget_id=budget_id,
                budget_name=budget_name,
                category_name=category_name,
                limit_amount=limit_amount,
                consumed_amount=consumed,
                utilization=round(utilization, 3),
                score=budget_score,
                status=status
            ))
        
        # Calculate overall score (average of all budget scores)
        overall_score = int(sum(scores) / len(scores)) if scores else 100
        
        # TODO: Calculate trend from historical data (requires score history tracking)
        # For now, always return "stable"
        trend = "stable"
        
        # TODO: Track perfect week (requires daily score logging)
        perfect_week = overall_score == 100
        
        total_budgets = len(budgets_data)
        message = _generate_score_message(
            overall_score, on_track_count, warning_count, over_count, total_budgets
        )
        
        logger.info(
            f"Budget health score for user_id={user_id}: "
            f"score={overall_score}, on_track={on_track_count}, "
            f"warning={warning_count}, over={over_count}"
        )
        
        return BudgetScoreResponse(
            score=overall_score,
            trend=trend,
            budgets_on_track=on_track_count,
            budgets_warning=warning_count,
            budgets_over=over_count,
            total_budgets=total_budgets,
            breakdown=breakdown,
            perfect_week=perfect_week,
            message=message
        )
    
    except Exception as e:
        logger.error(f"Error calculating budget health score for user_id={user_id}: {e}")
        raise
