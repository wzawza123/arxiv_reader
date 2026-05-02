from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, ConfigDict, Field


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: Optional[str] = None


class TagIn(BaseModel):
    name: str
    description: Optional[str] = None


class TagPatch(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class FigureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    idx: int
    path: str
    caption: Optional[str] = None


class PaperListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    arxiv_id: str
    title: str
    authors: List[str]
    abstract: str
    abstract_zh: Optional[str] = None
    categories: List[str]
    abs_url: str
    pdf_url: str
    published_at: datetime
    status: str
    tags: List[TagOut] = []


class PaperDetail(PaperListItem):
    summary_md: Optional[str] = None
    insights_md: Optional[str] = None
    followup_md: Optional[str] = None
    figures: List[FigureOut] = []


class PaperPatch(BaseModel):
    status: Optional[Literal["new", "to_read", "not_interested", "read"]] = None
    tag_ids: Optional[List[int]] = None


class SubscriptionIn(BaseModel):
    kind: Literal["category", "keyword"]
    value: str
    enabled: bool = True


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    value: str
    enabled: bool
    created_at: datetime
    last_fetched_at: Optional[datetime] = None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    paper_id: Optional[int] = None
    kind: str
    status: str
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime


class FetchTriggerOut(BaseModel):
    queued: int
    new_papers: int


HeavyProcessingTrigger = Literal["on_fetch", "on_to_read"]


class FetchSettingsIn(BaseModel):
    fetch_lookback_days: Optional[int] = Field(default=None, ge=1, le=365)
    heavy_processing_trigger: Optional[HeavyProcessingTrigger] = None


class FetchSettingsOut(BaseModel):
    fetch_lookback_days: int
    default_fetch_lookback_days: int
    heavy_processing_trigger: HeavyProcessingTrigger
    default_heavy_processing_trigger: HeavyProcessingTrigger
