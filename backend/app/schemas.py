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


class PaperNeighbors(BaseModel):
    previous: Optional[PaperListItem] = None
    next: Optional[PaperListItem] = None


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
    job_id: Optional[int] = None
    queued: int
    new_papers: int


HeavyProcessingTrigger = Literal["on_fetch", "on_to_read"]


class FetchSettingsIn(BaseModel):
    fetch_lookback_days: Optional[int] = Field(default=None, ge=1, le=365)
    auto_fetch_enabled: Optional[bool] = None
    fetch_time: Optional[str] = Field(
        default=None,
        pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
    )
    heavy_processing_trigger: Optional[HeavyProcessingTrigger] = None


class ArxivCandidate(BaseModel):
    arxiv_id: str
    title: str
    authors: List[str]
    abstract: str
    categories: List[str]
    pdf_url: str
    abs_url: str
    published_at: str
    already_imported: bool
    paper_id: Optional[int] = None


class ArxivImportIn(BaseModel):
    arxiv_ids: List[str]


class ArxivImportOut(BaseModel):
    imported: List[int]
    skipped: List[str]


class FetchSettingsOut(BaseModel):
    fetch_lookback_days: int
    default_fetch_lookback_days: int
    auto_fetch_enabled: bool
    default_auto_fetch_enabled: bool
    fetch_time: str
    default_fetch_time: str
    server_time: datetime
    server_timezone: str
    server_utc_offset_minutes: int
    heavy_processing_trigger: HeavyProcessingTrigger
    default_heavy_processing_trigger: HeavyProcessingTrigger
