"""
Engagement Schemas - Pydantic models for engagement/gamification features

This module defines request and response models for:
- Streak tracking
- Activity logging
- Gamification stats
- Budget Health Score
"""

from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field


# =========================================================
# Streak Response Models
# =========================================================

class StreakStatusResponse(BaseModel):
    """Current streak status for a user."""
    
    current_streak: int = Field(
        ...,
        ge=0,
        description="Current consecutive days with financial activity"
    )
    longest_streak: int = Field(
        ...,
        ge=0,
        description="All-time longest streak achieved"
    )
    last_activity_date: Optional[date] = Field(
        None,
        description="Last date when user logged financial activity (UTC)"
    )
    streak_freeze_available: bool = Field(
        ...,
        description="Whether user can use a streak freeze if they miss a day"
    )
    streak_at_risk: bool = Field(
        ...,
        description="Whether streak will break if no activity today"
    )
    days_until_streak_break: Optional[int] = Field(
        None,
        ge=0,
        description="Days remaining before streak breaks (0 = breaks at end of today)"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "current_streak": 7,
                    "longest_streak": 14,
                    "last_activity_date": "2025-12-01",
                    "streak_freeze_available": True,
                    "streak_at_risk": False,
                    "days_until_streak_break": 2
                }
            ]
        }
    }


class StreakUpdateResponse(BaseModel):
    """Response after updating streak (from transaction/invoice creation)."""
    
    current_streak: int = Field(
        ...,
        ge=0,
        description="Updated current streak count"
    )
    longest_streak: int = Field(
        ...,
        ge=0,
        description="All-time longest streak (may have updated)"
    )
    streak_continued: bool = Field(
        ...,
        description="Whether the streak was continued (True) or reset (False)"
    )
    streak_frozen: bool = Field(
        ...,
        description="Whether a streak freeze was used to prevent break"
    )
    new_personal_best: bool = Field(
        ...,
        description="Whether this update set a new longest streak record"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "current_streak": 8,
                    "longest_streak": 14,
                    "streak_continued": True,
                    "streak_frozen": False,
                    "new_personal_best": False
                }
            ]
        }
    }


# =========================================================
# Profile Streak Fields (for embedding in profile responses)
# =========================================================

class ProfileStreakFields(BaseModel):
    """Streak fields that are part of the profile object."""
    
    current_streak: int = Field(
        default=0,
        ge=0,
        description="Current consecutive days with financial activity"
    )
    longest_streak: int = Field(
        default=0,
        ge=0,
        description="All-time longest streak achieved"
    )
    last_activity_date: Optional[date] = Field(
        None,
        description="Last date when user logged financial activity"
    )
    streak_freeze_available: bool = Field(
        default=True,
        description="Whether user has a streak freeze available this week"
    )
    streak_freeze_used_this_week: bool = Field(
        default=False,
        description="Whether user used their streak freeze this week"
    )


# =========================================================
# Engagement Summary (for dashboard/home screen)
# =========================================================

class EngagementSummary(BaseModel):
    """Summary of user's engagement stats for dashboard display."""
    
    current_streak: int = Field(
        ...,
        ge=0,
        description="Current consecutive days with activity"
    )
    longest_streak: int = Field(
        ...,
        ge=0,
        description="All-time record streak"
    )
    streak_at_risk: bool = Field(
        ...,
        description="Whether streak needs attention today"
    )
    streak_freeze_available: bool = Field(
        ...,
        description="Whether freeze protection is available"
    )
    has_logged_today: bool = Field(
        ...,
        description="Whether user has logged any activity today"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "current_streak": 7,
                    "longest_streak": 14,
                    "streak_at_risk": False,
                    "streak_freeze_available": True,
                    "has_logged_today": True
                }
            ]
        }
    }


# =========================================================
# Budget Health Score Models
# =========================================================

class BudgetScoreBreakdown(BaseModel):
    """Individual budget score breakdown."""

    budget_id: str = Field(..., description="UUID of the budget")
    budget_name: str = Field(..., description="Name of the budget")
    category_name: Optional[str] = Field(None, description="Associated category name")
    limit_amount: float = Field(..., description="Budget limit amount")
    consumed_amount: float = Field(..., description="Amount consumed so far")
    utilization: float = Field(
        ..., ge=0.0, description="Consumption ratio (0.0 to 1.0+)"
    )
    score: int = Field(..., ge=0, le=100, description="Individual budget score 0-100")
    status: str = Field(
        ..., description="Budget status: 'on_track', 'warning', or 'over'"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "budget_id": "b1234567-89ab-cdef-0123-456789abcdef",
                    "budget_name": "Groceries Monthly",
                    "category_name": "Food & Groceries",
                    "limit_amount": 2000.00,
                    "consumed_amount": 1450.00,
                    "utilization": 0.725,
                    "score": 100,
                    "status": "on_track"
                }
            ]
        }
    }


class BudgetScoreResponse(BaseModel):
    """Budget health score response."""

    score: int = Field(..., ge=0, le=100, description="Overall budget health 0-100")
    trend: str = Field(
        ..., description="Score trend vs last week: 'up', 'down', or 'stable'"
    )
    budgets_on_track: int = Field(
        ..., ge=0, description="Number of budgets under 75% limit"
    )
    budgets_warning: int = Field(
        ..., ge=0, description="Number of budgets at 75-100% limit"
    )
    budgets_over: int = Field(..., ge=0, description="Number of budgets over limit")
    total_budgets: int = Field(..., ge=0, description="Total number of active budgets")
    breakdown: List[BudgetScoreBreakdown] = Field(
        default_factory=list, description="Per-budget score breakdown"
    )
    perfect_week: bool = Field(
        default=False,
        description="True if score has been 100 for 7 consecutive days",
    )
    message: str = Field(
        ..., description="Human-readable summary message for the user"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "score": 85,
                    "trend": "up",
                    "budgets_on_track": 3,
                    "budgets_warning": 1,
                    "budgets_over": 0,
                    "total_budgets": 4,
                    "breakdown": [],
                    "perfect_week": False,
                    "message": "Great job! 3 of 4 budgets are on track."
                }
            ]
        }
    }
