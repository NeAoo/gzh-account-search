"""Domain models for collected public account articles."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

CONTENT_MAX_LENGTH = 3000


class Article(BaseModel):
    """A collected WeChat public account article."""

    title: str = Field(..., description="Article title")
    source: str = Field(..., description="Source public account name")
    publish_time: datetime = Field(..., description="Publish time")
    url: str = Field(..., description="Original URL")
    content: str = Field("", description="Article body, truncated to 3000 chars")

    author: Optional[str] = Field(None, description="Author or public account name")
    tags: list[str] = Field(default_factory=list, description="User or crawler tags")

    score: Optional[float] = Field(None, description="Overall LLM score")
    score_details: Optional[dict] = Field(None, description="Detailed score payload")

    @field_validator("content", mode="before")
    @classmethod
    def truncate_content(cls, value) -> str:
        if value is None:
            return ""
        return str(value)[:CONTENT_MAX_LENGTH]


class CollectionResult(BaseModel):
    """Crawler result container."""

    success_count: int = Field(0, description="Collected article count")
    failed_count: int = Field(0, description="Failed account or item count")
    items: list[Article] = Field(default_factory=list)
    error_messages: list[str] = Field(default_factory=list)
