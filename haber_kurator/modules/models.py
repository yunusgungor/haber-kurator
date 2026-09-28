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
            return dict(NEWS_SOURCES_EMBEDDED)

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

    return dict(NEWS_SOURCES_EMBEDDED)


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


# ══════════════════════════════════════════════════════════════
# EMBEDDED NEWS SOURCES (fallback)
# ══════════════════════════════════════════════════════════════

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


NEWS_SOURCES_EMBEDDED: Dict[str, NewsSource] = {
    # ── TIER 0: PRIMARY WIRE SERVICES ──
    "reuters": NewsSource(
        name="Reuters",
        base_url="https://www.reuters.com",
        category="news",
        tier=SourceTier.PRIMARY,
        rss_feeds=[
            "https://www.reuters.com/arc/outboundfeeds/newsletter-rss/world/",
            "https://www.reuters.com/arc/outboundfeeds/newsletter-rss/business/",
            "https://www.reuters.com/arc/outboundfeeds/newsletter-rss/technology/",
        ],
        notes="World's largest wire service. Strict editorial standards.",
    ),
    "ap": NewsSource(
        name="Associated Press (AP)",
        base_url="https://apnews.com",
        category="news",
        tier=SourceTier.PRIMARY,
        rss_feeds=["https://rsshub.app/apnews"],
        language="en",
        notes="Independent wire service, founded 1846. Gold standard for factual reporting.",
    ),
    "afp": NewsSource(
        name="Agence France-Presse (AFP)",
        base_url="https://www.afp.com",
        category="news",
        tier=SourceTier.PRIMARY,
        rss_feeds=["https://www.afp.com/en/rss"],
        notes="Third major global wire service. Founded 1835.",
    ),
    "bbc": NewsSource(
        name="BBC News",
        base_url="https://www.bbc.com/news",
        category="news",
        tier=SourceTier.PRIMARY,
        rss_feeds=[
            "https://feeds.bbci.co.uk/news/rss.xml",
            "https://feeds.bbci.co.uk/news/technology/rss.xml",
            "https://feeds.bbci.co.uk/news/world/rss.xml",
            "https://feeds.bbci.co.uk/news/business/rss.xml",
            "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
        ],
        language="en",
        notes="UK public service broadcaster. Royal Charter ensures editorial independence.",
    ),
    # ── TIER 1: MAJOR OUTLETS ──
    "bloomberg": NewsSource(
        name="Bloomberg",
        base_url="https://www.bloomberg.com",
        category="business",
        tier=SourceTier.MAJOR,
        rss_feeds=[
            "https://feeds.bloomberg.com/markets/news.rss",
            "https://feeds.bloomberg.com/technology/news.rss",
        ],
        notes="Global financial data and news leader. Strong fact-checking.",
    ),
    "wsj": NewsSource(
        name="The Wall Street Journal",
        base_url="https://www.wsj.com",
        category="business",
        tier=SourceTier.MAJOR,
        rss_feeds=[
            "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
            "https://feeds.a.dj.com/rss/RSSWSJD.xml",
        ],
        notes="Premier US financial newspaper. 40+ Pulitzer Prizes.",
    ),
    "ft": NewsSource(
        name="Financial Times",
        base_url="https://www.ft.com",
        category="business",
        tier=SourceTier.MAJOR,
        rss_feeds=[
            "https://www.ft.com/technology?format=rss",
            "https://www.ft.com/world?format=rss",
        ],
        notes="Leading global business publication. Known for accurate financial reporting.",
    ),
    "guardian": NewsSource(
        name="The Guardian",
        base_url="https://www.theguardian.com",
        category="news",
        tier=SourceTier.MAJOR,
        rss_feeds=[
            "https://www.theguardian.com/world/rss",
            "https://www.theguardian.com/technology/rss",
            "https://www.theguardian.com/business/rss",
            "https://www.theguardian.com/science/rss",
        ],
        notes="UK daily newspaper with strong editorial standards.",
    ),
    "nytimes": NewsSource(
        name="The New York Times",
        base_url="https://www.nytimes.com",
        category="news",
        tier=SourceTier.MAJOR,
        rss_feeds=[
            "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
            "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
            "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
            "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml",
            "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        ],
        notes="Most awarded US newspaper (138+ Pulitzers).",
    ),
    "washington_post": NewsSource(
        name="The Washington Post",
        base_url="https://www.washingtonpost.com",
        category="news",
        tier=SourceTier.MAJOR,
        rss_feeds=[
            "https://feeds.washingtonpost.com/rss/world",
            "https://feeds.washingtonpost.com/rss/national",
            "https://feeds.washingtonpost.com/rss/business",
        ],
        notes="Major US newspaper, 70+ Pulitzers.",
    ),
    "aljazeera": NewsSource(
        name="Al Jazeera English",
        base_url="https://www.aljazeera.com",
        category="news",
        tier=SourceTier.MAJOR,
        rss_feeds=[
            "https://www.aljazeera.com/xml/rss/all.xml",
            "https://www.aljazeera.com/xml/rss/news.xml",
        ],
        notes="Qatar-based global news network. Extensive on-ground reporting.",
    ),
    "npr": NewsSource(
        name="NPR",
        base_url="https://www.npr.org",
        category="news",
        tier=SourceTier.MAJOR,
        rss_feeds=[
            "https://feeds.npr.org/1001/rss.xml",
            "https://feeds.npr.org/1019/rss.xml",
            "https://feeds.npr.org/1007/rss.xml",
        ],
        notes="US public radio network. Known for thorough fact-checking.",
    ),
    "cnn": NewsSource(
        name="CNN",
        base_url="https://www.cnn.com",
        category="news",
        tier=SourceTier.MAJOR,
        rss_feeds=["https://edition.cnn.com/services/rss/"],
        language="en",
        notes="Major US news network. Global reach, 24/7 news coverage.",
    ),
    "nbc_news": NewsSource(
        name="NBC News",
        base_url="https://www.nbcnews.com",
        category="news",
        tier=SourceTier.MAJOR,
        rss_feeds=[
            "https://feeds.nbcnews.com/nbcnews/public/news",
            "https://feeds.nbcnews.com/nbcnews/public/tech",
        ],
        language="en",
        notes="Major US broadcast news network.",
    ),
    "fox_news": NewsSource(
        name="Fox News",
        base_url="https://www.foxnews.com",
        category="news",
        tier=SourceTier.MAJOR,
        rss_feeds=["https://moxie.foxnews.com/google-publisher/latest.xml"],
        language="en",
        notes="Major US cable news network.",
    ),
    # ── TIER 2: SPECIALIZED ──
    "nature": NewsSource(
        name="Nature",
        base_url="https://www.nature.com",
        category="science",
        tier=SourceTier.SPECIALIZED,
        rss_feeds=[
            "https://www.nature.com/nature.rss",
            "https://www.nature.com/nature/research.rss",
        ],
        notes="Premier international science journal. Peer-reviewed. Founded 1869.",
    ),
    "technology_review": NewsSource(
        name="MIT Technology Review",
        base_url="https://www.technologyreview.com",
        category="technology",
        tier=SourceTier.SPECIALIZED,
        rss_feeds=[
            "https://www.technologyreview.com/feed/",
            "https://www.technologyreview.com/topics/artificial-intelligence/feed/",
        ],
        notes="MIT-owned technology magazine.",
    ),
    "the_verge": NewsSource(
        name="The Verge",
        base_url="https://www.theverge.com",
        category="technology",
        tier=SourceTier.SPECIALIZED,
        rss_feeds=[
            "https://www.theverge.com/rss/index.xml",
            "https://www.theverge.com/ai-artificial-intelligence/rss.xml",
            "https://www.theverge.com/tech/rss.xml",
        ],
        notes="Leading tech news outlet.",
    ),
    "wired": NewsSource(
        name="Wired",
        base_url="https://www.wired.com",
        category="technology",
        tier=SourceTier.SPECIALIZED,
        rss_feeds=[
            "https://www.wired.com/feed/rss",
            "https://www.wired.com/feed/category/technology/latest",
        ],
        notes="Authoritative tech & culture magazine.",
    ),
    "economist": NewsSource(
        name="The Economist",
        base_url="https://www.economist.com",
        category="news",
        tier=SourceTier.MAJOR,
        rss_feeds=[
            "https://www.economist.com/feeds/print-sections/77/business.xml",
            "https://www.economist.com/feeds/print-sections/79/science-and-technology.xml",
        ],
        notes="Weekly news & international affairs publication.",
    ),
    "hbr": NewsSource(
        name="Harvard Business Review",
        base_url="https://hbr.org",
        category="business",
        tier=SourceTier.SPECIALIZED,
        rss_feeds=[
            "https://hbr.org/feed/latest",
            "https://hbr.org/feed/topics/technology",
        ],
        notes="Peer-reviewed business research.",
    ),
    "sciencedaily": NewsSource(
        name="ScienceDaily",
        base_url="https://www.sciencedaily.com",
        category="science",
        tier=SourceTier.SPECIALIZED,
        rss_feeds=[
            "https://www.sciencedaily.com/rss/all.xml",
            "https://www.sciencedaily.com/rss/technology.xml",
            "https://www.sciencedaily.com/rss/matter_energy.xml",
        ],
        notes="Science news aggregator with strict sourcing from peer-reviewed journals.",
    ),
    # ── ADDITIONAL MAJOR ──
    "cnbc": NewsSource(
        name="CNBC",
        base_url="https://www.cnbc.com",
        category="business",
        tier=SourceTier.MAJOR,
        rss_feeds=[
            "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
            "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910",
        ],
        notes="Major US business news network.",
    ),
    "reuters_investigates": NewsSource(
        name="Reuters Investigates",
        base_url="https://www.reuters.com/investigates",
        category="news",
        tier=SourceTier.PRIMARY,
        rss_feeds=["https://www.reuters.com/arc/outboundfeeds/newsletter-rss/world/"],
        notes="Reuters' Pulitzer Prize-winning investigative journalism unit.",
    ),
    # ── TURKISH NEWS SOURCES ──
    "aa": NewsSource(
        name="Anadolu Ajansı (AA)",
        base_url="https://www.aa.com.tr",
        category="news",
        tier=SourceTier.MAJOR,
        rss_feeds=["https://www.aa.com.tr/tr/rss/default?cat=guncel"],
        language="tr", country="turkey",
        notes="Türkiye'nin resmî haber ajansı. 1920'de kuruldu.",
    ),
    "bbc_turkce": NewsSource(
        name="BBC Türkçe",
        base_url="https://www.bbc.com/turkce",
        category="news",
        tier=SourceTier.MAJOR,
        rss_feeds=["https://feeds.bbci.co.uk/turkce/rss.xml"],
        language="tr", country="turkey",
        notes="BBC'nin Türkçe yayını.",
    ),
    "euronews_tr": NewsSource(
        name="Euronews Türkçe",
        base_url="https://tr.euronews.com",
        category="news",
        tier=SourceTier.MAJOR,
        rss_feeds=[],
        language="tr", country="turkey",
        notes="Çok dilli haber ağının Türkçe servisi. ⚠️ RSS feed kullanılamıyor (Mayıs 2026).",
    ),
    "bloomberght": NewsSource(
        name="Bloomberg HT",
        base_url="https://www.bloomberght.com",
        category="business",
        tier=SourceTier.MAJOR,
        rss_feeds=["https://www.bloomberght.com/rss"],
        language="tr", country="turkey",
        notes="Bloomberg'in Türkiye ortaklığıyla yayın yapan finans ve ekonomi kanalı.",
    ),
    "t24": NewsSource(
        name="T24",
        base_url="https://t24.com.tr",
        category="news",
        tier=SourceTier.SPECIALIZED,
        rss_feeds=["https://news.google.com/rss/search?q=site:t24.com.tr&hl=tr&gl=TR&ceid=TR:tr"],
        language="tr", country="turkey",
        notes="Bağımsız haber sitesi. Google News RSS kullanılıyor.",
    ),
    "medyascope": NewsSource(
        name="Medyascope",
        base_url="https://medyascope.tv",
        category="news",
        tier=SourceTier.SPECIALIZED,
        rss_feeds=["https://medyascope.tv/feed/"],
        language="tr", country="turkey",
        notes="Bağımsız haber platformu.",
    ),
    "diken": NewsSource(
        name="Diken",
        base_url="https://www.diken.com.tr",
        category="news",
        tier=SourceTier.SPECIALIZED,
        rss_feeds=["https://www.diken.com.tr/feed/"],
        language="tr", country="turkey",
        notes="Bağımsız haber sitesi.",
    ),
    "birgun": NewsSource(
        name="BirGün",
        base_url="https://www.birgun.net",
        category="news",
        tier=SourceTier.SPECIALIZED,
        rss_feeds=["https://www.birgun.net/rss/home"],
        language="tr", country="turkey",
        notes="Günlük gazete. Bağımsız sol yayın çizgisi.",
    ),
    "sozcu": NewsSource(
        name="Sözcü",
        base_url="https://www.sozcu.com.tr",
        category="news",
        tier=SourceTier.SPECIALIZED,
        rss_feeds=[
            "https://www.sozcu.com.tr/feeds-haberler",
            "https://www.sozcu.com.tr/feeds-son-dakika",
        ],
        language="tr", country="turkey",
        notes="Türkiye'nin en çok okunan gazetelerinden.",
    ),
    "cumhuriyet": NewsSource(
        name="Cumhuriyet",
        base_url="https://www.cumhuriyet.com.tr",
        category="news",
        tier=SourceTier.SPECIALIZED,
        rss_feeds=["http://www.cumhuriyet.com.tr/rss/son_dakika.xml"],
        language="tr", country="turkey",
        notes="Türkiye'nin en köklü gazetelerinden (1924).",
    ),
    "hurriyet": NewsSource(
        name="Hürriyet",
        base_url="https://www.hurriyet.com.tr",
        category="news",
        tier=SourceTier.SPECIALIZED,
        rss_feeds=["http://rss.hurriyet.com.tr/"],
        language="tr", country="turkey",
        notes="Türkiye'nin önde gelen gazetelerinden.",
    ),
    "webrazzi": NewsSource(
        name="Webrazzi",
        base_url="https://webrazzi.com",
        category="technology",
        tier=SourceTier.SPECIALIZED,
        rss_feeds=["https://webrazzi.com/feed/"],
        language="tr", country="turkey",
        notes="Türkiye'nin önde gelen teknoloji haberciliği platformu.",
    ),
}
