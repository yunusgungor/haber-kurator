"""
Haber Kuratör — Data Models & Constants
==========================================
Pure data classes, enums, exceptions, and configuration constants.
No business logic — safe to import from anywhere without circular imports.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

VERSION = os.getenv("HABER_VERSION", "3.1.0")


# ══════════════════════════════════════════════════════════════
# EXCEPTION HIERARCHY
# ════════════════════════════════════��═════════════════════════

class HaberKuratorError(Exception):
    """Base for all Haber-Kuratör exceptions."""
    def __init__(self, message: str, *, slug: str | None = None,
                 details: dict | None = None):
        super().__init__(message)
        self.slug = slug
        self.details = details or {}


class SourceError(HaberKuratorError):
    """Source loading, RSS fetch, or parsing errors."""


class StateError(HaberKuratorError):
    """State machine transition or validation errors."""


class ConfigError(HaberKuratorError):
    """Configuration or env-loading errors."""


class LLMError(HaberKuratorError):
    """LLM call or response-parsing errors."""


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════

def _env_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _env_float_list(key: str, default: list) -> list:
    val = os.getenv(key)
    if not val:
        return default
    try:
        return [float(x.strip()) for x in val.split(",") if x.strip()]
    except ValueError:
        return default


CONFIG = {
    "version": VERSION,
    "min_verification_level": int(os.getenv("HABER_MIN_VERIFICATION_LEVEL", "1")),
    "rss_timeout": int(os.getenv("HABER_RSS_TIMEOUT", "5")),
    "rss_delay": float(os.getenv("HABER_RSS_DELAY", "0.3")),
    "rss_max_workers": int(os.getenv("HABER_RSS_MAX_WORKERS", "8")),
    "rss_retry_delays": _env_float_list("HABER_RSS_RETRY_DELAYS", [1.0, 2.0, 4.0]),
    "news_max_age_hours": int(os.getenv("HABER_NEWS_MAX_AGE_HOURS", "48")),
    "cache_enabled": _env_bool("HABER_CACHE_ENABLED", True),
}


# ══════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════

class SourceTier(Enum):
    """Credibility tiers for news sources.

    Tier 0 (PRIMARY):   Wire services — Reuters, AP, AFP. Gold standard.
    Tier 1 (MAJOR):     Major newspapers & broadcasters with editorial standards.
    Tier 2 (SPECIALIZED): Topic-specific but reputable (tech, science, finance).
    Tier 3 (SUPPLEMENTARY): Local/regional reputable outlets.
    """
    PRIMARY = 0
    MAJOR = 1
    SPECIALIZED = 2
    SUPPLEMENTARY = 3

    @property
    def confidence_label(self) -> str:
        return {
            0: "PRIMARY — Wire Service",
            1: "MAJOR — Major Outlet",
            2: "SPECIALIZED — Topic Expert",
            3: "SUPPLEMENTARY — Regional",
        }[self.value]

    @property
    def weight(self) -> int:
        return {0: 3, 1: 2, 2: 1, 3: 1}[self.value]


class VerificationLevel(Enum):
    CONFIRMED = 3
    HIGH_CONFIDENCE = 2
    MEDIUM_CONFIDENCE = 1
    LOW_CONFIDENCE = 0
    UNVERIFIED = -1

    @property
    def label(self) -> str:
        return {
            3: "✅ CONFIRMED — Multiple primary sources",
            2: "🟡 HIGH CONFIDENCE — Primary + major sources",
            1: "🟠 MEDIUM CONFIDENCE — Multiple major sources",
            0: "🔴 LOW CONFIDENCE — Single source / specialized only",
            -1: "⛔ UNVERIFIED — Cannot be verified",
        }[self.value]

    @property
    def can_publish(self) -> bool:
        return self.value >= CONFIG["min_verification_level"]


# ══════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════

@dataclass
class NewsSource:
    name: str
    base_url: str
    category: str
    tier: SourceTier = SourceTier.MAJOR
    rss_feeds: List[str] = field(default_factory=list)
    trending_feeds: List[str] = field(default_factory=list)
    language: str = "en"
    country: str = "global"
    notes: str = ""

    @property
    def tier_name(self) -> str:
        return self.tier.confidence_label

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "base_url": self.base_url,
            "category": self.category,
            "tier": self.tier.value,
            "tier_name": self.tier_name,
            "language": self.language,
            "country": self.country,
        }


@dataclass
class FactClaim:
    claim_text: str
    source_name: str
    source_url: str
    source_tier: SourceTier
    verified_by: List[str] = field(default_factory=list)
    discrepancies: List[str] = field(default_factory=list)
    is_verified: bool = False
    verification_level: str = "unverified"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim": self.claim_text[:200],
            "source": self.source_name,
            "source_url": self.source_url,
            "source_tier": self.source_tier.value,
            "verified_by": self.verified_by,
            "discrepancies": self.discrepancies,
            "is_verified": self.is_verified,
            "verification_level": self.verification_level,
        }


@dataclass
class CrossVerificationResult:
    story_title: str
    slug: str
    claims: List[FactClaim] = field(default_factory=list)
    sources_checked: List[str] = field(default_factory=list)
    sources_agreed: List[str] = field(default_factory=list)
    sources_disagreed: List[str] = field(default_factory=list)
    verification_level: VerificationLevel = VerificationLevel.UNVERIFIED
    verified_claims: int = 0
    total_claims: int = 0
    discrepancies_found: List[str] = field(default_factory=list)
    report: str = ""

    @property
    def is_safe_to_publish(self) -> bool:
        return self.verification_level.value >= CONFIG["min_verification_level"]

    @property
    def summary(self) -> str:
        return (
            f"Verification: {self.verification_level.label} "
            f"({self.verified_claims}/{self.total_claims} claims verified, "
            f"{len(self.sources_agreed)} sources agree)"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "story_title": self.story_title,
            "slug": self.slug,
            "verification_level": self.verification_level.value,
            "verification_label": self.verification_level.label,
            "verified_claims": self.verified_claims,
            "total_claims": self.total_claims,
            "sources_checked": self.sources_checked,
            "sources_agreed": self.sources_agreed,
            "sources_disagreed": self.sources_disagreed,
            "discrepancies": self.discrepancies_found,
            "is_safe_to_publish": self.is_safe_to_publish,
        }


# ══════════════════════════════════════════════════════════════
# NEWS SOURCES (embedded fallback + loader)
# ══════════════════════════════════════════════════════════════

NEWS_SOURCES: Dict[str, NewsSource] = {}


def _load_news_sources(json_path: Optional[Path] = None) -> Dict[str, NewsSource]:
    if json_path is None:
        env_path = os.getenv("HABER_SOURCES_JSON")
        if env_path:
            json_path = Path(env_path)
        else:
            candidates = [
                Path("sources/news_sources.json"),
                Path(".hermes/plugins/haber-kurator/sources/news_sources.json"),
            ]
            json_path = next((p for p in candidates if p.exists()), None)

    if json_path and json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load sources from {json_path}: {e}")
            return {}

        tier_map = {
            "PRIMARY": SourceTier.PRIMARY,
            "MAJOR": SourceTier.MAJOR,
            "SPECIALIZED": SourceTier.SPECIALIZED,
        }

        sources = {}
        for entry in raw:
            key = entry.get("key", "")
            if not key:
                continue
            sources[key] = NewsSource(
                name=entry.get("name", key),
                base_url=entry.get("base_url", ""),
                category=entry.get("category", "news"),
                tier=tier_map.get(entry.get("tier", "SPECIALIZED"), SourceTier.SPECIALIZED),
                rss_feeds=entry.get("rss_feeds", []),
                language=entry.get("language", "en"),
                country=entry.get("country", "global"),
                notes=entry.get("notes", ""),
            )
        logger.info(f"Loaded {len(sources)} news sources from {json_path}")
        return sources

    return {}


# ══════════════════════════════════════════════════════════════
# RUN‑TIME DATA CLASSES
# ══════════════════════════════════════════════════════════════


@dataclass
class RunState:
    slug: str
    title: str = ""
    state: str = "captured"
    route: str = "VERIFIED"
    created: str = ""
    updated: str = ""
    source_type: str = "multi-source"
    verification_level: str = "unverified"


@dataclass
class SlopResult:
    score: str = "PASS"
    tier1_count: int = 0
    tier2_count: int = 0
    tier3_count: int = 0
    bonus_count: int = 0
    findings: List[str] = field(default_factory=list)
    findings_tier1: List[str] = field(default_factory=list)
    findings_tier2: List[str] = field(default_factory=list)
    findings_tier3: List[str] = field(default_factory=list)
    findings_bonus: List[str] = field(default_factory=list)
    all_findings: List[str] = field(default_factory=list)


@dataclass
class FetchedNewsItem:
    """A raw news item fetched from a source."""
    title: str
    url: str
    source_name: str
    source_tier: SourceTier
    published: str = ""
    summary: str = ""
    category: str = "general"
    guid: str = ""


# ══════════════════════════════════════════════════════════════
# STATE MACHINE CONSTANTS
# ══════════════════════════════════════════════════════════════

STATE_LIFECYCLE = [
    "captured",
    "verified",
    "published",
    "corrected",
    "archived",
]

STATE_TRANSITIONS = {
    "captured":           ["verified"],
    "verified":           ["captured", "verified", "published", "corrected"],
    "published":          ["corrected", "archived"],
    "corrected":          ["published", "archived"],
    "archived":           [],
}

STATE_ALIAS_MAP = {
    "fact_checking":      "verified",
    "cross_verified":     "verified",
    "cross_verified":     "verified",
    "correction_needed":  "corrected",
    "corrected":          "corrected",
    "retracted":          "corrected",
}

ROUTE_VERIFIED = "VERIFIED"
ROUTE_HIGH_SLOP = "HIGH_SLOP"
ROUTE_ESCALATED = "ESCALATED"

WRITER_FIELDS = [
    "rubric_self_assessment",
    "avoid_slop_pass",
    "source_attribution_check",
]



