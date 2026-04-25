import csv
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

if __package__ in {None, ""}:
    import sys

    ROOT_DIR = Path(__file__).resolve().parent.parent
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))

    from backend.auth_utils import hash_password
    from backend.database import SessionLocal, init_db
    from backend.models import User, VideoTask
    from backend.repositories import (
        create_user,
        create_video_task,
        get_user_by_username,
        get_video_task_by_task_id,
        update_preference_summary,
    )
else:
    from .auth_utils import hash_password
    from .database import SessionLocal, init_db
    from .models import User, VideoTask
    from .repositories import (
        create_user,
        create_video_task,
        get_user_by_username,
        get_video_task_by_task_id,
        update_preference_summary,
    )


BASE_DIR = Path(__file__).resolve().parent.parent
USERS_CSV_PATH = BASE_DIR / "users.csv"
VIDEO_HISTORY_CSV_PATH = BASE_DIR / "video_history.csv"


def _safe_rows(csv_path: Path) -> list[dict]:
    if not csv_path.exists():
        return []
    try:
        with csv_path.open("r", encoding="utf-8") as file:
            return list(csv.DictReader(file))
    except Exception:
        return []


def _normalize_status(status: str | None, filename: str | None = None) -> str:
    value = (status or "").strip().lower()
    if value in {"pending", "submitted", "processing", "succeeded", "failed", "downloaded"}:
        return value
    if value in {"completed", "done"}:
        return "downloaded" if filename else "succeeded"
    if value in {"generating", "in_queue"}:
        return "processing"
    return "pending"


def _parse_datetime(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def migrate_users_from_csv(db: Session, csv_path: Path = USERS_CSV_PATH) -> dict:
    rows = _safe_rows(csv_path)
    created = 0
    skipped = 0

    for row in rows:
        username = (row.get("username") or "").strip()
        if not username:
            skipped += 1
            continue

        if get_user_by_username(db, username):
            skipped += 1
            continue

        password_hash = (row.get("password_hash") or "").strip()
        if not password_hash:
            raw_password = (row.get("password") or "").strip()
            password_hash = hash_password(raw_password or f"{username}_temporary_password")

        token = (row.get("token") or "").strip() or None
        create_user(db, username=username, password_hash=password_hash, token=token)
        created += 1

    return {"created": created, "skipped": skipped, "total": len(rows)}


def migrate_video_history_from_csv(db: Session, csv_path: Path = VIDEO_HISTORY_CSV_PATH) -> dict:
    rows = _safe_rows(csv_path)
    created = 0
    skipped = 0
    placeholder_users = 0

    for row in rows:
        task_id = (row.get("task_id") or "").strip()
        if not task_id or get_video_task_by_task_id(db, task_id):
            skipped += 1
            continue

        username = (row.get("username") or "").strip() or "legacy_user"
        user = get_user_by_username(db, username)
        if not user:
            user = create_user(
                db,
                username=username,
                password_hash=hash_password(f"{username}_temporary_password"),
            )
            placeholder_users += 1

        prompt = (row.get("prompt") or "").strip() or "历史迁移视频"
        filename = (row.get("video_filename") or row.get("filename") or "").strip() or None
        status = _normalize_status(row.get("status"), filename)

        task = create_video_task(
            db,
            user_id=user.id,
            prompt=prompt,
            provider="volcengine_seedance",
            status=status,
            progress=100 if status in {"succeeded", "downloaded"} else 0,
            task_id=task_id,
        )

        task.video_filename = filename
        task.video_path = f"video/{filename}" if filename else None
        task.video_url = (row.get("video_url") or "").strip() or None
        task.local_video_url = (
            f"http://127.0.0.1:8000/video/{filename}" if filename else None
        )
        task.error_message = (row.get("error_message") or "").strip() or None
        migrated_created_at = _parse_datetime((row.get("created_at") or "").strip())
        if migrated_created_at:
            task.created_at = migrated_created_at
            task.updated_at = migrated_created_at
        else:
            task.updated_at = task.created_at
        if status in {"failed", "succeeded", "downloaded"}:
            task.finished_at = task.created_at
        db.commit()
        db.refresh(task)
        created += 1

        if status in {"downloaded", "succeeded"}:
            update_preference_summary(
                db,
                user.id,
                summary="已从历史 CSV 迁移视频记录",
                preferred_video_types=["text-to-video"],
            )

    return {
        "created": created,
        "skipped": skipped,
        "placeholder_users": placeholder_users,
        "total": len(rows),
    }


def migrate_csv_to_sqlite(db: Session) -> dict:
    user_summary = migrate_users_from_csv(db)
    task_summary = migrate_video_history_from_csv(db)
    return {"users": user_summary, "video_tasks": task_summary}


def migrate_csv_to_sqlite_if_needed(db: Session) -> dict:
    should_migrate_users = db.scalar(select(User.id).limit(1)) is None
    should_migrate_tasks = db.scalar(select(VideoTask.id).limit(1)) is None

    summary = {
        "users": {"created": 0, "skipped": 0, "total": 0},
        "video_tasks": {"created": 0, "skipped": 0, "placeholder_users": 0, "total": 0},
    }

    if should_migrate_users:
        summary["users"] = migrate_users_from_csv(db)
    if should_migrate_tasks:
        summary["video_tasks"] = migrate_video_history_from_csv(db)
    return summary


def main() -> None:
    init_db()
    with SessionLocal() as db:
        summary = migrate_csv_to_sqlite(db)
    print("Migration summary:")
    print(summary)


if __name__ == "__main__":
    main()
