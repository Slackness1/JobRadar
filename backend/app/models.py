from datetime import datetime
from sqlalchemy import Column, Integer, Text, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    job_id = Column(Text, unique=True, nullable=False, index=True)
    source = Column(Text, default="tatawangshen")
    company = Column(Text, default="")
    company_type_industry = Column(Text, default="")
    company_tags = Column(Text, default="")
    department = Column(Text, default="")
    job_title = Column(Text, default="")
    location = Column(Text, default="")
    major_req = Column(Text, default="")
    job_req = Column(Text, default="")
    job_duty = Column(Text, default="")
    application_status = Column(Text, default="待申请")
    job_stage = Column(Text, default="campus")
    source_config_id = Column(Text, default="")
    publish_date = Column(DateTime, nullable=True)
    deadline = Column(DateTime, nullable=True)
    detail_url = Column(Text, default="")
    scraped_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    scores = relationship("JobScore", back_populates="job", cascade="all, delete-orphan")


class Track(Base):
    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True)
    key = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=False)
    weight = Column(Float, default=1.0)
    min_score = Column(Integer, default=10)
    sort_order = Column(Integer, default=0)

    groups = relationship("KeywordGroup", back_populates="track", cascade="all, delete-orphan",
                          order_by="KeywordGroup.sort_order")
    scores = relationship("JobScore", back_populates="track", cascade="all, delete-orphan")


class KeywordGroup(Base):
    __tablename__ = "keyword_groups"

    id = Column(Integer, primary_key=True)
    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False)
    group_name = Column(Text, nullable=False)
    sort_order = Column(Integer, default=0)

    track = relationship("Track", back_populates="groups")
    keywords = relationship("Keyword", back_populates="group", cascade="all, delete-orphan")


class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("keyword_groups.id", ondelete="CASCADE"), nullable=False)
    word = Column(Text, nullable=False)

    group = relationship("KeywordGroup", back_populates="keywords")


class ScoringConfig(Base):
    __tablename__ = "scoring_config"

    id = Column(Integer, primary_key=True)
    config_json = Column(Text, nullable=False, default="{}")
    updated_at = Column(DateTime, default=datetime.utcnow)


class ExcludeRule(Base):
    __tablename__ = "exclude_rules"

    id = Column(Integer, primary_key=True)
    category = Column(Text, nullable=False)
    keyword = Column(Text, nullable=False)


class JobScore(Base):
    __tablename__ = "job_scores"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False)
    score = Column(Integer, default=0)
    matched_keywords = Column(Text, default="[]")
    scored_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="scores")
    track = relationship("Track", back_populates="scores")

    __table_args__ = (
        UniqueConstraint("job_id", "track_id", name="uq_job_track"),
    )


class CrawlLog(Base):
    __tablename__ = "crawl_logs"

    id = Column(Integer, primary_key=True)
    source = Column(Text, default="tatawangshen")
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    status = Column(Text, default="running")
    new_count = Column(Integer, default=0)
    total_count = Column(Integer, default=0)
    error_message = Column(Text, default="")


class SystemConfig(Base):
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True)
    key = Column(Text, unique=True, nullable=False)
    value = Column(Text, nullable=False, default="")
    updated_at = Column(DateTime, default=datetime.utcnow)


class CompanyRecrawlQueue(Base):
    __tablename__ = "company_recrawl_queue"

    id = Column(Integer, primary_key=True)
    company = Column(Text, nullable=False, index=True)
    department = Column(Text, default="")
    career_url = Column(Text, nullable=False)
    source_domain = Column(Text, default="")
    status = Column(Text, default="pending", index=True)
    attempt_count = Column(Integer, default=0)
    fetched_count = Column(Integer, default=0)
    new_count = Column(Integer, default=0)
    last_error = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
