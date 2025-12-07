"""
Engagement API endpoints.

Provides endpoints for:
- Streak tracking and status
- Engagement statistics

All endpoints require authentication and return streak/engagement data
scoped to the authenticated user via RLS.
"""

import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.dependencies import get_authenticated_user, AuthenticatedUser
from backend.db.client import get_supabase_client
from backend.services.engagement_service import (
    get_streak_status,
    get_streak_from_profile,
    get_budget_health_score,
)
from backend.schemas.engagement import (
    StreakStatusResponse,
    EngagementSummary,
    BudgetScoreResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/engagement", tags=["engagement"])


@router.get(
    "/streak",
    response_model=StreakStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get streak status",
    description="""
    Get the authenticated user's current streak status.
    
    This endpoint:
    - Returns current and longest streak counts
    - Includes streak risk assessment (at_risk, days_until_break)
    - Shows streak freeze availability
    
    Use this for:
    - Streak display widgets
    - Reminder/notification logic
    - Gamification UI elements
    
    Security:
    - Requires valid Authorization Bearer token
    - RLS ensures users only see their own data
    """
)
async def get_streak(
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> StreakStatusResponse:
    """
    Get the authenticated user's streak status with risk assessment.
    """
    try:
        supabase_client = get_supabase_client(auth_user.access_token)
        # Service now returns StreakStatusResponse directly
        return await get_streak_status(
            supabase_client=supabase_client,
            user_id=auth_user.user_id
        )
    
    except Exception as e:
        logger.error(f"Error getting streak for user_id={auth_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "streak_fetch_failed", "details": str(e)}
        )


@router.get(
    "/summary",
    response_model=EngagementSummary,
    status_code=status.HTTP_200_OK,
    summary="Get engagement summary",
    description="""
    Get a summary of user's engagement stats for dashboard display.
    
    This endpoint:
    - Returns condensed streak info
    - Includes has_logged_today flag for UI state
    - Lightweight alternative to full streak status
    
    Use this for:
    - Home screen widgets
    - Quick engagement checks
    - Dashboard cards
    
    Security:
    - Requires valid Authorization Bearer token
    - RLS ensures users only see their own data
    """
)
async def get_engagement_summary(
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> EngagementSummary:
    """
    Get engagement summary for dashboard display.
    """
    try:
        supabase_client = get_supabase_client(auth_user.access_token)
        streak_data = await get_streak_from_profile(
            supabase_client=supabase_client,
            user_id=auth_user.user_id
        )
        
        # Calculate has_logged_today
        today = date.today()
        last_activity = streak_data.get("last_activity_date")
        has_logged_today = False
        
        if last_activity:
            if isinstance(last_activity, str):
                last_activity = date.fromisoformat(last_activity)
            has_logged_today = last_activity == today
        
        # Calculate streak_at_risk (simplified check)
        streak_at_risk = False
        if streak_data.get("current_streak", 0) > 0 and not has_logged_today:
            streak_at_risk = True
        
        return EngagementSummary(
            current_streak=streak_data.get("current_streak", 0),
            longest_streak=streak_data.get("longest_streak", 0),
            streak_at_risk=streak_at_risk,
            streak_freeze_available=streak_data.get("streak_freeze_available", True),
            has_logged_today=has_logged_today
        )
    
    except Exception as e:
        logger.error(f"Error getting engagement summary for user_id={auth_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "engagement_fetch_failed", "details": str(e)}
        )


@router.get(
    "/budget-score",
    response_model=BudgetScoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Get budget health score",
    description="""
    Get the authenticated user's budget health score.
    
    This endpoint:
    - Calculates a 0-100 score based on budget adherence
    - Returns per-budget breakdown with individual scores
    - Provides trend indicator (up/down/stable)
    - Counts budgets by status (on_track, warning, over)
    
    Scoring Logic:
    - 0-75% utilization = 100 points (on track)
    - 75-100% utilization = linear decrease from 100 to 75
    - Over 100% = penalty (minimum 0)
    
    Status Thresholds:
    - on_track: Under 75% of limit
    - warning: 75-100% of limit
    - over: Exceeded limit
    
    Use this for:
    - Budget health dashboard widget
    - Spending alerts and notifications
    - Financial wellness tracking
    
    Security:
    - Requires valid Authorization Bearer token
    - RLS ensures users only see their own budgets
    """
)
async def get_budget_score(
    auth_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
) -> BudgetScoreResponse:
    """
    Get the authenticated user's budget health score with breakdown.
    """
    try:
        supabase_client = get_supabase_client(auth_user.access_token)
        score_response = await get_budget_health_score(
            supabase_client=supabase_client,
            user_id=auth_user.user_id
        )
        
        return score_response
    
    except Exception as e:
        logger.error(f"Error getting budget score for user_id={auth_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "budget_score_fetch_failed", "details": str(e)}
        )
