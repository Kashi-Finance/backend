# Kashi Finances: Engagement Strategy Analysis

**Date:** December 1, 2025  
**Status:** Analysis Complete - Ready for Review  
**Author:** Backend Team  
**Document Type:** Product Strategy + Technical Architecture

---

## Executive Summary

This document analyzes the Kashi Finances backend to identify opportunities for increasing user engagement and daily app usage. After comprehensive codebase review and application of behavioral design principles, we propose **5 high-impact features** that are implementable with the current architecture.

**Key Finding:** The app is currently **purely functional** with **zero engagement mechanics**. There's no reward for consistent usage, no progress visualization, and no habit-forming loops.

**Recommended Priority:**
1. Financial Logging Streak (highest ROI)
2. Savings Goal Tracker (extends wishlists)
3. Budget Health Score (low effort, high visibility)
4. Weekly Financial Summary (natural review cycle)
5. Budget Milestone Celebrations (rewards discipline)

---

## Table of Contents

1. [App Understanding](#1-app-understanding)
2. [Strategy Analysis](#2-strategy-analysis)
3. [Feature Concepts](#3-feature-concepts)
4. [Evaluation & Shortlist](#4-evaluation--shortlist)
5. [Implementation Roadmap](#5-implementation-roadmap)
6. [Technical Specifications](#6-technical-specifications)

---

## 1. App Understanding

### 1.1 App Summary

| Aspect | Description |
|--------|-------------|
| **What it does** | Personal finance management mobile app with AI-powered receipt OCR and product recommendations |
| **Target Market** | Latin American market (primarily Guatemala, GTQ currency) |
| **Primary Users** | Young adults managing personal finances who want easy expense tracking |
| **Core Value** | Frictionless expense logging via receipt photos + budget discipline tools |

### 1.2 Core Features

| Feature | Description | Tables Involved |
|---------|-------------|-----------------|
| Multi-account tracking | Cash, bank, credit cards, crypto, investments | `account` |
| Receipt OCR | AI extracts data from receipt photos | `invoice` + Gemini Vision |
| Transaction management | Manual and auto-generated transactions | `transaction` |
| Budgeting | Multi-category spending limits | `budget`, `budget_category` |
| Recurring transactions | Auto-generate scheduled income/expenses | `recurring_transaction` |
| Wishlists | Purchase goals with AI recommendations | `wishlist`, `wishlist_item` + DeepSeek |
| Transfers | Move money between accounts | Paired `transaction` records |

### 1.3 Core User Journeys

| Journey | Description | Frequency |
|---------|-------------|-----------|
| **Receipt Capture** | Photo → OCR → Confirm → Transaction | Daily/Weekly |
| **Manual Transaction** | Log income/expense with category | Daily/Weekly |
| **Budget Tracking** | Create budget → Spend → Check consumption | Weekly/Monthly |
| **Recurring Setup** | Create rule → System auto-generates | Setup + ongoing |
| **Transfer Money** | Move between accounts | Occasional |
| **Wishlist + Recommendations** | Set goal → AI recommends → Save options | Occasional |
| **Balance Check** | View accounts and history | Daily |

### 1.4 Current Engagement Mechanics

| Category | Status | Notes |
|----------|--------|-------|
| **Streaks** | ❌ None | No logging streak, no consistency tracking |
| **Points/Badges** | ❌ None | No achievement system |
| **Progress Visualization** | ⚠️ Partial | Budget has `cached_consumption` vs `limit_amount` but no visual progress |
| **Goals** | ⚠️ Partial | Wishlists have `goal_title`, `target_date`, `status` but no savings tracking |
| **Reminders/Notifications** | ❌ None | No push notification infrastructure |
| **Analytics Events** | ❌ None | No user behavior tracking |
| **History/Logs** | ✅ Full | Rich transaction history available |

**Critical Gap:** No reason to open the app daily beyond necessity. No reward for consistent usage.

### 1.5 Architecture Constraints

| Component | Technology | Engagement Implications |
|-----------|------------|------------------------|
| Backend | FastAPI (Python) | Easy to add new endpoints |
| Database | PostgreSQL + Supabase | Can add new tables/fields easily |
| Auth | Supabase Auth (JWT) | User identity available |
| AI | Gemini + DeepSeek | Could power smart suggestions |
| Background Jobs | ❌ None | Can't send scheduled notifications without external scheduler |
| Push Notifications | ❌ None | Requires Flutter integration for mobile tokens |

---

## 2. Strategy Analysis

### 2.1 Behavioral Opportunities

| Action | Current State | Habit Potential | Why |
|--------|---------------|-----------------|-----|
| Daily expense logging | Manual, no reward | **HIGH** | Users already have daily expenses to log |
| Receipt capture | Functional but isolated | **HIGH** | Core differentiator, should be encouraged |
| Budget check-in | User must remember | **MEDIUM** | Natural weekly cycle |
| Category tagging | Required but tedious | **MEDIUM** | Could be gamified |
| End-of-day review | Doesn't exist | **HIGH** | Financial hygiene habit |

### 2.2 Engagement Patterns That Fit

| Pattern | Fit for Kashi | Implementation Difficulty |
|---------|---------------|--------------------------|
| **Logging Streaks** | ✅ Perfect | LOW - Add 2-3 fields to profile |
| **Budget Progress Bars** | ✅ Direct fit | LOW - Data exists, needs UI |
| **Savings Goals with Progress** | ✅ Extends wishlists | MEDIUM - Add contribution tracking |
| **Achievement Badges** | ✅ Milestone recognition | MEDIUM - New tables needed |
| **Weekly Summary** | ✅ Natural financial cycle | MEDIUM - Aggregation logic |
| **Points System** | ⚠️ May feel gimmicky | - |
| **Leaderboards** | ❌ Privacy concerns | - |

---

## 3. Feature Concepts

### 3.1 Feature 1: Financial Logging Streak ⭐ TOP PRIORITY

**Description:**  
Track consecutive days where the user logged at least one transaction (manual or invoice). Display streak count prominently. Reward streak milestones.

**User Story:**  
> "As a Kashi user, I want to see how many consecutive days I've logged my expenses, so I can build a habit of tracking all my spending."

**Engagement Mechanism:**
- Streak counter (1, 2, 3, 7, 14, 30, 60, 90+ days)
- Streak freeze (1 free miss per week unlocked at 7-day streak)
- Milestone celebrations at 7, 30, 90 days
- Visual fire/flame icon that grows with streak

**Success Metrics:**
| Metric | Target |
|--------|--------|
| DAU increase | +30% |
| 7-day retention | +20% |
| Users with 7+ day streaks | 25% of MAU |

**UX Flow:**
1. Home screen shows current streak prominently
2. Transaction creation triggers streak check/update
3. Modal celebration at milestones
4. "Streak at risk" reminder if no transactions by 8pm

**Database Changes:**
```sql
ALTER TABLE public.profile ADD COLUMN current_streak INT DEFAULT 0;
ALTER TABLE public.profile ADD COLUMN longest_streak INT DEFAULT 0;
ALTER TABLE public.profile ADD COLUMN last_activity_date DATE;
ALTER TABLE public.profile ADD COLUMN streak_freeze_available BOOLEAN DEFAULT FALSE;
ALTER TABLE public.profile ADD COLUMN streak_freeze_used_this_week BOOLEAN DEFAULT FALSE;
```

**API Changes:**
- `GET /engagement/streak` - Returns streak status
- Modify `POST /transactions` and `POST /invoices/commit` to update streak

---

### 3.2 Feature 2: Budget Health Score

**Description:**  
A 0-100 score calculated from budget adherence across all active budgets. Updated in real-time as transactions are logged.

**User Story:**  
> "As a Kashi user, I want a single score that tells me how well I'm managing my budgets, so I can easily understand my financial discipline at a glance."

**Engagement Mechanism:**
- Score from 0-100 based on % of budgets under limit
- Color coding (green 80+, yellow 50-79, red <50)
- Weekly score trend arrow (up/down/stable)
- "Perfect Week" celebration if score stays 100 for 7 days

**Success Metrics:**
| Metric | Target |
|--------|--------|
| Average user score | 70+ |
| Users checking score weekly | 50% |
| Budget under-limit rate | +15% |

**Calculation Logic:**
```python
def calculate_budget_health_score(budgets: List[Budget]) -> int:
    if not budgets:
        return 100  # No budgets = perfect score
    
    scores = []
    for b in budgets:
        if b.limit_amount <= 0:
            continue
        utilization = b.cached_consumption / b.limit_amount
        
        if utilization <= 0.75:
            scores.append(100)  # Under 75% = perfect
        elif utilization <= 1.0:
            # 75-100% = linear decrease from 100 to 75
            scores.append(100 - (utilization - 0.75) * 100)
        else:
            # Over budget = penalty (minimum 0)
            scores.append(max(0, 50 - (utilization - 1.0) * 100))
    
    return int(sum(scores) / len(scores)) if scores else 100
```

**API Changes:**
- `GET /engagement/budget-score` - Returns score + breakdown

---

### 3.3 Feature 3: Savings Goal Tracker (Enhanced Wishlists) ⭐ HIGH VALUE

**Description:**  
Transform wishlists into active savings goals with contribution tracking, progress visualization, and projected completion dates.

**User Story:**  
> "As a Kashi user, I want to track how much I've saved toward my wishlist goal, so I can see my progress and know when I'll be able to afford it."

**Engagement Mechanism:**
- Visual progress bar (saved_amount / budget_hint)
- Projected completion date based on average savings rate
- "Quick Save" button to log contribution
- Celebration when goal is reached
- Option to link to account for automatic tracking

**Success Metrics:**
| Metric | Target |
|--------|--------|
| Wishlists with contributions | 40% |
| Time to goal completion | -20% vs estimate |
| Wishlist completion rate | +30% |

**Database Changes:**
```sql
-- Add to wishlist table
ALTER TABLE public.wishlist ADD COLUMN saved_amount NUMERIC(12,2) DEFAULT 0;
ALTER TABLE public.wishlist ADD COLUMN last_contribution_date DATE;

-- New contribution tracking table
CREATE TABLE public.wishlist_contribution (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  wishlist_id UUID NOT NULL REFERENCES public.wishlist(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
  note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX wishlist_contribution_wishlist_idx 
  ON public.wishlist_contribution(wishlist_id);
CREATE INDEX wishlist_contribution_user_idx 
  ON public.wishlist_contribution(user_id);

-- RLS for wishlist_contribution
ALTER TABLE public.wishlist_contribution ENABLE ROW LEVEL SECURITY;

CREATE POLICY "wishlist_contribution_select_own" ON public.wishlist_contribution
FOR SELECT USING (user_id = auth.uid() OR auth.role() = 'service_role');

CREATE POLICY "wishlist_contribution_insert_own" ON public.wishlist_contribution
FOR INSERT WITH CHECK (user_id = auth.uid() OR auth.role() = 'service_role');

CREATE POLICY "wishlist_contribution_delete_own" ON public.wishlist_contribution
FOR DELETE USING (user_id = auth.uid() OR auth.role() = 'service_role');
```

**API Changes:**
- `POST /wishlists/{id}/contribute` - Add savings contribution
- `GET /wishlists/{id}/contributions` - List contribution history
- Modify `GET /wishlists/{id}` to include `saved_amount` and progress percentage

---

### 3.4 Feature 4: Weekly Financial Summary

**Description:**  
Automated weekly digest summarizing spending, income, budget status, and achievements for the past 7 days.

**User Story:**  
> "As a Kashi user, I want a weekly summary of my financial activity, so I can understand my spending patterns and celebrate my wins."

**Engagement Mechanism:**
- Total income vs expenses comparison
- Top spending categories with bars
- Budget status overview (X/Y budgets on track)
- Streak status and achievements earned
- Comparison to previous week

**Success Metrics:**
| Metric | Target |
|--------|--------|
| Users viewing summary | 60% |
| Post-summary app opens (within 24h) | 40% |
| User satisfaction rating | 4+ stars |

**API Changes:**
```python
# GET /engagement/weekly-summary?week_start=YYYY-MM-DD

class WeeklySummaryResponse(BaseModel):
    week_start: str
    week_end: str
    
    # Totals
    total_income: float
    total_expenses: float
    net_change: float
    
    # Comparison
    income_vs_last_week: float  # percentage change
    expenses_vs_last_week: float
    
    # Category breakdown
    top_expense_categories: List[CategorySpending]
    top_income_categories: List[CategorySpending]
    
    # Budget status
    budgets_on_track: int
    budgets_over: int
    budget_score: int
    
    # Engagement
    current_streak: int
    transactions_logged: int
    receipts_captured: int
    
    # Achievements (if badge system exists)
    badges_earned: List[str]
```

---

### 3.5 Feature 5: Budget Milestone Celebrations

**Description:**  
Celebrate when a user completes a budget period under limit (e.g., monthly grocery budget finished at 80%).

**User Story:**  
> "As a Kashi user, I want to be celebrated when I finish a budget period under my limit, so I feel rewarded for my discipline."

**Engagement Mechanism:**
- End-of-period detection (when budget resets)
- Under-limit → confetti animation + badge
- Streak of successful budget periods
- "Budget Champion" badge for 3 consecutive periods under limit

**Success Metrics:**
| Metric | Target |
|--------|--------|
| Budget under-limit rate | +20% |
| User awareness of period end | 80% |
| Celebration engagement | 40% |

**Database Changes:**
```sql
ALTER TABLE public.budget ADD COLUMN successful_periods INT DEFAULT 0;
ALTER TABLE public.budget ADD COLUMN current_period_streak INT DEFAULT 0;
ALTER TABLE public.budget ADD COLUMN last_period_end DATE;
```

**API Changes:**
- `GET /budgets/{id}/history` - Returns period-by-period performance
- Logic to detect period completion and update counters

---

## 4. Evaluation & Shortlist

### 4.1 Evaluation Matrix

| Feature | Impact | Specificity | Effort | Arch Fit | Overall |
|---------|--------|-------------|--------|----------|---------|
| F1: Logging Streak | HIGH | Very specific | LOW | STRONG | ⭐⭐⭐⭐⭐ |
| F2: Budget Health Score | MEDIUM | Very specific | LOW | STRONG | ⭐⭐⭐⭐ |
| F3: Savings Goal Tracker | HIGH | Very specific | MEDIUM | STRONG | ⭐⭐⭐⭐⭐ |
| F4: Weekly Summary | MEDIUM | Specific | MEDIUM | STRONG | ⭐⭐⭐⭐ |
| F5: Budget Milestones | MEDIUM | Specific | LOW | STRONG | ⭐⭐⭐⭐ |

### 4.2 Ideas Considered But Discarded

| Idea | Reason for Discarding |
|------|----------------------|
| Transaction Tagging Gamification | High complexity, low user value - users don't care about "mastering" categories |
| Daily Financial Challenge | Requires challenge management system, high complexity for moderate value |
| Financial Health Dashboard | Too generic - every finance app has this, not differentiated |
| End-of-Month Ritual | Nice but not a retention driver - users can ignore without consequence |
| Points System | May feel gimmicky and undermine financial app seriousness |
| Leaderboards | Privacy concerns - users don't want financial comparisons |

### 4.3 Final Recommendations

| Priority | Feature | Justification |
|----------|---------|---------------|
| **1** | **Logging Streak** | Highest impact on DAU, lowest effort, proven pattern in finance apps |
| **2** | **Savings Goal Tracker** | Extends existing wishlist elegantly, creates long-term engagement |
| **3** | **Budget Health Score** | Low effort, synthesizes existing data into actionable metric |
| **4** | **Weekly Summary** | Natural review cycle, drives weekly re-engagement |
| **5** | **Budget Milestones** | Low effort, rewards core desired behavior |

---

## 5. Implementation Roadmap

### Phase 1: MVP Engagement (2-3 weeks)

**Goal:** Establish daily engagement loop

| Task | Effort | Dependencies |
|------|--------|--------------|
| Add streak fields to profile table | 1 day | Migration |
| Implement streak update logic | 2 days | - |
| Add `GET /engagement/streak` endpoint | 1 day | - |
| Modify transaction/invoice endpoints to call streak update | 1 day | - |
| Implement budget health score calculation | 1 day | - |
| Add `GET /engagement/budget-score` endpoint | 1 day | - |
| Create engagement router and schemas | 1 day | - |
| **Total** | **~8 days** | - |

### Phase 2: Goal-Oriented Engagement (2-3 weeks)

**Goal:** Long-term engagement through savings goals

| Task | Effort | Dependencies |
|------|--------|--------------|
| Add saved_amount to wishlist table | 1 day | Migration |
| Create wishlist_contribution table | 1 day | Migration |
| Implement contribution service | 2 days | - |
| Add contribution endpoints | 2 days | - |
| Add budget period tracking fields | 1 day | Migration |
| Implement milestone detection logic | 2 days | - |
| Add budget history endpoint | 1 day | - |
| **Total** | **~10 days** | Phase 1 |

### Phase 3: Retention & Habit (2-3 weeks)

**Goal:** Weekly re-engagement and celebration

| Task | Effort | Dependencies |
|------|--------|--------------|
| Implement weekly summary aggregation | 3 days | - |
| Add `GET /engagement/weekly-summary` endpoint | 2 days | - |
| Design badge system (if proceeding) | 2 days | - |
| Implement badge tables and logic | 3 days | - |
| Add badge endpoints | 2 days | - |
| **Total** | **~12 days** | Phase 1-2 |

---

## 6. Technical Specifications

### 6.1 New Database Tables

```sql
-- =========================================================
-- Engagement System Tables
-- =========================================================

-- Wishlist contributions (for savings goal tracking)
CREATE TABLE public.wishlist_contribution (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  wishlist_id UUID NOT NULL REFERENCES public.wishlist(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
  note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.wishlist_contribution ENABLE ROW LEVEL SECURITY;

CREATE POLICY "wishlist_contribution_select_own" ON public.wishlist_contribution
FOR SELECT USING (user_id = auth.uid() OR auth.role() = 'service_role');

CREATE POLICY "wishlist_contribution_insert_own" ON public.wishlist_contribution
FOR INSERT WITH CHECK (user_id = auth.uid() OR auth.role() = 'service_role');

CREATE POLICY "wishlist_contribution_delete_own" ON public.wishlist_contribution
FOR DELETE USING (user_id = auth.uid() OR auth.role() = 'service_role');

CREATE INDEX wishlist_contribution_wishlist_idx ON public.wishlist_contribution(wishlist_id);
CREATE INDEX wishlist_contribution_user_idx ON public.wishlist_contribution(user_id);

-- Badge definitions (system-wide, not user-specific)
CREATE TABLE public.badge (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  icon TEXT NOT NULL,
  category TEXT NOT NULL,  -- 'streak', 'budget', 'savings', 'milestone'
  is_secret BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- User badge awards
CREATE TABLE public.user_badge (
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  badge_id UUID NOT NULL REFERENCES public.badge(id) ON DELETE CASCADE,
  earned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, badge_id)
);

ALTER TABLE public.user_badge ENABLE ROW LEVEL SECURITY;

CREATE POLICY "user_badge_select_own" ON public.user_badge
FOR SELECT USING (user_id = auth.uid() OR auth.role() = 'service_role');

CREATE INDEX user_badge_user_idx ON public.user_badge(user_id);
```

### 6.2 Profile Table Extensions

```sql
-- Streak tracking
ALTER TABLE public.profile ADD COLUMN current_streak INT NOT NULL DEFAULT 0;
ALTER TABLE public.profile ADD COLUMN longest_streak INT NOT NULL DEFAULT 0;
ALTER TABLE public.profile ADD COLUMN last_activity_date DATE;
ALTER TABLE public.profile ADD COLUMN streak_freeze_available BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE public.profile ADD COLUMN streak_freeze_used_this_week BOOLEAN NOT NULL DEFAULT FALSE;

-- Receipt-specific streak (optional)
ALTER TABLE public.profile ADD COLUMN receipt_streak INT NOT NULL DEFAULT 0;
ALTER TABLE public.profile ADD COLUMN longest_receipt_streak INT NOT NULL DEFAULT 0;
ALTER TABLE public.profile ADD COLUMN last_receipt_date DATE;
```

### 6.3 Wishlist Table Extensions

```sql
ALTER TABLE public.wishlist ADD COLUMN saved_amount NUMERIC(12,2) NOT NULL DEFAULT 0;
ALTER TABLE public.wishlist ADD COLUMN last_contribution_date DATE;
```

### 6.4 Budget Table Extensions

```sql
ALTER TABLE public.budget ADD COLUMN successful_periods INT NOT NULL DEFAULT 0;
ALTER TABLE public.budget ADD COLUMN current_period_streak INT NOT NULL DEFAULT 0;
ALTER TABLE public.budget ADD COLUMN last_period_end DATE;
```

### 6.5 New API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/engagement/streak` | Get user's current streak status |
| GET | `/engagement/budget-score` | Get budget health score |
| GET | `/engagement/weekly-summary` | Get weekly financial summary |
| GET | `/engagement/badges` | List user's earned badges |
| GET | `/engagement/badges/available` | List all badges (for discovery) |
| POST | `/wishlists/{id}/contribute` | Add savings contribution |
| GET | `/wishlists/{id}/contributions` | List contribution history |
| GET | `/budgets/{id}/history` | Get period-by-period performance |

### 6.6 New Pydantic Schemas

```python
# backend/schemas/engagement.py

from typing import List, Optional
from pydantic import BaseModel, Field


class StreakResponse(BaseModel):
    """User's streak status."""
    current_streak: int = Field(..., description="Current consecutive days logged")
    longest_streak: int = Field(..., description="Best streak ever achieved")
    last_activity_date: Optional[str] = Field(None, description="Last transaction date")
    streak_freeze_available: bool = Field(..., description="Can use streak freeze")
    streak_at_risk: bool = Field(..., description="No transaction today yet")
    days_until_milestone: int = Field(..., description="Days to next milestone (7, 30, 90)")
    next_milestone: int = Field(..., description="Next milestone value")


class BudgetScoreResponse(BaseModel):
    """Budget health score."""
    score: int = Field(..., ge=0, le=100, description="Overall budget health 0-100")
    trend: str = Field(..., description="up, down, or stable vs last week")
    budgets_on_track: int = Field(..., description="Budgets under limit")
    budgets_over: int = Field(..., description="Budgets over limit")
    breakdown: List["BudgetScoreBreakdown"] = Field(..., description="Per-budget scores")


class BudgetScoreBreakdown(BaseModel):
    """Individual budget score."""
    budget_id: str
    budget_name: str
    utilization: float  # 0.0 to 1.0+
    score: int  # 0-100
    status: str  # "on_track", "warning", "over"


class WeeklySummaryResponse(BaseModel):
    """Weekly financial summary."""
    week_start: str
    week_end: str
    total_income: float
    total_expenses: float
    net_change: float
    income_vs_last_week: float
    expenses_vs_last_week: float
    top_expense_categories: List["CategorySpending"]
    budget_score: int
    current_streak: int
    transactions_logged: int
    receipts_captured: int


class CategorySpending(BaseModel):
    """Category spending summary."""
    category_id: str
    category_name: str
    amount: float
    percentage: float  # of total expenses


class ContributionCreateRequest(BaseModel):
    """Request to add savings contribution."""
    amount: float = Field(..., gt=0, description="Contribution amount")
    note: Optional[str] = Field(None, max_length=500, description="Optional note")


class ContributionResponse(BaseModel):
    """Savings contribution record."""
    id: str
    wishlist_id: str
    amount: float
    note: Optional[str]
    created_at: str


class BadgeResponse(BaseModel):
    """Badge information."""
    id: str
    key: str
    name: str
    description: str
    icon: str
    category: str
    earned_at: Optional[str] = None  # None if not earned


# Allow forward references
BudgetScoreResponse.model_rebuild()
```

---

## Appendix A: Competitor Analysis

| App | Streak Feature | Progress Visualization | Badges |
|-----|----------------|----------------------|--------|
| **Mint** | ❌ No | ✅ Budget progress bars | ❌ No |
| **YNAB** | ❌ No | ✅ Age of Money metric | ❌ No |
| **Copilot** | ❌ No | ✅ Spending trends | ❌ No |
| **Duolingo** | ✅ Core feature | ✅ XP and levels | ✅ Achievements |
| **Strava** | ✅ Activity streaks | ✅ Distance goals | ✅ Trophies |

**Observation:** Finance apps generally lack gamification. Kashi could differentiate by adopting proven patterns from habit-forming apps like Duolingo while maintaining financial seriousness.

---

## Appendix B: Risk Analysis

| Risk | Mitigation |
|------|------------|
| Streaks feel gimmicky | Keep visual design subtle and professional |
| Users game the system | Minimum transaction amount requirements |
| Feature bloat | Phase implementation, measure each feature's impact |
| Push notification fatigue | Make notifications opt-in, limit frequency |
| Privacy concerns with badges | All badges are personal, never public |

---

## Appendix C: Success Measurement

### Key Metrics to Track

| Metric | Current Baseline | Phase 1 Target | Phase 3 Target |
|--------|------------------|----------------|----------------|
| DAU/MAU ratio | Unknown | +15% | +30% |
| 7-day retention | Unknown | +10% | +25% |
| Transactions per user/week | Unknown | +20% | +40% |
| Budget under-limit rate | Unknown | +10% | +20% |
| Wishlist completion rate | Unknown | +15% | +30% |
| Average session duration | Unknown | +10% | +20% |

### Tracking Requirements

To measure these, the app needs event tracking. Recommended events:
- `transaction_created` (source: manual, invoice, recurring)
- `budget_created`, `budget_checked`
- `wishlist_created`, `contribution_added`, `goal_completed`
- `streak_milestone_reached` (7, 30, 90)
- `weekly_summary_viewed`
- `badge_earned`

---

*End of Document*
