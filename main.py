from datetime import datetime, timezone
from pathlib import Path
import re

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.database import SessionLocal, get_db, init_db
from backend.migration_csv_to_sqlite import migrate_csv_to_sqlite_if_needed
from backend.models import User, VideoTask
from backend.repositories import (
    create_feedback,
    create_video_task,
    get_feedback_by_user,
    get_or_create_preference_profile,
    get_user_by_token,
    get_video_task_by_id,
    get_video_task_by_task_id,
    get_video_tasks_by_user,
    update_preference_summary,
    update_user_token,
    verify_user_login,
)
from backend.schemas import FeedbackCreateRequest, LoginRequest, VideoTaskCreateRequest
from backend.video_service import ensure_video_metadata, start_task_worker, submit_generation_task


BASE_DIR = Path(__file__).resolve().parent
VIDEO_FOLDER = BASE_DIR / "video"
VIDEO_FOLDER.mkdir(exist_ok=True)

GALLERY_ITEMS = [
    {"id": 1, "type": "video", "url": "https://picsum.photos/400/300?random=1"},
    {"id": 2, "type": "video", "url": "https://picsum.photos/400/600?random=2"},
    {"id": 3, "type": "video", "url": "https://picsum.photos/400/400?random=3"},
    {"id": 4, "type": "video", "url": "https://picsum.photos/400/500?random=4"},
    {"id": 5, "type": "video", "url": "https://picsum.photos/400/700?random=5"},
    {"id": 6, "type": "image", "url": "https://picsum.photos/400/350?random=6"},
]

STATUS_PROGRESS_MAP = {
    "pending": 2,
    "submitted": 8,
    "processing": 35,
    "in_queue": 12,
    "generating": 55,
    "succeeded": 98,
    "downloaded": 100,
    "failed": 0,
}


app = FastAPI(title="AI Toolkit Video Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/video", StaticFiles(directory=str(VIDEO_FOLDER)), name="video")


@app.on_event("startup")
def startup_event() -> None:
    init_db()
    with SessionLocal() as db:
        summary = migrate_csv_to_sqlite_if_needed(db)
    if any(section.get("created") for section in summary.values()):
        print(f"✅ CSV 数据已迁移到 SQLite: {summary}")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_current_user(db: Session, token: str) -> User | None:
    return get_user_by_token(db, token)


def build_feedback_summary(video_task: VideoTask, liked: bool | None, rating: int | None, feedback_text: str | None) -> tuple[str, list[str], list[str]]:
    keywords = extract_prompt_keywords(video_task.optimized_prompt or video_task.prompt)
    if liked:
        summary = "用户偏好这类视频内容，建议保留类似提示词方向。"
        return summary, keywords, []
    if liked is False:
        summary = "用户不喜欢这类视频内容，建议减少类似提示词方向。"
        return summary, [], keywords
    if rating and rating >= 4:
        summary = "用户对生成结果评分较高。"
        return summary, keywords, []
    if rating and rating <= 2:
        summary = "用户对生成结果评分较低。"
        return summary, [], keywords
    if feedback_text:
        return "用户提交了补充反馈。", keywords[:3], []
    return "记录了一条中性反馈。", [], []


def extract_prompt_keywords(prompt: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,}", prompt or "")
    deduped: list[str] = []
    for token in tokens:
        if token not in deduped:
            deduped.append(token)
    return deduped[:8]


@app.post("/api/login")
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = verify_user_login(db, req.username, req.password)
    if not user:
        return {"status": "error", "message": "用户名或密码错误"}

    user = update_user_token(db, user)
    return {"status": "success", "token": user.token, "username": user.username}


@app.get("/api/user/info")
async def user_info(token: str | None = None, db: Session = Depends(get_db)):
    user = get_current_user(db, token or "")
    if not user:
        return {"status": "error", "message": "需要登录"}
    return {"status": "success", "username": user.username}


@app.post("/api/logout")
async def logout(token: str | None = None, db: Session = Depends(get_db)):
    user = get_current_user(db, token or "")
    if user:
        user.token = None
        user.updated_at = utc_now()
        db.commit()
    return {"status": "success"}


@app.post("/api/generate")
async def generate_video(req: VideoTaskCreateRequest, db: Session = Depends(get_db)):
    user = get_current_user(db, req.token)
    if not user:
        return {"status": "error", "message": "需要登录"}

    video_task = create_video_task(
        db,
        user_id=user.id,
        prompt=req.prompt,
        optimized_prompt=None,
        provider="volcengine_seedance",
        status="pending",
        progress=STATUS_PROGRESS_MAP["pending"],
    )

    try:
        provider_task_id = submit_generation_task(
            db_video_task_id=video_task.id,
            prompt=req.prompt,
            ratio=req.ratio,
            duration=req.duration,
        )
        start_task_worker(provider_task_id)
        return {"status": "success", "task_id": provider_task_id, "message": "任务已提交"}
    except Exception as exc:
        video_task.status = "failed"
        video_task.progress = 0
        video_task.error_message = str(exc)
        video_task.finished_at = utc_now()
        video_task.updated_at = utc_now()
        db.commit()
        db.refresh(video_task)
        return {"status": "error", "message": f"提交任务失败: {exc}"}


@app.get("/api/task/{task_id}/progress")
async def get_task_progress(task_id: str, db: Session = Depends(get_db)):
    task = get_video_task_by_task_id(db, task_id)
    if not task:
        return {"status": "error", "message": "任务不存在"}

    progress = task.progress if task.progress is not None else STATUS_PROGRESS_MAP.get(task.status, 0)
    return {
        "status": "success",
        "task_id": task.task_id,
        "task_status": task.status,
        "progress": progress,
        "data": ensure_video_metadata(task),
    }


@app.get("/api/videos")
async def get_videos(token: str | None = None, db: Session = Depends(get_db)):
    user = get_current_user(db, token or "")
    if not user:
        return {"status": "error", "message": "需要登录", "videos": []}

    tasks = get_video_tasks_by_user(db, user.id)
    videos = [ensure_video_metadata(task) for task in tasks]
    return {"status": "success", "videos": videos, "count": len(videos)}


@app.post("/feedback")
async def create_feedback_endpoint(req: FeedbackCreateRequest, db: Session = Depends(get_db)):
    user = get_current_user(db, req.token)
    if not user:
        return {"status": "error", "message": "需要登录"}

    video_task = get_video_task_by_id(db, req.video_task_id)
    if not video_task or video_task.user_id != user.id:
        return {"status": "error", "message": "视频任务不存在"}

    feedback = create_feedback(
        db,
        user_id=user.id,
        video_task_id=video_task.id,
        liked=req.liked,
        rating=req.rating,
        feedback_text=req.feedback_text,
    )
    summary, preferred_keywords, disliked_keywords = build_feedback_summary(
        video_task,
        req.liked,
        req.rating,
        req.feedback_text,
    )
    profile = update_preference_summary(
        db,
        user.id,
        summary=summary,
        preferred_prompt_keywords=preferred_keywords,
        disliked_styles=disliked_keywords if req.liked is False else None,
        preferred_video_types=["text-to-video"],
    )

    return {
        "status": "success",
        "feedback": {
            "id": feedback.id,
            "liked": feedback.liked,
            "rating": feedback.rating,
            "feedback_text": feedback.feedback_text,
            "created_at": feedback.created_at.isoformat(),
        },
        "preference_profile": {
            "id": profile.id,
            "summary": profile.summary,
            "preferred_prompt_keywords": profile.preferred_prompt_keywords,
            "disliked_styles": profile.disliked_styles,
            "updated_at": profile.updated_at.isoformat(),
        },
    }


@app.get("/api/feedback")
async def get_feedback(token: str | None = None, db: Session = Depends(get_db)):
    user = get_current_user(db, token or "")
    if not user:
        return {"status": "error", "message": "需要登录", "feedback": []}

    feedback_records = get_feedback_by_user(db, user.id)
    return {
        "status": "success",
        "feedback": [
            {
                "id": record.id,
                "video_task_id": record.video_task_id,
                "liked": record.liked,
                "rating": record.rating,
                "feedback_text": record.feedback_text,
                "created_at": record.created_at.isoformat(),
            }
            for record in feedback_records
        ],
    }


@app.get("/api/preferences")
async def get_preferences(token: str | None = None, db: Session = Depends(get_db)):
    user = get_current_user(db, token or "")
    if not user:
        return {"status": "error", "message": "需要登录"}

    profile = get_or_create_preference_profile(db, user.id)
    return {
        "status": "success",
        "profile": {
            "id": profile.id,
            "preferred_styles": profile.preferred_styles,
            "disliked_styles": profile.disliked_styles,
            "preferred_prompt_keywords": profile.preferred_prompt_keywords,
            "preferred_video_types": profile.preferred_video_types,
            "summary": profile.summary,
            "updated_at": profile.updated_at.isoformat(),
        },
    }


@app.get("/api/gallery")
async def get_gallery():
    return {"status": "success", "data": GALLERY_ITEMS}


@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    video_count = db.scalar(select(func.count(VideoTask.id))) or 0
    user_count = db.scalar(select(func.count(User.id))) or 0
    downloaded_count = db.scalar(
        select(func.count(VideoTask.id)).where(VideoTask.status == "downloaded")
    ) or 0
    return {
        "video_count": video_count,
        "user_count": user_count,
        "downloaded_count": downloaded_count,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


app.mount("/", StaticFiles(directory=str(BASE_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    print("🚀 启动完整应用服务器...")
    print("📍 前端首页: http://127.0.0.1:8000/")
    print("📍 登录页面: http://127.0.0.1:8000/login.html")
    print("📍 API 地址: http://127.0.0.1:8000/api")
    print("📍 文档地址: http://127.0.0.1:8000/docs")
    uvicorn.run(app, host="127.0.0.1", port=8000)
