import json
import os
from pathlib import Path

import requests
from volcenginesdkcore.signv4 import SignerV4

from volcengine_credentials import VOLCENGINE_ACCESS_KEY, VOLCENGINE_SECRET_KEY


BASE_DIR = Path(__file__).resolve().parent.parent
VIDEO_DIR = BASE_DIR / "video"
VIDEO_DIR.mkdir(exist_ok=True)

ACCESS_KEY = VOLCENGINE_ACCESS_KEY
SECRET_KEY = VOLCENGINE_SECRET_KEY
VOLCENGINE_API_HOST = os.getenv("VOLCENGINE_API_HOST", "visual.volcengineapi.com")
VOLCENGINE_REGION = os.getenv("VOLCENGINE_REGION", "cn-north-1")
VOLCENGINE_SERVICE = os.getenv("VOLCENGINE_SERVICE", "cv")
VOLCENGINE_VERSION = os.getenv("VOLCENGINE_VERSION", "2022-08-31")
VOLCENGINE_TEXT2VIDEO_REQ_KEY = os.getenv("VOLCENGINE_TEXT2VIDEO_REQ_KEY", "jimeng_t2v_v30")


def call_visual_api(action: str, req_body: dict) -> dict:
    query = {"Action": action, "Version": VOLCENGINE_VERSION}
    url = f"https://{VOLCENGINE_API_HOST}/?Action={action}&Version={VOLCENGINE_VERSION}"
    body_json = json.dumps(req_body, ensure_ascii=False)
    headers = {"Content-Type": "application/json", "Host": VOLCENGINE_API_HOST}

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
        service=VOLCENGINE_SERVICE,
    )

    response = requests.post(url, data=body_json.encode("utf-8"), headers=headers, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:500]}")

    result = response.json()
    if result.get("ResponseMetadata", {}).get("Error"):
        raise RuntimeError(result["ResponseMetadata"]["Error"].get("Message", "未知错误"))

    if result.get("code") != 10000:
        raise RuntimeError(result.get("message", "请求失败"))

    return result


def submit_text_to_video_task(prompt: str, ratio: str = "16:9", duration: int = 5) -> str:
    frames_map = {5: 121, 10: 241}
    payload = {
        "req_key": VOLCENGINE_TEXT2VIDEO_REQ_KEY,
        "prompt": prompt,
        "seed": -1,
        "frames": frames_map.get(duration, 121),
        "aspect_ratio": ratio,
    }
    result = call_visual_api("CVSync2AsyncSubmitTask", payload)
    task_id = result.get("data", {}).get("task_id")
    if not task_id:
        raise RuntimeError("未返回任务 ID")
    return task_id


def get_task_result(task_id: str) -> dict:
    payload = {"req_key": VOLCENGINE_TEXT2VIDEO_REQ_KEY, "task_id": task_id}
    return call_visual_api("CVSync2AsyncGetResult", payload)


def download_video(video_url: str, task_id: str) -> Path:
    response = requests.get(video_url, timeout=60)
    if response.status_code != 200:
        raise RuntimeError(f"视频下载失败: HTTP {response.status_code}")

    file_path = VIDEO_DIR / f"{task_id}.mp4"
    file_path.write_bytes(response.content)
    return file_path

