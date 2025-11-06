"""
Pydantic models for category endpoints.

Categories are labels for income/outcome transactions.
System categories (user_id=NULL) are read-only.
User categories (user_id NOT NULL) are editable.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


# Literal type for flow_type (income or outcome)
FlowType = Literal["income", "outcome"]


class CategoryResponse(BaseModel):
    """
    Response model for a single category.
    
    Fields:
        id: UUID of the category
        user_id: Owner user ID (NULL for system categories)
        key: Stable system key (only for system categories)
        name: User-facing category label
        flow_type: Direction of money ("income" or "outcome")
        created_at: ISO-8601 timestamp
        updated_at: ISO-8601 timestamp
    """
    id: str = Field(..., description="Category UUID")
    user_id: Optional[str] = Field(None, description="Owner user ID (NULL for system categories)")
    key: Optional[str] = Field(None, description="System category key (e.g., 'general', 'transfer')")
    name: str = Field(..., description="Category display name")
    flow_type: FlowType = Field(..., description="Money direction: 'income' or 'outcome'")
    created_at: str = Field(..., description="Creation timestamp (ISO-8601)")
    updated_at: Optional[str] = Field(None, description="Last update timestamp (ISO-8601)")


class CategoryListResponse(BaseModel):
    """
    Response model for listing categories.
    
    Returns both system categories (user_id=NULL) and user's personal categories.
    """
    categories: list[CategoryResponse] = Field(..., description="List of categories")
    count: int = Field(..., description="Number of categories returned")
    limit: int = Field(..., description="Query limit applied")
    offset: int = Field(..., description="Query offset applied")


class CategoryCreateRequest(BaseModel):
    """
    Request model for creating a new user category.
    
    System categories cannot be created via API.
    """
    name: str = Field(..., min_length=1, max_length=100, description="Category display name")
    flow_type: FlowType = Field(..., description="Money direction: 'income' or 'outcome'")


class CategoryCreateResponse(BaseModel):
    """Response for successful category creation."""
    status: Literal["CREATED"] = Field(..., description="Status indicator")
    category: CategoryResponse = Field(..., description="Created category")
    message: str = Field(..., description="Success message")


class CategoryUpdateRequest(BaseModel):
    """
    Request model for updating a user category.
    
    All fields optional (partial update).
    At least one field must be provided.
    
    NOTE: flow_type is NOT editable. Changing flow_type would affect all transactions
    in that category, impacting balances and dependent data structures. Users must
    create a new category with the correct flow_type instead.
    """
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="New category name")


class CategoryUpdateResponse(BaseModel):
    """Response for successful category update."""
    status: Literal["UPDATED"] = Field(..., description="Status indicator")
    category: CategoryResponse = Field(..., description="Updated category")
    message: str = Field(..., description="Success message")


class CategoryDeleteResponse(BaseModel):
    """
    Response for successful category deletion.
    
    Includes counts of reassigned transactions and removed budget links.
    """
    status: Literal["DELETED"] = Field(..., description="Status indicator")
    category_id: str = Field(..., description="Deleted category UUID")
    transactions_reassigned: int = Field(..., description="Number of transactions reassigned to 'general'")
    budget_links_removed: int = Field(..., description="Number of budget_category links removed")
    message: str = Field(..., description="Success message")
