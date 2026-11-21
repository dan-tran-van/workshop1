
from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime, ForeignKey, JSON, Table, UniqueConstraint

from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


user_restaurants = Table(
    "user_restaurants",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("restaurant_id", Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), primary_key=True),
)


class Restaurant(Base):
    __tablename__ = "restaurants"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    google_place_id = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False, index=True)
    address = Column(String(500), nullable=True)
    google_rating = Column(Float, nullable=True)
    user_rating_count = Column(Integer, nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    reviews = relationship("Review", back_populates="restaurant", cascade="all, delete-orphan", order_by="desc(Review.published_at)")
    analyses = relationship("Analysis", back_populates="restaurant", cascade="all, delete-orphan", order_by="desc(Analysis.created_at)")
    owners = relationship("User", secondary=user_restaurants, back_populates="restaurants")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(320), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(30), nullable=False, default="OWNER")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    restaurants = relationship("Restaurant", secondary=user_restaurants, back_populates="owners")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)
    external_review_id = Column(String(255), unique=True, index=True, nullable=True)
    author_name = Column(String(255), nullable=False)
    author_uri = Column(String(500), nullable=True)
    rating = Column(Float, nullable=False)
    text = Column(Text, nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=False)

    # Relationships
    restaurant = relationship("Restaurant", back_populates="reviews")


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)
    overall_sentiment = Column(String(50), nullable=False)
    result_json = Column(JSON, nullable=False)
    review_count = Column(Integer, nullable=False, default=0)
    last_review_at = Column(DateTime(timezone=True), nullable=True)
    model = Column(String(100), nullable=False, default="gpt-4o-mini")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    restaurant = relationship("Restaurant", back_populates="analyses")


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_id = Column(Integer, ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    analysis = relationship("Analysis")


class SyncTarget(Base):
    __tablename__ = "sync_targets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    target_type = Column(String(50), nullable=False)  # e.g., "place_id", "query", "region"
    value = Column(String(255), nullable=False)
    language_code = Column(String(10), default="en", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    status = Column(String(50), default="PENDING", nullable=False)  # PENDING, RUNNING, COMPLETED, FAILED
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    restaurants_upserted = Column(Integer, default=0, nullable=False)
    reviews_upserted = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("review_id", "channel", name="uq_notifications_review_channel"),)

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)
    review_id = Column(Integer, ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    sync_run_id = Column(Integer, ForeignKey("sync_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    channel = Column(String(50), nullable=False, default="in_app")
    status = Column(String(50), nullable=False, default="PENDING")  # PENDING, SENT, FAILED
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    sent_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    review = relationship("Review")
