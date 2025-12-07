"""
Pydantic models for category endpoints.

Categories are labels for income/outcome transactions.
System categories (user_id=NULL) are read-only.
User categories (user_id NOT NULL) are editable.

Subcategory Support:
- Categories can have subcategories (max depth: 1)
- parent_category_id links a subcategory to its parent
- Parent and child must have same flow_type and user_id
- System categories cannot be parents or children
- Subcategories can be created inline with parent via subcategories array
"""

from typing import Literal, Optional, List
from pydantic import BaseModel, Field, model_validator


# Literal type for flow_type (income or outcome)
FlowType = Literal["income", "outcome"]


class SubcategoryCreateInline(BaseModel):
    """
    Inline subcategory definition for creating subcategories 
    together with their parent category in a single request.
    """
    name: str = Field(..., min_length=1, max_length=100, description="Subcategory display name")
    icon: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Icon identifier for UI display",
        examples=["store", "pet", "person"]
    )
    color: str = Field(
        ...,
        pattern=r'^#[0-9A-Fa-f]{6}$',
        description="Hex color code for UI display (e.g., '#4CAF50')",
        examples=["#4CAF50", "#FF5733", "#2196F3"]
    )


class CategoryResponse(BaseModel):
    """
    Response model for a single category.
    
    Fields:
        id: UUID of the category
        user_id: Owner user ID (NULL for system categories)
        parent_category_id: Parent category UUID (NULL for top-level categories)
        key: Stable system key (only for system categories)
        name: User-facing category label
        flow_type: Direction of money ("income" or "outcome")
        icon: Icon identifier for UI display
        color: Hex color code for UI display
        created_at: ISO-8601 timestamp
        updated_at: ISO-8601 timestamp
        subcategories: List of child categories (only populated on request)
    """
    id: str = Field(..., description="Category UUID")
    user_id: Optional[str] = Field(None, description="Owner user ID (NULL for system categories)")
    parent_category_id: Optional[str] = Field(None, description="Parent category UUID (NULL for top-level)")
    key: Optional[str] = Field(None, description="System category key (e.g., 'general', 'transfer')")
    name: str = Field(..., description="Category display name")
    flow_type: FlowType = Field(..., description="Money direction: 'income' or 'outcome'")
    icon: str = Field(..., description="Icon identifier for UI display (e.g., 'shopping', 'food')")
    color: str = Field(..., description="Hex color code for UI display (e.g., '#4CAF50')")
    created_at: str = Field(..., description="Creation timestamp (ISO-8601)")
    updated_at: Optional[str] = Field(None, description="Last update timestamp (ISO-8601)")
    subcategories: Optional[List["CategoryResponse"]] = Field(
        None, 
        description="Child categories (only populated when include_subcategories=true)"
    )


class CategoryListResponse(BaseModel):
    """
    Response model for listing categories.
    
    Returns both system categories (user_id=NULL) and user's personal categories.
    Subcategories are nested under their parents when include_subcategories=true.
    """
    categories: list[CategoryResponse] = Field(..., description="List of categories")
    count: int = Field(..., description="Number of categories returned")
    limit: int = Field(..., description="Query limit applied")
    offset: int = Field(..., description="Query offset applied")


class CategoryCreateRequest(BaseModel):
    """
    Request model for creating a new user category.
    
    System categories cannot be created via API.
    
    Subcategory Creation:
    - To create a category under a parent, provide parent_category_id
    - To create a category WITH subcategories, provide subcategories array
    - Cannot both have a parent AND create subcategories (max depth: 1)
    """
    name: str = Field(..., min_length=1, max_length=100, description="Category display name")
    flow_type: FlowType = Field(..., description="Money direction: 'income' or 'outcome'")
    icon: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Icon identifier for UI display",
        examples=["shopping", "food", "transport", "entertainment"]
    )
    color: str = Field(
        ...,
        pattern=r'^#[0-9A-Fa-f]{6}$',
        description="Hex color code for UI display (e.g., '#4CAF50')",
        examples=["#4CAF50", "#FF5733", "#2196F3"]
    )
    parent_category_id: Optional[str] = Field(
        None,
        description="Parent category UUID. If provided, creates this as a subcategory."
    )
    subcategories: Optional[List[SubcategoryCreateInline]] = Field(
        None,
        description="Inline subcategories to create with this parent category."
    )
    
    @model_validator(mode='after')
    def validate_subcategory_depth(self):
        """Ensure max depth of 1: can't both be a child AND have children."""
        if self.parent_category_id and self.subcategories:
            raise ValueError(
                "Cannot create a category that is both a subcategory (has parent_category_id) "
                "and a parent (has subcategories). Max depth is 1."
            )
        return self


class CategoryCreateResponse(BaseModel):
    """
    Response for successful category creation.
    
    When subcategories were created inline, they appear in category.subcategories.
    """
    status: Literal["CREATED"] = Field(..., description="Status indicator")
    category: CategoryResponse = Field(..., description="Created category with optional subcategories")
    subcategories_created: int = Field(
        0, 
        description="Number of inline subcategories created (0 if none provided)"
    )
    message: str = Field(..., description="Success message")


class CategoryUpdateRequest(BaseModel):
    """
    Request model for updating a user category.
    
    All fields optional (partial update).
    At least one field must be provided.
    
    NOTE: flow_type is NOT editable. Changing flow_type would affect all transactions
    in that category, impacting balances and dependent data structures. Users must
    create a new category with the correct flow_type instead.
    
    NOTE: parent_category_id is NOT editable. Moving subcategories between parents
    is not supported. Delete and recreate if needed.
    """
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="New category name")
    icon: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50,
        description="New icon identifier for UI display"
    )
    color: Optional[str] = Field(
        None,
        pattern=r'^#[0-9A-Fa-f]{6}$',
        description="New hex color code for UI display (e.g., '#4CAF50')"
    )


class CategoryUpdateResponse(BaseModel):
    """Response for successful category update."""
    status: Literal["UPDATED"] = Field(..., description="Status indicator")
    category: CategoryResponse = Field(..., description="Updated category")
    message: str = Field(..., description="Success message")


class CategoryDeleteResponse(BaseModel):
    """
    Response for successful category deletion.
    
    Includes counts of reassigned transactions and removed budget links.
    When deleting a parent category, its subcategories become top-level (parent_category_id set to NULL).
    """
    status: Literal["DELETED"] = Field(..., description="Status indicator")
    category_id: str = Field(..., description="Deleted category UUID")
    transactions_reassigned: int = Field(..., description="Number of transactions reassigned to 'general'")
    budget_links_removed: int = Field(..., description="Number of budget_category links removed")
    subcategories_orphaned: int = Field(
        0,
        description="Number of subcategories that became top-level (parent was deleted)"
    )
    message: str = Field(..., description="Success message")


# Allow CategoryResponse to reference itself for subcategories
CategoryResponse.model_rebuild()
