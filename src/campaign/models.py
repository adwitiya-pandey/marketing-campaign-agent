"""Pydantic domain models and contracts."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SegmentType = Literal[
    "fitness-enthusiasts",
    "young-professionals",
    "eco-conscious-families",
    "students",
]

ChannelType = Literal["google_ads", "instagram", "email"]

RunStatus = Literal[
    "AWAITING_APPROVAL",
    "COMPLETED",
    "REJECTED",
    "FAILED",
    "BUDGET_EXCEEDED",
    "LIMIT_REACHED",
]

# Strict ASCII ID patterns ensuring no trailing newlines or unicode digits
RUN_ID_REGEX = re.compile(r"^RUN-[0-9]{8}-[0-9]{4}\Z")
USER_ID_REGEX = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{1,31}\Z")
HASHTAG_REGEX = re.compile(r"^#[A-Za-z0-9]{2,30}\Z")


class StrictBaseModel(BaseModel):
    """Base model that forbids extra fields."""

    model_config = ConfigDict(extra="forbid")


class ProductBrief(StrictBaseModel):
    """Product brief input schema."""

    name: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=10, max_length=2000)
    segment: SegmentType
    budget_usd: float = Field(default=5000.0, ge=100.0, le=100000.0)


class CampaignAngle(StrictBaseModel):
    """Single proposed campaign angle with supporting research evidence."""

    title: str = Field(min_length=5, max_length=80)
    positioning: str = Field(min_length=20, max_length=300)
    target_insight: str = Field(min_length=20, max_length=300)
    key_message: str = Field(min_length=10, max_length=140)
    evidence: list[str] = Field(min_length=1, max_length=4)
    estimated_reach: int = Field(ge=0)
    competitor_contrast: str = Field(min_length=10, max_length=200)

    @field_validator("evidence")
    @classmethod
    def validate_evidence_items(cls, items: list[str]) -> list[str]:
        for item in items:
            if len(item) > 200:
                raise ValueError("Evidence item must be at most 200 characters")
            if not item.strip():
                raise ValueError("Evidence item cannot be empty")
        return items


class CampaignAngles(StrictBaseModel):
    """Exactly 5 distinct campaign angles."""

    angles: list[CampaignAngle] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def validate_distinct_titles(self) -> CampaignAngles:
        titles_lower = [a.title.strip().lower() for a in self.angles]
        if len(set(titles_lower)) != len(self.angles):
            raise ValueError("All 5 angle titles must be distinct (case-insensitive)")
        return self


class GoogleAdsCopy(StrictBaseModel):
    """Google Ads copy constraints."""

    headlines: list[str] = Field(min_length=3, max_length=3)
    descriptions: list[str] = Field(min_length=2, max_length=2)

    @field_validator("headlines")
    @classmethod
    def validate_headlines(cls, items: list[str]) -> list[str]:
        for h in items:
            if len(h) > 30:
                raise ValueError(f"Headline exceeds 30 characters: '{h}'")
            if not h.strip():
                raise ValueError("Headline cannot be empty")
        return items

    @field_validator("descriptions")
    @classmethod
    def validate_descriptions(cls, items: list[str]) -> list[str]:
        for d in items:
            if len(d) > 90:
                raise ValueError(f"Description exceeds 90 characters: '{d}'")
            if not d.strip():
                raise ValueError("Description cannot be empty")
        return items


class InstagramCopy(StrictBaseModel):
    """Instagram copy constraints."""

    caption: str = Field(min_length=1, max_length=600)
    hashtags: list[str] = Field(min_length=3, max_length=8)
    image_idea: str = Field(min_length=1, max_length=200)

    @field_validator("hashtags")
    @classmethod
    def validate_hashtags(cls, tags: list[str]) -> list[str]:
        for tag in tags:
            if "\n" in tag or "\r" in tag or not HASHTAG_REGEX.fullmatch(tag):
                raise ValueError(f"Invalid hashtag '{tag}': must match ^#[A-Za-z0-9]{{2,30}}$")
        return tags


class EmailCopy(StrictBaseModel):
    """Email copy constraints."""

    subject: str = Field(min_length=1, max_length=60)
    preheader: str = Field(min_length=1, max_length=100)
    body: str = Field(min_length=1, max_length=1200)
    cta: str = Field(min_length=1, max_length=40)


class CampaignPackage(StrictBaseModel):
    """Complete advertising copy package for an approved angle."""

    angle_title: str = Field(min_length=5, max_length=80)
    google_ads: GoogleAdsCopy
    instagram: InstagramCopy
    email: EmailCopy


class WebSearchArgs(StrictBaseModel):
    """Arguments for the web_search tool."""

    query: str = Field(min_length=3, max_length=200)


class SqlQueryArgs(StrictBaseModel):
    """Arguments for the sql_query tool."""

    query: str = Field(min_length=10, max_length=500)


class AnalyticsLookupArgs(StrictBaseModel):
    """Arguments for the analytics_lookup tool."""

    segment: SegmentType
    channel: ChannelType
    budget_usd: float = Field(ge=50.0, le=100000.0)


class DraftCopyArgs(StrictBaseModel):
    """Arguments for the draft_copy tool."""

    channel: ChannelType
    fields: dict[str, str | list[str]]


class RunRecord(StrictBaseModel):
    """Run state record persisted in SQLite."""

    run_id: str
    user_id: str
    status: RunStatus
    product: ProductBrief
    angles: CampaignAngles | None = None
    selected_index: int | None = Field(default=None, ge=0, le=4)
    package: CampaignPackage | None = None
    tool_calls_used: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    created_at: str
    updated_at: str

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, v: str) -> str:
        if "\n" in v or "\r" in v or not RUN_ID_REGEX.fullmatch(v):
            raise ValueError(f"Invalid run_id '{v}': must match ^RUN-[0-9]{{8}}-[0-9]{{4}}$")
        return v

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        if "\n" in v or "\r" in v or not USER_ID_REGEX.fullmatch(v):
            raise ValueError(f"Invalid user_id '{v}': must match ^[A-Za-z][A-Za-z0-9_.-]{{1,31}}$")
        return v
