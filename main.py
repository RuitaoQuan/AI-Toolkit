import os
import csv
import json
import uuid
import time
import datetime
import threading
import requests
import hashlib
import hmac
from typing import Dict, Optional
from pydantic import BaseModel
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from volcenginesdkcore.signv4 import SignerV4
from volcengine_credentials import VOLCENGINE_ACCESS_KEY, VOLCENGINE_SECRET_KEY

# Volcano Engine API 配置
ACCESS_KEY = VOLCENGINE_ACCESS_KEY
SECRET_KEY = VOLCENGINE_SECRET_KEY
VOLCENGINE_API_HOST = os.getenv("VOLCENGINE_API_HOST", "visual.volcengineapi.com")
VOLCENGINE_REGION = os.getenv("VOLCENGINE_REGION", "cn-north-1")
VOLCENGINE_SERVICE = os.getenv("VOLCENGINE_SERVICE", "cv")
VOLCENGINE_VERSION = os.getenv("VOLCENGINE_VERSION", "2022-08-31")
VOLCENGINE_TEXT2VIDEO_REQ_KEY = os.getenv("VOLCENGINE_TEXT2VIDEO_REQ_KEY", "jimeng_t2v_v30")

# CSV 用户数据文件
USERS_CSV_FILE = os.path.join(os.path.dirname(__file__), "users.csv")

# 视频存储文件夹
VIDEO_FOLDER = os.path.join(os.path.dirname(__file__), "video")
os.makedirs(VIDEO_FOLDER, exist_ok=True)

# 视频历史 CSV 文件
VIDEO_HISTORY_CSV = os.path.join(os.path.dirname(__file__), "video_history.csv")
VIDEO_HISTORY_HEADERS = ['task_id', 'username', 'prompt', 'video_filename', 'size', 'created_at', 'status']


def init_video_history_csv():
    """初始化视频历史 CSV"""
    if not os.path.exists(VIDEO_HISTORY_CSV):
        with open(VIDEO_HISTORY_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(VIDEO_HISTORY_HEADERS)
        print(f"✅ 创建视频历史文件: {VIDEO_HISTORY_CSV}")


init_video_history_csv()


# === 用户认证函数 ===
def load_users() -> Dict[str, str]:
    """从 CSV 加载用户"""
    users = {}
    if not os.path.exists(USERS_CSV_FILE):
        return users
    
    try:
        with open(USERS_CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row and 'username' in row and 'password' in row:
                    users[row['username']] = row['password']
    except Exception as e:
        print(f"❌ 读取 users.csv 失败: {e}")
    
    return users


def verify_user(username: str, password: str) -> bool:
    """验证用户"""
    users = load_users()
    if username not in users:
        return False
    return users[username] == password


def read_video_history_rows() -> list:
    """读取视频历史 CSV 全量记录"""
    if not os.path.exists(VIDEO_HISTORY_CSV):
        return []

    with open(VIDEO_HISTORY_CSV, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def write_video_history_rows(rows: list):
    """重写视频历史 CSV"""
    with open(VIDEO_HISTORY_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=VIDEO_HISTORY_HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def upsert_video_history(task_id: str, username: str, prompt: str, video_filename: str = "", size: int = 0,
                         status: str = "processing", created_at: Optional[str] = None):
    """按 task_id 更新或创建视频历史，确保用户与视频关系持久化到 CSV"""
    try:
        rows = read_video_history_rows()
        existing_row = None
        for row in rows:
            if row.get('task_id') == task_id:
                existing_row = row
                break

        if existing_row is None:
            existing_row = {
                'task_id': task_id,
                'username': username,
                'prompt': prompt,
                'video_filename': video_filename,
                'size': str(size),
                'created_at': created_at or datetime.datetime.now().isoformat(),
                'status': status
            }
            rows.append(existing_row)
        else:
            existing_row['username'] = username or existing_row.get('username', '')
            existing_row['prompt'] = prompt or existing_row.get('prompt', '')
            existing_row['video_filename'] = video_filename
            existing_row['size'] = str(size)
            existing_row['status'] = status
            if created_at:
                existing_row['created_at'] = created_at

        write_video_history_rows(rows)
        print(f"✅ 视频记录已写入 CSV: {task_id} - {username} - {status}")
    except Exception as e:
        print(f"❌ 保存视频历史失败: {e}")


def get_user_videos_from_csv(username: str) -> list:
    """读取用户的视频历史"""
    videos = []
    try:
        if not os.path.exists(VIDEO_HISTORY_CSV):
            return videos

        for row in read_video_history_rows():
            if not row or row.get('username') != username:
                continue

            filename = row.get('video_filename', '')
            video_path = os.path.join(VIDEO_FOLDER, filename) if filename else ""
            file_exists = bool(filename and os.path.exists(video_path))

            try:
                size = int(row.get('size') or 0)
            except ValueError:
                size = 0

            videos.append({
                "task_id": row.get('task_id', ''),
                "filename": filename,
                "url": f"http://127.0.0.1:8000/video/{filename}" if file_exists else "",
                "size": size,
                "prompt": row.get('prompt', '') or '生成的视频',
                "created_at": row.get('created_at', ''),
                "status": row.get('status', 'completed'),
                "file_exists": file_exists
            })

        videos.sort(key=lambda x: x['created_at'], reverse=True)
    except Exception as e:
        print(f"❌ 读取视频历史失败: {e}")
    
    return videos


def generate_token(username: str) -> str:
    """生成 token"""
    token = f"{username}_{uuid.uuid4().hex[:16]}"
    session_store[token] = username
    return token


def verify_token(token: str) -> Optional[str]:
    """验证 token"""
    return session_store.get(token)


# FastAPI 应用
app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件
app.mount("/video", StaticFiles(directory=VIDEO_FOLDER), name="video")

# 全局存储
session_store: Dict[str, str] = {}
task_store: Dict[str, dict] = {}


# 数据模型
class LoginRequest(BaseModel):
    username: str
    password: str


class GenerateRequest(BaseModel):
    prompt: str
    model_type: str = "Seedance3.0"
    ratio: str = "16:9"
    duration: int = 5
    negative_prompt: str = ""
    token: str = ""


# Volcano Engine 函数
def call_visual_api(action: str, req_body: dict) -> dict:
    """调用 API"""
    try:
        query = {
            "Action": action,
            "Version": VOLCENGINE_VERSION
        }
        url = f"https://{VOLCENGINE_API_HOST}/?Action={action}&Version={VOLCENGINE_VERSION}"
        body_json = json.dumps(req_body, ensure_ascii=False)
        headers = {
            "Content-Type": "application/json",
            "Host": VOLCENGINE_API_HOST
        }
        SignerV4.sign(
            path="/",
            method="POST",
            headers=headers,
            body=body_json,
            post_params={},
            query=query,
            ak=ACCESS_KEY,
            sk=SECRET_KEY,
            region=VOLCENGINE_REGION,
            service=VOLCENGINE_SERVICE
        )

        response = requests.post(url, data=body_json.encode("utf-8"), headers=headers, timeout=30)
        
        if response.status_code != 200:
            error_text = response.text[:500]
            print(f"❌ API 调用失败: {response.status_code} - {error_text}")
            return {
                "error": f"HTTP {response.status_code}: {error_text}"
            }
        
        result = response.json()
        if result.get("ResponseMetadata", {}).get("Error"):
            error_msg = result["ResponseMetadata"]["Error"].get("Message", "未知错误")
            print(f"❌ API 错误: {error_msg}")
            return {
                "error": error_msg,
                "raw": result
            }
        
        return result
    except Exception as e:
        print(f"❌ API 调用异常: {e}")
        return {
            "error": str(e)
        }


def submit_text_to_video_task(prompt: str, negative_prompt: str = "", model_type: str = "Seedance3.0", ratio: str = "16:9", duration: int = 5) -> str:
    """提交任务"""
    frames_map = {
        5: 121,
        10: 241
    }
    req_body = {
        "req_key": VOLCENGINE_TEXT2VIDEO_REQ_KEY,
        "prompt": prompt,
        "seed": -1,
        "frames": frames_map.get(duration, 121),
        "aspect_ratio": ratio
    }
    
    result = call_visual_api("CVSync2AsyncSubmitTask", req_body)
    if result.get("error"):
        raise RuntimeError(result["error"])

    if result.get("code") != 10000:
        raise RuntimeError(result.get("message", "提交任务失败"))

    return result.get("data", {}).get("task_id", "")


def get_task_result(task_id: str) -> dict:
    """获取任务结果"""
    req_body = {
        "req_key": VOLCENGINE_TEXT2VIDEO_REQ_KEY,
        "task_id": task_id
    }
    result = call_visual_api("CVSync2AsyncGetResult", req_body)
    if result.get("error"):
        raise RuntimeError(result["error"])
    return result


def poll_until_done(task_id: str, poll_interval: int = 3, max_polls: int = 120) -> str:
    """轮询任务"""
    poll_count = 0
    
    while poll_count < max_polls:
        task_result = get_task_result(task_id)
        result_code = task_result.get("code")
        task_data = task_result.get("data") or {}
        task_status = task_data.get("status", "")
        
        if result_code == 10000 and task_status == "done":
            output_video_url = task_data.get("video_url", "")
            print(f"✅ 视频生成成功: {output_video_url}")
            return output_video_url
        elif task_status in {"not_found", "expired"}:
            raise RuntimeError(f"任务状态异常: {task_status}")
        elif result_code != 10000 and task_status == "done":
            raise RuntimeError(task_result.get("message", "视频生成失败"))
        
        poll_count += 1
        if poll_count < max_polls:
            time.sleep(poll_interval)
            if task_id in task_store:
                progress = min(95, int((poll_count / max_polls) * 100))
                task_store[task_id]["progress"] = progress
                task_store[task_id]["status"] = task_status or "processing"
    
    print("❌ 任务超时")
    return ""


def download_video(video_url: str, task_id: str) -> str:
    """下载视频"""
    try:
        response = requests.get(video_url, timeout=30)
        if response.status_code == 200:
            file_path = os.path.join(VIDEO_FOLDER, f"{task_id}.mp4")
            with open(file_path, 'wb') as f:
                f.write(response.content)
            print(f"✅ 视频已下载: {file_path}")
            return file_path
    except Exception as e:
        print(f"❌ 下载视频失败: {e}")
    
    return ""


def poll_task_bg(task_id: str, prompt: str = "", username: str = ""):
    """后台处理任务"""
    try:
        video_url = poll_until_done(task_id, poll_interval=3)
        if not video_url:
            raise RuntimeError("视频生成未返回可下载地址")

        file_path = download_video(video_url, task_id)
        if not file_path or not os.path.exists(file_path):
            raise RuntimeError("视频下载失败，未生成本地文件")
        
        file_size = os.path.getsize(file_path)
        
        filename = os.path.basename(file_path)
        upsert_video_history(task_id, username, prompt, filename, file_size, "completed")
        
        if task_id in task_store:
            task_store[task_id]["status"] = "completed"
            task_store[task_id]["video_url"] = video_url
            task_store[task_id]["local_path"] = file_path
            task_store[task_id]["prompt"] = prompt
            task_store[task_id]["owner"] = username
        
        print(f"🎉 完整流程完成: {task_id}")
    except Exception as e:
        print(f"❌ 后台处理失败: {e}")
        upsert_video_history(task_id, username, prompt, "", 0, "failed")
        if task_id in task_store:
            task_store[task_id]["status"] = "failed"
            task_store[task_id]["error"] = str(e)


# API 端点
@app.post("/api/login")
async def login(req: LoginRequest):
    """登录"""
    if not verify_user(req.username, req.password):
        return {"status": "error", "message": "用户名或密码错误"}
    
    token = generate_token(req.username)
    return {"status": "success", "token": token, "username": req.username}


@app.get("/api/user/info")
async def user_info(token: str = None):
    """用户信息"""
    if not token or token not in session_store:
        return {"status": "error", "message": "需要登录"}
    
    username = session_store[token]
    return {"status": "success", "username": username}


@app.post("/api/logout")
async def logout(token: str = None):
    """登出"""
    if token and token in session_store:
        del session_store[token]
    
    return {"status": "success"}


@app.post("/api/generate")
async def generate_video(req: GenerateRequest):
    """生成视频"""
    if not req.token or req.token not in session_store:
        return {"status": "error", "message": "需要登录"}
    
    username = session_store[req.token]
    
    try:
        task_id = submit_text_to_video_task(
            prompt=req.prompt,
            negative_prompt=req.negative_prompt,
            model_type=req.model_type,
            ratio=req.ratio,
            duration=req.duration
        )
    except Exception as e:
        return {"status": "error", "message": f"提交任务失败: {e}"}
    
    if not task_id:
        return {"status": "error", "message": "提交任务失败"}
    
    task_store[task_id] = {
        "status": "processing",
        "prompt": req.prompt,
        "created_at": datetime.datetime.now().isoformat(),
        "owner": username,
        "progress": 0
    }

    upsert_video_history(
        task_id=task_id,
        username=username,
        prompt=req.prompt,
        status="processing",
        created_at=task_store[task_id]["created_at"]
    )
    
    thread = threading.Thread(target=poll_task_bg, args=(task_id, req.prompt, username), daemon=True)
    thread.start()
    
    return {"status": "success", "task_id": task_id, "message": "任务已提交"}


@app.get("/api/task/{task_id}/progress")
async def get_task_progress(task_id: str):
    """任务进度"""
    if task_id not in task_store:
        return {"status": "error", "message": "任务不存在"}
    
    task = task_store[task_id]
    task_status = task.get("status")
    
    progress_map = {
        "processing": 50,
        "in_queue": 10,
        "generating": 50,
        "done": 95,
        "completed": 100,
        "failed": 0
    }
    
    progress = task.get("progress", progress_map.get(task_status, 0))
    
    return {
        "status": "success",
        "task_id": task_id,
        "task_status": task_status,
        "progress": progress,
        "data": task
    }


@app.get("/api/videos")
async def get_videos(token: str = None):
    """获取视频列表"""
    try:
        if not token or token not in session_store:
            return {"status": "error", "message": "需要登录", "videos": []}
        
        username = session_store[token]
        videos = get_user_videos_from_csv(username)
        
        return {"status": "success", "videos": videos, "count": len(videos)}
    except Exception as e:
        print(f"❌ 获取视频列表失败: {e}")
        return {"status": "error", "message": str(e), "videos": []}


@app.get("/api/gallery")
async def get_gallery():
    """获取首页画廊数据"""
    return {
        "status": "success",
        "data": [
            {"id": 1, "type": "video", "url": "https://picsum.photos/400/300?random=1"},
            {"id": 2, "type": "video", "url": "https://picsum.photos/400/600?random=2"},
            {"id": 3, "type": "video", "url": "https://picsum.photos/400/400?random=3"},
            {"id": 4, "type": "video", "url": "https://picsum.photos/400/500?random=4"},
            {"id": 5, "type": "video", "url": "https://picsum.photos/400/700?random=5"},
            {"id": 6, "type": "image", "url": "https://picsum.photos/400/350?random=6"},
        ]
    }


@app.get("/api/stats")
async def get_stats():
    """统计"""
    video_count = len([f for f in os.listdir(VIDEO_FOLDER) if f.endswith('.mp4')]) if os.path.exists(VIDEO_FOLDER) else 0
    user_count = len(load_users())
    
    return {"video_count": video_count, "user_count": user_count, "task_count": len(task_store)}


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    print("🚀 启动 FastAPI 服务器...")
    print("📍 API 地址: http://127.0.0.1:8000")
    print("📍 文档地址: http://127.0.0.1:8000/docs")
    
    uvicorn.run(app, host="127.0.0.1", port=8000)
