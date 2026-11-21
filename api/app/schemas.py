from datetime import datetime
from typing import List, Optional, Any, Dict, Literal
from pydantic import BaseModel, ConfigDict, Field


UserRole = Literal["OWNER", "ANALYST", "ADMIN"]


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=1, max_length=128)


class BootstrapRequest(LoginRequest):
    full_name: str = Field(..., min_length=1, max_length=255)
    setup_key: str = Field(..., min_length=1, max_length=512)


class UserCreate(LoginRequest):
    full_name: str = Field(..., min_length=1, max_length=255)
    role: UserRole = "OWNER"
    restaurant_ids: List[int] = Field(default_factory=list)


class UserUpdate(BaseModel):
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    restaurant_ids: Optional[List[int]] = None


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    restaurant_ids: List[int] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class AuthSetupResponse(BaseModel):
    setup_required: bool


# --------------------------------------------------------
# Aspect & Analysis Inner Result Structures
# --------------------------------------------------------
class AspectBreakdown(BaseModel):
    aspect: str  # food, service, wait_time, hygiene, ambience, price
    sentiment: Literal["POSITIVE", "NEGATIVE", "NEUTRAL", "MIXED"]
    score: Optional[float] = None  # e.g., 1 to 5 scale
    summary: str
    highlights: List[str] = Field(default_factory=list)


class ImprovementSuggestion(BaseModel):
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    aspect: str
    issue: str
    recommended_action: str
    expected_impact: str


class StrengthItem(BaseModel):
    aspect: str
    strength: str
    marketing_tip: Optional[str] = None


class AnalysisResultPayload(BaseModel):
    overall_sentiment: Literal["POSITIVE", "NEGATIVE", "NEUTRAL", "MIXED"]
    summary: str
    estimated_rating_trend: Literal["IMPROVING", "STABLE", "DECLINING"]
    aspect_breakdown: List[AspectBreakdown] = Field(default_factory=list)
    prioritized_improvements: List[ImprovementSuggestion] = Field(default_factory=list)
    strengths_to_keep: List[StrengthItem] = Field(default_factory=list)


# --------------------------------------------------------
# Review Schemas
# --------------------------------------------------------
class ReviewBase(BaseModel):
    author_name: str
    author_uri: Optional[str] = None
    rating: float = Field(..., ge=1.0, le=5.0)
    text: str
    published_at: datetime
    external_review_id: Optional[str] = None


class ReviewCreate(ReviewBase):
    restaurant_id: Optional[int] = None


class ReviewResponse(ReviewBase):
    id: int
    restaurant_id: int

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------
# Analysis Schemas
# --------------------------------------------------------
class AnalysisBase(BaseModel):
    overall_sentiment: str
    result_json: Dict[str, Any]
    review_count: int
    last_review_at: Optional[datetime] = None
    model: str = "gpt-4o-mini"


class AnalysisCreate(AnalysisBase):
    restaurant_id: int


class AnalysisResponse(AnalysisBase):
    id: int
    restaurant_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnalysisHistoryResponse(BaseModel):
    id: int
    created_at: datetime
    analysis: AnalysisResponse

    model_config = ConfigDict(from_attributes=True)


class TriggerAnalysisRequest(BaseModel):
    force_refresh: bool = False
    model: Optional[str] = None


# --------------------------------------------------------
# Restaurant Schemas
# --------------------------------------------------------
class RestaurantBase(BaseModel):
    google_place_id: str
    name: str
    address: Optional[str] = None
    google_rating: Optional[float] = Field(default=None, ge=1.0, le=5.0)
    user_rating_count: Optional[int] = Field(default=None, ge=0)


class RestaurantCreate(RestaurantBase):
    pass


class RestaurantUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    google_rating: Optional[float] = None
    user_rating_count: Optional[int] = None
    last_synced_at: Optional[datetime] = None


class RestaurantResponse(RestaurantBase):
    id: int
    last_synced_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    review_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)


class RestaurantDetailResponse(RestaurantResponse):
    reviews: List[ReviewResponse] = Field(default_factory=list)
    latest_analysis: Optional[AnalysisResponse] = None

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------
# Sync Job Schemas
# --------------------------------------------------------
class SyncTargetBase(BaseModel):
    target_type: str  # place_id, query, region
    value: str
    language_code: str = "en"
    is_active: bool = True


class SyncTargetCreate(SyncTargetBase):
    pass


class SyncTargetResponse(SyncTargetBase):
    id: int
    last_synced_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SyncRunResponse(BaseModel):
    id: int
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    restaurants_upserted: int
    reviews_upserted: int
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------
# Notification Schemas
# --------------------------------------------------------
class NotificationResponse(BaseModel):
    id: int
    restaurant_id: int
    review_id: int
    sync_run_id: Optional[int] = None
    channel: str
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    sent_at: Optional[datetime] = None
    review: ReviewResponse

    model_config = ConfigDict(from_attributes=True)
