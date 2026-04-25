import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth_utils import generate_token, hash_password, needs_password_rehash, verify_password
from .models import FeedbackRecord, PreferenceProfile, User, VideoTask


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _merge_json_list(existing_value: str | None, incoming_values: list[str] | None) -> str | None:
    if not incoming_values:
        return existing_value

    try:
        current = json.loads(existing_value) if existing_value else []
    except json.JSONDecodeError:
        current = []

    if not isinstance(current, list):
        current = []

    for item in incoming_values:
        if item and item not in current:
            current.append(item)

    return json.dumps(current, ensure_ascii=False)


def create_user(db: Session, username: str, password_hash: str, token: str | None = None) -> User:
    user = User(username=username, password_hash=password_hash, token=token)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_user_by_token(db: Session, token: str) -> User | None:
    if not token:
        return None
    return db.scalar(select(User).where(User.token == token))


def verify_user_login(db: Session, username: str, password: str) -> User | None:
    user = get_user_by_username(db, username)
    if not user or not verify_password(password, user.password_hash):
        return None

    if needs_password_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        user.updated_at = utc_now()
        db.commit()
        db.refresh(user)

    return user


def update_user_token(db: Session, user: User, token: str | None = None) -> User:
    user.token = token or generate_token(user.username)
    user.updated_at = utc_now()
    db.commit()
    db.refresh(user)
    return user


def create_video_task(
    db: Session,
    user_id: int,
    prompt: str,
    optimized_prompt: str | None = None,
    provider: str = "volcengine_seedance",
    status: str = "pending",
    progress: int = 0,
    task_id: str | None = None,
) -> VideoTask:
    video_task = VideoTask(
        user_id=user_id,
        prompt=prompt,
        optimized_prompt=optimized_prompt,
        provider=provider,
        status=status,
        progress=progress,
        task_id=task_id,
    )
    db.add(video_task)
    db.commit()
    db.refresh(video_task)
    return video_task


def get_video_task_by_task_id(db: Session, task_id: str) -> VideoTask | None:
    return db.scalar(select(VideoTask).where(VideoTask.task_id == task_id))


def get_video_task_by_id(db: Session, video_task_id: int) -> VideoTask | None:
    return db.get(VideoTask, video_task_id)


def get_video_tasks_by_user(db: Session, user_id: int) -> list[VideoTask]:
    stmt = (
        select(VideoTask)
        .where(VideoTask.user_id == user_id)
        .order_by(VideoTask.created_at.desc())
    )
    return list(db.scalars(stmt).all())


def attach_provider_task_id(
    db: Session,
    video_task_id: int,
    provider_task_id: str,
    status: str = "submitted",
) -> VideoTask | None:
    video_task = get_video_task_by_id(db, video_task_id)
    if not video_task:
        return None

    video_task.task_id = provider_task_id
    video_task.status = status
    video_task.updated_at = utc_now()
    db.commit()
    db.refresh(video_task)
    return video_task


def update_video_task_status(
    db: Session,
    task_id: str,
    status: str,
    progress: int | None = None,
    error_message: str | None = None,
    video_url: str | None = None,
) -> VideoTask | None:
    video_task = get_video_task_by_task_id(db, task_id)
    if not video_task:
        return None

    video_task.status = status
    if progress is not None:
        video_task.progress = progress
    if error_message is not None:
        video_task.error_message = error_message
    if video_url is not None:
        video_task.video_url = video_url
    if status in {"succeeded", "failed", "downloaded"}:
        video_task.finished_at = utc_now()
    video_task.updated_at = utc_now()
    db.commit()
    db.refresh(video_task)
    return video_task


def update_video_task_success(
    db: Session,
    task_id: str,
    video_filename: str | None,
    video_path: str | None,
    video_url: str | None,
    local_video_url: str | None,
    status: str = "downloaded",
) -> VideoTask | None:
    video_task = get_video_task_by_task_id(db, task_id)
    if not video_task:
        return None

    video_task.status = status
    video_task.progress = 100
    video_task.video_filename = video_filename
    video_task.video_path = video_path
    video_task.video_url = video_url
    video_task.local_video_url = local_video_url
    video_task.error_message = None
    video_task.finished_at = utc_now()
    video_task.updated_at = utc_now()
    db.commit()
    db.refresh(video_task)
    return video_task


def update_video_task_failure(db: Session, task_id: str, error_message: str) -> VideoTask | None:
    video_task = get_video_task_by_task_id(db, task_id)
    if not video_task:
        return None

    video_task.status = "failed"
    video_task.error_message = error_message
    video_task.finished_at = utc_now()
    video_task.updated_at = utc_now()
    db.commit()
    db.refresh(video_task)
    return video_task


def create_feedback(
    db: Session,
    user_id: int,
    video_task_id: int,
    liked: bool | None = None,
    rating: int | None = None,
    feedback_text: str | None = None,
) -> FeedbackRecord:
    feedback = FeedbackRecord(
        user_id=user_id,
        video_task_id=video_task_id,
        liked=liked,
        rating=rating,
        feedback_text=feedback_text,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


def get_feedback_by_user(db: Session, user_id: int) -> list[FeedbackRecord]:
    stmt = (
        select(FeedbackRecord)
        .where(FeedbackRecord.user_id == user_id)
        .order_by(FeedbackRecord.created_at.desc())
    )
    return list(db.scalars(stmt).all())


def get_or_create_preference_profile(db: Session, user_id: int) -> PreferenceProfile:
    profile = db.scalar(select(PreferenceProfile).where(PreferenceProfile.user_id == user_id))
    if profile:
        return profile

    profile = PreferenceProfile(user_id=user_id)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update_preference_summary(
    db: Session,
    user_id: int,
    summary: str | None = None,
    preferred_styles: list[str] | None = None,
    disliked_styles: list[str] | None = None,
    preferred_prompt_keywords: list[str] | None = None,
    preferred_video_types: list[str] | None = None,
) -> PreferenceProfile:
    profile = get_or_create_preference_profile(db, user_id)
    profile.preferred_styles = _merge_json_list(profile.preferred_styles, preferred_styles)
    profile.disliked_styles = _merge_json_list(profile.disliked_styles, disliked_styles)
    profile.preferred_prompt_keywords = _merge_json_list(
        profile.preferred_prompt_keywords,
        preferred_prompt_keywords,
    )
    profile.preferred_video_types = _merge_json_list(
        profile.preferred_video_types,
        preferred_video_types,
    )
    if summary:
        profile.summary = summary
    profile.updated_at = utc_now()
    db.commit()
    db.refresh(profile)
    return profile

