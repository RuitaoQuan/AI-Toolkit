import threading
import time
from pathlib import Path

from .database import SessionLocal
from .repositories import (
    attach_provider_task_id,
    get_video_task_by_id,
    update_video_task_failure,
    update_video_task_status,
    update_video_task_success,
)
from .volcengine_client import download_video, get_task_result, submit_text_to_video_task


BASE_DIR = Path(__file__).resolve().parent.parent


def submit_generation_task(
    db_video_task_id: int,
    prompt: str,
    ratio: str = "16:9",
    duration: int = 5,
) -> str:
    provider_task_id = submit_text_to_video_task(prompt=prompt, ratio=ratio, duration=duration)
    with SessionLocal() as db:
        attach_provider_task_id(db, db_video_task_id, provider_task_id, status="submitted")
    return provider_task_id


def start_task_worker(provider_task_id: str) -> threading.Thread:
    thread = threading.Thread(target=process_generation_task, args=(provider_task_id,), daemon=True)
    thread.start()
    return thread


def process_generation_task(provider_task_id: str, poll_interval: int = 3, max_polls: int = 120) -> None:
    try:
        video_url = poll_until_done(provider_task_id, poll_interval=poll_interval, max_polls=max_polls)
        with SessionLocal() as db:
            update_video_task_status(
                db,
                provider_task_id,
                status="succeeded",
                progress=98,
                video_url=video_url,
            )

        file_path = download_video(video_url, provider_task_id)
        local_video_url = f"http://127.0.0.1:8000/video/{file_path.name}"

        with SessionLocal() as db:
            update_video_task_success(
                db,
                provider_task_id,
                video_filename=file_path.name,
                video_path=str(file_path),
                video_url=video_url,
                local_video_url=local_video_url,
                status="downloaded",
            )
    except Exception as exc:
        with SessionLocal() as db:
            update_video_task_failure(db, provider_task_id, str(exc))


def poll_until_done(provider_task_id: str, poll_interval: int = 3, max_polls: int = 120) -> str:
    for poll_count in range(max_polls):
        result = get_task_result(provider_task_id)
        result_code = result.get("code")
        task_data = result.get("data") or {}
        task_status = task_data.get("status", "")

        if result_code == 10000 and task_status == "done":
            video_url = task_data.get("video_url")
            if not video_url:
                raise RuntimeError("任务完成，但未返回视频地址")
            return video_url

        if task_status in {"not_found", "expired"}:
            raise RuntimeError(f"任务状态异常: {task_status}")

        if result_code != 10000 and task_status == "done":
            raise RuntimeError(result.get("message", "视频生成失败"))

        progress = min(95, max(5, int(((poll_count + 1) / max_polls) * 100)))
        with SessionLocal() as db:
            update_video_task_status(
                db,
                provider_task_id,
                status=task_status or "processing",
                progress=progress,
            )
        time.sleep(poll_interval)

    raise RuntimeError("任务超时，请稍后重试")


def get_local_video_url(video_filename: str | None) -> str | None:
    if not video_filename:
        return None
    return f"http://127.0.0.1:8000/video/{video_filename}"


def ensure_video_metadata(video_task) -> dict:
    local_url = video_task.local_video_url or get_local_video_url(video_task.video_filename)
    file_path = Path(video_task.video_path) if video_task.video_path else None
    if file_path and not file_path.is_absolute():
        file_path = BASE_DIR / file_path
    file_exists = bool(file_path and file_path.exists())
    return {
        "id": video_task.id,
        "task_id": video_task.task_id or f"local_{video_task.id}",
        "filename": video_task.video_filename,
        "url": local_url if file_exists else None,
        "size": file_path.stat().st_size if file_exists else 0,
        "prompt": video_task.optimized_prompt or video_task.prompt,
        "created_at": video_task.created_at.isoformat(),
        "status": video_task.status,
        "file_exists": file_exists,
        "progress": video_task.progress,
        "error_message": video_task.error_message,
    }
