from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Enum as SAEnum,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from .db import Base


class PaperStatus(str, PyEnum):
    NEW = "new"
    TO_READ = "to_read"
    NOT_INTERESTED = "not_interested"
    READ = "read"


class JobKind(str, PyEnum):
    TRANSLATE = "translate"
    TAG = "tag"
    SUMMARY = "summary"
    FIGURES = "figures"
    FETCH = "fetch"


class JobStatus(str, PyEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class SubscriptionKind(str, PyEnum):
    CATEGORY = "category"
    KEYWORD = "keyword"


class Paper(Base):
    __tablename__ = "papers"

    id = Column(Integer, primary_key=True)
    arxiv_id = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(Text, nullable=False)
    authors = Column(JSON, nullable=False, default=list)
    abstract = Column(Text, nullable=False)
    abstract_zh = Column(Text, nullable=True)
    categories = Column(JSON, nullable=False, default=list)
    pdf_url = Column(String(512), nullable=False)
    abs_url = Column(String(512), nullable=False)
    published_at = Column(DateTime, nullable=False)
    fetched_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    status = Column(
        SAEnum(PaperStatus, native_enum=False),
        nullable=False,
        default=PaperStatus.NEW,
        index=True,
    )
    summary_md = Column(Text, nullable=True)
    insights_md = Column(Text, nullable=True)
    followup_md = Column(Text, nullable=True)

    tags = relationship(
        "Tag",
        secondary="paper_tags",
        back_populates="papers",
        lazy="selectin",
    )
    figures = relationship(
        "Figure",
        back_populates="paper",
        cascade="all, delete-orphan",
        order_by="Figure.idx",
        lazy="selectin",
    )


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    papers = relationship(
        "Paper",
        secondary="paper_tags",
        back_populates="tags",
    )


class PaperTag(Base):
    __tablename__ = "paper_tags"

    paper_id = Column(Integer, ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    kind = Column(SAEnum(SubscriptionKind, native_enum=False), nullable=False)
    value = Column(String(256), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_fetched_at = Column(DateTime, nullable=True)

    __table_args__ = (UniqueConstraint("kind", "value", name="uq_subscription_kind_value"),)


class Figure(Base):
    __tablename__ = "figures"

    id = Column(Integer, primary_key=True)
    paper_id = Column(Integer, ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True)
    idx = Column(Integer, nullable=False)
    path = Column(String(512), nullable=False)  # relative to data/figures
    caption = Column(Text, nullable=True)

    paper = relationship("Paper", back_populates="figures")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    paper_id = Column(Integer, ForeignKey("papers.id", ondelete="CASCADE"), nullable=True, index=True)
    kind = Column(SAEnum(JobKind, native_enum=False), nullable=False)
    status = Column(
        SAEnum(JobStatus, native_enum=False),
        nullable=False,
        default=JobStatus.PENDING,
        index=True,
    )
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


Index("ix_jobs_status_kind", Job.status, Job.kind)
