"""Request/response DTOs for chat."""

from pydantic import BaseModel


class Message(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[Message] = []
    planning: str | None = None  # off | auto | approve (overrides agent default)
    approved_plan: str | None = None  # set on the post-approval execute request
