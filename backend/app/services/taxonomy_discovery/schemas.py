"""Dual-schema for taxonomy discovery + KB extraction (spec §5)."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class StrategyType(str, Enum):
    """7 大策略大类 (Phase G 扩 +AI 应用类, spec §4.1)。enum value 用中文,LLM 直接吐就行。"""
    基本面权益 = "基本面权益"
    量化 = "量化"
    固定收益 = "固定收益"
    卖方研究 = "卖方研究"
    多资产_FOF_衍生品 = "多资产_FOF_衍生品"
    相关补充 = "相关补充"
    AI_应用_PM_开发 = "AI 应用_PM_开发"


class KBInsightType(str, Enum):
    """5 类 KB insight (复用 Pony schema, spec §5.2)。"""
    role = "role"
    interview = "interview"
    company = "company"
    resume = "resume"
    industry = "industry"


class StrategySignal(BaseModel):
    canonical: StrategyType
    verbatim_phrase: str = Field(description="原文里学生用什么词描述")


class IndustrySignal(BaseModel):
    industry: str = Field(description="行业方向, 如 消费/TMT/医药, 不锁 enum 让 LLM 自由发现")
    verbatim_phrase: str


class InstitutionSignal(BaseModel):
    tier_guess: str = Field(description="平台类型, 如 一线公募/头部主观私募")
    company_name: str
    verbatim: str


class CompanyRolePair(BaseModel):
    company: str
    role_or_dept: str
    strategy: str


class DimensionDistinction(BaseModel):
    axis: str = Field(description="哪个维度, e.g. strategy_type / institution_tier")
    x_vs_y: str = Field(description="X vs Y 形式, e.g. '公募 vs 资管子'")
    note: str


class KBInsight(BaseModel):
    type: KBInsightType
    text: str = Field(description="1 句摘要")
    verbatim_quote: str = Field(description="原文截取")
    confidence: Literal["high", "med", "low"]

    @field_validator("confidence", mode="before")
    @classmethod
    def _normalize_confidence(cls, v):
        # LLM 偶尔吐 medium/Medium/MED 等变体, 归一到 med
        if not isinstance(v, str):
            return v
        s = v.strip().lower()
        if s in {"medium", "mid"}:
            return "med"
        return s


class PostTaxonomyExtract(BaseModel):
    """Taxonomy 发现字段 (spec §5.1)。"""
    strategy_signals: list[StrategySignal] = Field(default_factory=list)
    industry_signals: list[IndustrySignal] = Field(default_factory=list)
    institution_signals: list[InstitutionSignal] = Field(default_factory=list)
    discovered_sub_categories: list[str] = Field(default_factory=list)
    company_role_pairs: list[CompanyRolePair] = Field(default_factory=list)
    dimension_distinctions: list[DimensionDistinction] = Field(default_factory=list)


class PostKBExtract(BaseModel):
    """KB 字段 (spec §5.2, 沿用 Pony 5-type)。"""
    insights: list[KBInsight] = Field(default_factory=list)


class DualSchemaExtract(BaseModel):
    """每帖 LLM 一次调用产出, 双 schema 合一。"""
    post_id: str
    url: str
    time: str
    author: str
    relevance_score: float = Field(ge=0.0, le=1.0, description="该帖是否真讨论投研, <0.3 drop")
    taxonomy: PostTaxonomyExtract
    kb: PostKBExtract
    extraction_confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="LLM 自评抽取置信度, <0.7 触发 Sonnet 二审")

    @field_validator("time", "author", "post_id", "url", mode="before")
    @classmethod
    def _coerce_to_str(cls, v):
        # XHS / TikHub 偶尔返 int (timestamp / user_id), 强转 str
        if v is None:
            return ""
        return str(v)
