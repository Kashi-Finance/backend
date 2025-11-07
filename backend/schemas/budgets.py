"""
Pydantic schemas for budget CRUD endpoints.

Budgets represent spending caps over time for one or more categories.
Categories are linked via budget_category junction table.
"""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


# Budget frequency enum (matches DB CHECK constraint)
BudgetFrequency = Literal["once", "daily", "weekly", "monthly", "yearly"]


# --- Budget response models ---

class LinkedCategoryResponse(BaseModel):
    """
    Represents a category linked to a budget via budget_category junction table.
    """
    id: str = Field(..., description="Category UUID")
    name: str = Field(..., description="Category display name")
    flow_type: Literal["income", "outcome"] = Field(..., description="Money direction")
    key: Optional[str] = Field(None, description="System category key (null for user categories)")


class BudgetResponse(BaseModel):
    """
    Response for budget details.
    
    Contains all budget fields plus linked categories from budget_category table.
    Consumption (spent amount) is computed from transactions at runtime, not stored directly.
    """
    id: str = Field(..., description="Budget UUID")
    user_id: str = Field(..., description="Owner user UUID")
    limit_amount: float = Field(..., description="Maximum allowed spend for this budget period")
    frequency: BudgetFrequency = Field(..., description="Budget repetition cadence")
    interval: int = Field(..., description="How often the budget repeats in units of frequency")
    start_date: str = Field(..., description="When this budget starts counting (ISO-8601 date)")
    end_date: Optional[str] = Field(None, description="Hard stop date for one-time/project budgets (ISO-8601 date)")
    is_active: bool = Field(..., description="Whether the budget is currently in effect")
    categories: List[LinkedCategoryResponse] = Field(
        default_factory=list,
        description="List of categories linked to this budget via budget_category table"
    )
    created_at: str = Field(..., description="ISO-8601 timestamp when created")
    updated_at: str = Field(..., description="ISO-8601 timestamp of last update")


class BudgetListResponse(BaseModel):
    """
    Response for listing user budgets.
    """
    budgets: List[BudgetResponse] = Field(..., description="List of user's budgets")
    count: int = Field(..., description="Total number of budgets returned")


# --- Budget create models ---

class BudgetCreateRequest(BaseModel):
    """
    Request to create a new budget.
    
    All fields are required except end_date and is_active (which has a default).
    Categories are linked separately via budget_category after creation.
    """
    limit_amount: float = Field(
        ...,
        description="Maximum allowed spend for this budget period",
        gt=0,
        examples=[1200.00, 500.00]
    )
    frequency: BudgetFrequency = Field(
        ...,
        description="Budget repetition cadence",
        examples=["monthly", "weekly", "once"]
    )
    interval: int = Field(
        default=1,
        description="How often the budget repeats in units of frequency",
        ge=1,
        examples=[1, 2]
    )
    start_date: str = Field(
        ...,
        description="When this budget starts counting (ISO-8601 date)",
        examples=["2025-11-01", "2025-12-15"]
    )
    end_date: Optional[str] = Field(
        None,
        description="Hard stop date (ISO-8601 date) - for one-time/project budgets",
        examples=["2026-01-01", None]
    )
    is_active: bool = Field(
        default=True,
        description="Whether the budget is currently in effect"
    )
    category_ids: List[str] = Field(
        default_factory=list,
        description="List of category UUIDs to link to this budget",
        examples=[["cat-uuid-1", "cat-uuid-2"], []]
    )


class BudgetCreateResponse(BaseModel):
    """
    Response after successfully creating a budget.
    """
    status: Literal["CREATED"] = Field("CREATED", description="Indicates successful creation")
    budget: BudgetResponse = Field(..., description="The created budget")
    categories_linked: int = Field(..., description="Number of categories linked to this budget")
    message: str = Field(
        ...,
        description="Success message",
        examples=["Budget created successfully with 3 categories"]
    )


# --- Budget update models ---

class BudgetUpdateRequest(BaseModel):
    """
    Request to update a budget.
    
    All fields are optional - only provided fields will be updated.
    At least one field must be provided.
    
    NOTE: To update linked categories, use separate endpoints for adding/removing
    budget_category links. This endpoint only updates budget fields.
    """
    limit_amount: Optional[float] = Field(
        None,
        description="Updated maximum spend",
        gt=0
    )
    frequency: Optional[BudgetFrequency] = Field(
        None,
        description="Updated repetition cadence"
    )
    interval: Optional[int] = Field(
        None,
        description="Updated interval",
        ge=1
    )
    start_date: Optional[str] = Field(
        None,
        description="Updated start date (ISO-8601)"
    )
    end_date: Optional[str] = Field(
        None,
        description="Updated end date (ISO-8601)"
    )
    is_active: Optional[bool] = Field(
        None,
        description="Updated active status"
    )


class BudgetUpdateResponse(BaseModel):
    """
    Response after successfully updating a budget.
    """
    status: Literal["UPDATED"] = Field("UPDATED", description="Indicates successful update")
    budget: BudgetResponse = Field(..., description="The updated budget")
    message: str = Field(
        ...,
        description="Success message",
        examples=["Budget updated successfully"]
    )


# --- Budget delete models ---

class BudgetDeleteResponse(BaseModel):
    """
    Response after successfully deleting a budget.
    
    Includes count of budget_category links removed.
    """
    status: Literal["DELETED"] = Field("DELETED", description="Indicates successful deletion")
    budget_id: str = Field(..., description="UUID of deleted budget")
    categories_unlinked: int = Field(..., description="Number of budget_category links removed")
    message: str = Field(
        ...,
        description="Success message with deletion details",
        examples=["Budget deleted successfully. 3 category link(s) removed."]
    )
