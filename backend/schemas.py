from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


class LoginResponse(BaseModel):
    status: str
    token: str
    username: str


class VideoTaskCreateRequest(BaseModel):
    prompt: str = Field(min_length=1)
    model_type: str = "Seedance3.0"
    ratio: str = "16:9"
    duration: int = 5
    negative_prompt: str = ""
    token: str = ""


class VideoTaskUpdateRequest(BaseModel):
    status: str
    progress: int | None = Field(default=None, ge=0, le=100)
    error_message: str | None = None


class VideoTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    provider: str
    task_id: str | None
    prompt: str
    optimized_prompt: str | None
    status: str
    progress: int
    video_filename: str | None
    video_path: str | None
    video_url: str | None
    local_video_url: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None


class FeedbackCreateRequest(BaseModel):
    token: str
    video_task_id: int
    liked: bool | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    feedback_text: str | None = None


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    video_task_id: int
    liked: bool | None
    rating: int | None
    feedback_text: str | None
    created_at: datetime


class PreferenceProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    preferred_styles: str | None
    disliked_styles: str | None
    preferred_prompt_keywords: str | None
    preferred_video_types: str | None
    summary: str | None
    updated_at: datetime

