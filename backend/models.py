from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    token: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    video_tasks: Mapped[list["VideoTask"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    feedback_records: Mapped[list["FeedbackRecord"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    preference_profile: Mapped["PreferenceProfile | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )


class VideoTask(Base):
    __tablename__ = "video_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(100), default="volcengine_seedance", nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True, index=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    optimized_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    video_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    video_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    local_video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="video_tasks")
    feedback_records: Mapped[list["FeedbackRecord"]] = relationship(
        back_populates="video_task",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_video_tasks_user_created_at", "user_id", "created_at"),
    )


class FeedbackRecord(Base):
    __tablename__ = "feedback_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    video_task_id: Mapped[int] = mapped_column(ForeignKey("video_tasks.id"), nullable=False, index=True)
    liked: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    user: Mapped["User"] = relationship(back_populates="feedback_records")
    video_task: Mapped["VideoTask"] = relationship(back_populates="feedback_records")

    __table_args__ = (
        CheckConstraint("rating IS NULL OR (rating >= 1 AND rating <= 5)", name="check_feedback_rating"),
    )


class PreferenceProfile(Base):
    __tablename__ = "preference_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True, index=True)
    preferred_styles: Mapped[str | None] = mapped_column(Text, nullable=True)
    disliked_styles: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_prompt_keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_video_types: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="preference_profile")

