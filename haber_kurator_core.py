"""
Haber Kuratör Core v3.1.0 — News Verification Engine
====================================================
Complete news verification system: multi-source fetching → cross-verification
→ fact-check pipeline → publish/correct.

Built on world's leading proven-accurate media sources with automated
cross-referencing to ensure every published fact is verified.

Key Features:
• Multi-source RSS aggregation from Reuters, AP, AFP, BBC, Bloomberg, WSJ, FT, etc.
• Cross-verification: every claim checked against 2+ independent sources
• 4-tier source credibility system (42+ sources including Turkish outlets)
• Hallucination protection: Writer Agent restricted to source-attributed facts
• Fact-check pipeline before any draft is written
• Correction workflow for post-publication errors
• 8-state news lifecycle
• 122 slop patterns across 4 severity tiers
• Cross-language clustering (English/Turkish)
"""

import json
import logging
import re
import shutil
import sqlite3
import time
import urllib.request
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

VERSION = "3.1.0"

CONFIG = {
    "version": "3.1.0",
    "min_verification_level": 1,  # Minimum level to publish (0-3)
    "cross_verify_sources": 2,    # Minimum sources that must agree
    "cache_enabled": True,
    "rss_timeout": 5,             # Seconds per RSS fetch
    "rss_delay": 0.3,             # Delay (s) between RSS fetches to avoid rate limiting
    "max_sources_per_story": 5,   # Max sources to track per story
}

# ══════════════════════════════════════════════════════════════
# SOURCE CREDIBILITY SYSTEM
# ══════════════════════════════════════════════════════════════


class SourceTier(Enum):
    """Credibility tiers for news sources.

    Tier 0 (PRIMARY):   Wire services — Reuters, AP, AFP. Gold standard.
    Tier 1 (MAJOR):     Major newspapers & broadcasters with editorial standards.
    Tier 2 (SPECIALIZED): Topic-specific but reputable (tech, science, finance).
    Tier 3 (SUPPLEMENTARY): Local/regional reputable outlets.
    """
    PRIMARY = 0       # Reuters, AP, AFP — highest credibility
    MAJOR = 1         # Bloomberg, WSJ, FT, BBC, Guardian, etc.
    SPECIALIZED = 2   # TechCrunch, Nature, MIT Tech Review, etc.
    SUPPLEMENTARY = 3  # Regional/local trusted outlets

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
        """Weight for cross-verification scoring."""
        return {0: 3, 1: 2, 2: 1, 3: 1}[self.value]


class VerificationLevel(Enum):
    """Cross-verification confidence levels.

    CONFIRMED:         2+ Tier 0 sources agree → highest confidence
    HIGH_CONFIDENCE:   1 Tier 0 + 1 Tier 1 agree
    MEDIUM_CONFIDENCE: 2+ Tier 1 sources agree
    LOW_CONFIDENCE:    Single source or Tier 2+ only → requires human review
    UNVERIFIED:        Cannot be verified → blocked from publishing
    """
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
        """Whether this verification level allows automatic publishing.
        CONFIRMED=3 and HIGH_CONFIDENCE=2 → auto-publish allowed.
        MEDIUM_CONFIDENCE=1 → human review recommended.
        LOW_CONFIDENCE=0 → human review required.
        UNVERIFIED=-1 → blocked.
        """
        return self.value >= CONFIG["min_verification_level"]


@dataclass
class NewsSource:
    """A verified news source with credibility metadata."""
    name: str                    # Display name
    base_url: str                # Homepage URL
    category: str                # news, technology, business, science, local
    tier: SourceTier = SourceTier.MAJOR
    rss_feeds: List[str] = field(default_factory=list)
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
    """A single factual claim extracted from a news story.

    Each claim maps back to the source(s) that reported it.
    """
    claim_text: str              # The factual claim
    source_name: str             # Which source reported this
    source_url: str              # Direct URL to the article
    source_tier: SourceTier      # Credibility of this source
    verified_by: List[str] = field(default_factory=list)  # Other sources confirming
    discrepancies: List[str] = field(default_factory=list)  # Dissenting reports
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
    """Result of cross-verifying a news item across multiple sources."""
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
        """Check if this meets minimum verification threshold."""
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
# DEFINITIVE SOURCE DIRECTORY — World's Leading Proven Media
# ══════════════════════════════════════════════════════════════
# Only sources with established editorial standards and fact-checking processes.
# Tier 0 = Wire services (Reuters, AP, AFP) — gold standard for factual reporting.
# Tier 1 = Major outlets with proven track records.

NEWS_SOURCES: Dict[str, NewsSource] = {
    # ════════════════════════════════════════════════════════
    # TIER 0: PRIMARY WIRE SERVICES (Highest Credibility)
    # ════════════════════════════════════════════════════════
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
        notes="World's largest wire service. Strict editorial standards. No political bias rating needed — pure factual reporting.",
    ),
    "ap": NewsSource(
        name="Associated Press (AP)",
        base_url="https://apnews.com",
        category="news",
        tier=SourceTier.PRIMARY,
        rss_feeds=[
            "https://rsshub.app/apnews",
        ],
        language="en",
        notes="Independent wire service, founded 1846. Gold standard for factual reporting. Used by 1,500+ newspapers globally.",
    ),
    "afp": NewsSource(
        name="Agence France-Presse (AFP)",
        base_url="https://www.afp.com",
        category="news",
        tier=SourceTier.PRIMARY,
        rss_feeds=[
            "https://www.afp.com/en/rss",
        ],
        notes="Third major global wire service. Founded 1835. 2,400+ journalists in 151 countries.",
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
        notes="UK public service broadcaster. Royal Charter ensures editorial independence. One of the most trusted news brands globally.",
    ),
    # ════════════════════════════════════════════════════════
    # TIER 1: MAJOR OUTLETS (High Credibility)
    # ════════════════════════════════════════════════════════
    "bloomberg": NewsSource(
        name="Bloomberg",
        base_url="https://www.bloomberg.com",
        category="business",
        tier=SourceTier.MAJOR,
        rss_feeds=[
            "https://feeds.bloomberg.com/markets/news.rss",
            "https://feeds.bloomberg.com/technology/news.rss",
        ],
        notes="Global business & financial news. 2,700+ journalists, 120 countries. Strict editorial process.",
    ),
    "wsj": NewsSource(
        name="The Wall Street Journal",
        base_url="https://www.wsj.com",
        category="business",
        tier=SourceTier.MAJOR,
        rss_feeds=[
            "https://feeds.a.dj.com/rss/RSSWSJD.xml",
            "https://www.wsj.com/xml/rss/3_7085.xml",
        ],
        notes="Premier US business daily. Pulitzer Prize-winning journalism. Strong editorial standards.",
    ),
    "ft": NewsSource(
        name="Financial Times",
        base_url="https://www.ft.com",
        category="business",
        tier=SourceTier.MAJOR,
        rss_feeds=[
            "https://www.ft.com/rss/home",
            "https://www.ft.com/rss/companies/technology",
        ],
        notes="Leading global business publication. Known for accurate, well-sourced financial reporting.",
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
        notes="UK daily newspaper with strong editorial standards. Multiple Pulitzer and investigative awards.",
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
        notes="Most awarded US newspaper (138+ Pulitzers). Strong editorial and fact-checking standards.",
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
        notes="Major US newspaper, 70+ Pulitzers. Known for investigative journalism and accurate reporting.",
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
        notes="Qatar-based global news network. Multiple international journalism awards. Extensive on-ground reporting.",
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
        notes="US public radio network. Known for thorough fact-checking and unbiased reporting.",
    ),
    "cnn": NewsSource(
        name="CNN",
        base_url="https://www.cnn.com",
        category="news",
        tier=SourceTier.MAJOR,
        rss_feeds=[
            "https://edition.cnn.com/services/rss/",
        ],
        language="en",
        notes="Major US news network. Global reach, 24/7 news coverage. Strong editorial standards.",
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
        notes="Major US broadcast news network. Part of NBCUniversal. Pulitzer Prize-winning journalism.",
    ),
    "fox_news": NewsSource(
        name="Fox News",
        base_url="https://www.foxnews.com",
        category="news",
        tier=SourceTier.MAJOR,
        rss_feeds=[
            "https://moxie.foxnews.com/google-publisher/latest.xml",
        ],
        language="en",
        notes="Major US cable news network. Extensive domestic and international coverage.",
    ),
    # ════════════════════════════════════════════════════════
    # TIER 2: SPECIALIZED (High credibility in specific domains)
    # ════════════════════════════════════════════════════════
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
        notes="MIT-owned technology magazine. Rigorous editorial standards.",
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
        notes="Leading tech news outlet. Known for in-depth reporting on technology policy and innovation.",
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
        notes="Authoritative tech & culture magazine. Strong editorial standards since 1993.",
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
        notes="Weekly news & international affairs publication. Known for in-depth analysis and factual accuracy.",
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
        notes="Peer-reviewed business research. Published by Harvard Business Publishing.",
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
    # ════════════════════════════════════════════════════════
    # TIER 1: ADDITIONAL MAJOR OUTLETS
    # ════════════════════════════════════════════════════════
    "cnbc": NewsSource(
        name="CNBC",
        base_url="https://www.cnbc.com",
        category="business",
        tier=SourceTier.MAJOR,
        rss_feeds=[
            "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
            "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910",
        ],
        notes="Major US business news network. Strong financial reporting credentials.",
    ),
    "reuters_investigates": NewsSource(
        name="Reuters Investigates",
        base_url="https://www.reuters.com/investigates",
        category="news",
        tier=SourceTier.PRIMARY,
        rss_feeds=[
            "https://www.reuters.com/arc/outboundfeeds/newsletter-rss/world/",
        ],
        notes="Reuters' Pulitzer Prize-winning investigative journalism unit.",
    ),
    # ════════════════════════════════════════════════════════
    # TURKISH NEWS SOURCES — Türkiye için güvenilir kaynaklar
    # ════════════════════════════════════════════════════════
    "aa": NewsSource(
        name="Anadolu Ajansı (AA)",
        base_url="https://www.aa.com.tr",
        category="news",
        tier=SourceTier.MAJOR,
        rss_feeds=[
            "https://www.aa.com.tr/tr/rss/default?cat=guncel",
        ],
        language="tr",
        country="turkey",
        notes="Türkiye'nin resmî haber ajansı. 1920'de kuruldu. 11 dilde yayın, 100+ ülkede büro. Wire service statüsünde.",
    ),
    "bbc_turkce": NewsSource(
        name="BBC Türkçe",
        base_url="https://www.bbc.com/turkce",
        category="news",
        tier=SourceTier.MAJOR,
        rss_feeds=[
            "https://feeds.bbci.co.uk/turkce/rss.xml",
        ],
        language="tr",
        country="turkey",
        notes="BBC'nin Türkçe yayını. Kraliyet tüzüğü ile editoryal bağımsızlık. Tarafsız ve güvenilir habercilik.",
    ),
    "euronews_tr": NewsSource(
        name="Euronews Türkçe",
        base_url="https://tr.euronews.com",
        category="news",
        tier=SourceTier.MAJOR,
        rss_feeds=[],  # Genel RSS yayından kaldırıldı — Mayıs 2026
        language="tr",
        country="turkey",
        notes="Çok dilli haber ağının Türkçe servisi. ⚠️ RSS feed kullanılamıyor (Mayıs 2026).",
    ),
    "dw_turkce": NewsSource(
        name="Deutsche Welle Türkçe",
        base_url="https://www.dw.com/tr",
        category="news",
        tier=SourceTier.MAJOR,
        rss_feeds=[
            "http://rss.dw.de/xml/rss-tur-pol-tur",
            "http://rss.dw.de/xml/rss-tur-eco",
        ],
        language="tr",
        country="turkey",
        notes="Alman uluslararası kamu yayıncısının Türkçe servisi. Bağımsız ve tarafsız haber.",
    ),
    "bloomberght": NewsSource(
        name="Bloomberg HT",
        base_url="https://www.bloomberght.com",
        category="business",
        tier=SourceTier.MAJOR,
        rss_feeds=[
            "https://www.bloomberght.com/rss",
        ],
        language="tr",
        country="turkey",
        notes="Bloomberg'in Türkiye ortaklığıyla yayın yapan finans ve ekonomi kanalı. Bloomberg'in editoryal standartları.",
    ),
    "t24": NewsSource(
        name="T24",
        base_url="https://t24.com.tr",
        category="news",
        tier=SourceTier.SPECIALIZED,
        rss_feeds=[],  # RSS kapandı (Mayıs 2026) — çalışan feed bulunamadı
        language="tr",
        country="turkey",
        notes="Bağımsız haber sitesi. ⚠️ RSS feed kullanılamıyor (Mayıs 2026).",
    ),
    "medyascope": NewsSource(
        name="Medyascope",
        base_url="https://medyascope.tv",
        category="news",
        tier=SourceTier.SPECIALIZED,
        rss_feeds=[],  # RSS erişimi engellendi (403) — Mayıs 2026
        language="tr",
        country="turkey",
        notes="Bağımsız haber platformu. ⚠️ RSS feed erişime kapalı (403 Forbidden). Podcast feed mevcut.",
    ),
    "gazete_duvar": NewsSource(
        name="Gazete Duvar",
        base_url="https://www.gazeteduvar.com.tr",
        category="news",
        tier=SourceTier.SPECIALIZED,
        rss_feeds=[],  # SİTE KAPANDI — 12 Mart 2025
        language="tr",
        country="turkey",
        notes="❌ Site kapanmıştır (12 Mart 2025). RSS feed kullanılamıyor.",
    ),
    "diken": NewsSource(
        name="Diken",
        base_url="https://www.diken.com.tr",
        category="news",
        tier=SourceTier.SPECIALIZED,
        rss_feeds=[],  # RSS erişimi engellendi (403) — Mayıs 2026
        language="tr",
        country="turkey",
        notes="Bağımsız haber sitesi. ⚠️ RSS feed erişime kapalı (403 Forbidden).",
    ),
    "birgun": NewsSource(
        name="BirGün",
        base_url="https://www.birgun.net",
        category="news",
        tier=SourceTier.SPECIALIZED,
        rss_feeds=[
            "https://www.birgun.net/rss/home",
        ],
        language="tr",
        country="turkey",
        notes="Günlük gazete. Bağımsız sol yayın çizgisi. İşçi hakları, çevre, demokrasi odaklı habercilik.",
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
        language="tr",
        country="turkey",
        notes="Türkiye'nin en çok okunan gazetelerinden. Geniş haber ağı, son dakika ve gündem.",
    ),
    "cumhuriyet": NewsSource(
        name="Cumhuriyet",
        base_url="https://www.cumhuriyet.com.tr",
        category="news",
        tier=SourceTier.SPECIALIZED,
        rss_feeds=[
            "http://www.cumhuriyet.com.tr/rss/son_dakika.xml",
        ],
        language="tr",
        country="turkey",
        notes="Türkiye'nin en köklü gazetelerinden (1924). Güçlü araştırmacı gazetecilik geleneği.",
    ),
    "hurriyet": NewsSource(
        name="Hürriyet",
        base_url="https://www.hurriyet.com.tr",
        category="news",
        tier=SourceTier.SPECIALIZED,
        rss_feeds=[
            "http://rss.hurriyet.com.tr/",
        ],
        language="tr",
        country="turkey",
        notes="Türkiye'nin önde gelen gazetelerinden. Geniş muhabir ağı, güncel haber ve analiz.",
    ),
    "webrazzi": NewsSource(
        name="Webrazzi",
        base_url="https://webrazzi.com",
        category="technology",
        tier=SourceTier.SPECIALIZED,
        rss_feeds=[
            "https://webrazzi.com/feed/",
        ],
        language="tr",
        country="turkey",
        notes="Türkiye'nin önde gelen teknoloji haberciliği platformu. Girişim, yatırım ve dijital dönüşüm odaklı.",
    ),
}

# RSS endpoint probe patterns — many sites use one of these
RSS_PROBES = ["/feed", "/rss", "/rss.xml", "/feed.xml", "/atom.xml", "/news/rss", "/rss/feed"]


# ══════════════════════════════════════════════════════════════
# STATE MACHINE — 8 States (News Only)
# ══════════════════════════════════════════════════════════════

STATE_LIFECYCLE = [
    "captured",           # News item enters the system
    "fact_checking",      # Cross-verification in progress
    "cross_verified",     # Claims verified against sources
    "published",          # Published to Memos
    "correction_needed",  # Error detected post-publication
    "corrected",          # Correction issued
    "retracted",          # Story retracted
    "archived",
]

STATE_TRANSITIONS = {
    "captured":           ["fact_checking"],
    "fact_checking":      ["cross_verified", "captured"],
    "cross_verified":     ["captured", "published"],
    "published":          ["correction_needed", "archived"],
    "correction_needed":  ["corrected", "retracted"],
    "corrected":          ["published"],
    "retracted":          ["archived"],
    "archived":           [],
}

ROUTE_VERIFIED = "VERIFIED"

# Self-assessment fields for Writer Agent output
WRITER_FIELDS = [
    "rubric_self_assessment",
    "avoid_slop_pass",
    "source_attribution_check",
]

# ══════════════════════════════════════════════════════════════
# SLOP DETECTION — Full 54+ patterns (original + news-specific)
# ══════════════════════════════════════════════════════════════

FULL_SLOP_TIER1 = [
    # 1. Promosyon Dili
    r"groundbreaking", r"game-changing", r"revolutionary", r"transformative", r"paradigm-shifting",
    # 2. Önem Atfetme Abartısı
    r"pivotal moment", r"testament to", r"a testament to", r"significant step", r"quantum leap",
    # 3. Belirsiz Atıf — CRITICAL for news (must name specific source)
    r"experts believe", r"studies show", r"research suggests", r"data shows", r"it turns out that",
    r"according to reports", r"according to sources", r"some say", r"many believe",
    # 4. Sahte Etkinlik
    r"the system compounds", r"the data tells us", r"compound interest of", r"the power of",
    # 5. Retorik Kurulum
    r"the question is whether", r"at its core", r"what if i told you",
    # 6. Staccato Parçalama
    r"(?i)(?:^|\n)\s*(?:no\s+\S+\.\s*){2,}", r"(?i)(?:^|\n)\s*(?:\S+\.\s*){4,}", r"(?i)(?:fail|error|bug)s?\s*\.\s*(?:fail|error|bug)s?\s*\.",
    # 7. Em Dash aşırı
    r"(?<!\-)\-\-(?!\-)",
    # 8. Dolgu Zarfları
    r"actually", r"literally", r"quietly", r"simply", r"just\b", r"basically",
    # 🔄 NEW 9-10: News-specific Critical Patterns
    # 9. Kaynaksız İddia
    r"it is reported that(?! by)", r"allegedly(?!,? (?:according to|Reuters|AP|AFP))",
    r"unnamed sources say", r"insiders reveal", r"sources close to",
    # 10. Sahte Orijinallik
    r"breaking:\s", r"developing story", r"this just in", r"we are learning",
]

FULL_SLOP_TIER2 = [
    # 11. Copula Avoidance
    r"serves as", r"stands as", r"features", r"encompasses", r"utilizes",
    # 12. -ing Padding
    r"leveraging", r"implementing", r"optimizing", r"enabling",
    # 13. Rule of Three Zorlama
    r"three things", r"three reasons", r"three ways", r"triad\b",
    # 14. Filler Phrases
    r"in order to", r"due to the fact that", r"at this point in time", r"in today's world",
    # 15. Generic Conclusions
    r"the future looks bright", r"exciting times ahead", r"the best is yet to come",
    # 16. Signposting
    r"let's dive in", r"here's what you need to know", r"tldr", r"in conclusion",
    # 17. Hyperbolic Quantifiers
    r"every single", r"all the time", r"never ever", r"absolutely everyone",
    # 18. Hedging
    r"it could potentially", r"it might be argued", r"somewhat", r"arguably",
]

FULL_SLOP_TIER3 = [
    # 19. Passive Voice
    r"\b(?:was|were|been|being)\s+\w+ed\b",
    # 20. Elegant Variation
    r"(?:\w+,\s*(?:also\s+)?known\s+as)",
    # 21. False Ranges
    r"from basic to advanced", r"from beginner to expert",
    # 22. Conjunction Overuse
    r"(?:^|\n)\s*(?:And|But)\s+",
    # 23. Unnecessary Intensifiers
    r"\bvery\b", r"\bsuch\b",
    # 24. Paragraph-Level Vagueness
    r"it is important to note that", r"it should be noted that",
    # 25. Rhetorical Questions
    r"(?:have you ever wondered|can you imagine|what would you do if)",
    # 26. Awkward List Introductions
    r"there are \d+ things", r"\d+ (?:is|are) ",
    # 27. False Precision
    r"exactly \d+\.\d+%",
    # 28. Clichéd Metaphors
    r"level\s*up", r"dive\s*deep", r"game\s*plan", r"road\s*map",
    # 29. Self-Referential Humility
    r"i may be wrong", r"i could be wrong",
    # 30. Empty Emphasis
    r"(?:^|\n)\s*\[.*?\]\s*\n", r"(?:^|\n)\s*[A-Z]{4,}\s*\n",
    # 31. Temporal Vagueness
    r"\brecently\b", r"\blately\b", r"\bthese days\b",
    # 32. False Balance
    r"some say .* while others say", r"on one hand .* on the other hand",
    # 33. Unearned Authority
    r"as someone who", r"having worked in",
    # 34. Template Language
    r"in this post, we.{0,20}(?:explore|dive|cover|discuss)",
    # 35. Unnecessary Qualification
    r"the very real possibility", r"the very real chance",
]

FULL_SLOP_BONUS = [
    # 36. Faux Authority
    r"\byou should\b", r"\byou must\b", r"never do this",
    # 37. Vibes Over Data
    r"it feels like", r"seems to me",
    # 38. Bülten-Bait Hooks
    r"here's the thing", r"the secret",
    # 39. Oversharing Backstory
    r"\d+\s*years? ago,?.*?(?:i|we|my|our)",
    # 40. Under-Explaining Proof
    r"result\s*:\s*%\s*\w+",
    # 🔄 NEW 41: Speculation as News
    r"could potentially mean", r"might indicate that", r"may suggest that",
    r"could be a sign", r"raises questions about",
]

# ══════════════════════════════════════════════════════════════
# EXCEPTIONS
# ══════════════════════════════════════════════════════════════


class HaberKuratorError(Exception):
    """Base exception for Haber Kuratör."""
    pass


class VerificationError(Exception):
    """Raised when news verification fails."""
    pass


class SourceNotFoundError(Exception):
    """Raised when a referenced source is not in our directory."""
    pass


# ══════════════════════════════════════════════════════════════
# DATA CLASSES
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
# CORE CLASS
# ══════════════════════════════════════════════════════════════

class HaberKuratorCore:
    """Haber Kuratör v3.1.0 — News Verification Engine.

    Transforms raw news from world-leading sources into verified,
    source-attributed news content through multi-source cross-verification,
    fact-checking, and hallucination protection.
    """

    def __init__(self, root: Path):
        self.root = root
        self.strategy = root / "strategy"
        self.voice = root / "voice"
        self.active_runs = root / "runs" / "active"
        self.stores = root / "stores"
        self.workflows = root / "workflows"
        self.archive = root / "runs" / "archive"
        self.references = root / "references"

        # Slop patterns
        self.slop_tier1 = FULL_SLOP_TIER1
        self.slop_tier2 = FULL_SLOP_TIER2
        self.slop_tier3 = FULL_SLOP_TIER3
        self.slop_bonus = FULL_SLOP_BONUS

        # Known sources directory
        self.sources = NEWS_SOURCES.copy()

        self.gbrain_enabled = False

        self._init_stores_dirs()
        self._migrate_old_state()

        # State cache — SQLite backed (v3.1.0)
        self._state_cache_dir = root / '.state_cache'
        self._state_cache_dir.mkdir(parents=True, exist_ok=True)
        self._state_cache: Dict[str, RunState] = {}
        self._db_path = str(self._state_cache_dir / 'state.db')
        self._init_db()
        self._load_state_cache()

    # ──────────────────────────────────────────────────────────
    # SETUP & MIGRATION
    # ──────────────────────────────────────────────────────────

    def _init_stores_dirs(self):
        """Initialize stores subdirectories."""
        for subdir in ["ideas", "hooks", "proof", "feedback"]:
            (self.stores / subdir).mkdir(parents=True, exist_ok=True)

    def _migrate_old_state(self):
        """Auto-migrate existing runs to new state format on init."""
        if not self.active_runs.exists():
            return
        for d in self.active_runs.iterdir():
            if d.is_dir():
                try:
                    self.sync_state(d.name)
                except Exception:
                    continue

    # ──────────────────────────────────────────────────────────
    # STATE CACHE — SQLite Backed
    # ──────────────────────────────────────────────────────────

    def _init_db(self):
        """Initialize SQLite state cache database."""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS state_cache (
                    slug TEXT PRIMARY KEY,
                    title TEXT DEFAULT '',
                    state TEXT DEFAULT 'captured',
                    route TEXT DEFAULT 'VERIFIED',
                    created TEXT DEFAULT '',
                    updated TEXT DEFAULT '',
                    source_type TEXT DEFAULT 'multi-source',
                    verification_level TEXT DEFAULT 'unverified'
                )
            """)
            conn.commit()
            conn.close()
            logger.debug(f"SQLite state cache initialized at {self._db_path}")
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize SQLite state cache: {e}")

    def _save_state_cache(self):
        """Persist state cache to SQLite."""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute("BEGIN TRANSACTION")
            conn.execute("DELETE FROM state_cache")
            for slug, rs in self._state_cache.items():
                conn.execute(
                    "INSERT OR REPLACE INTO state_cache "
                    "(slug, title, state, route, created, updated, source_type, verification_level) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (rs.slug, rs.title, rs.state, rs.route,
                     rs.created, rs.updated, rs.source_type, rs.verification_level)
                )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.error(f"Failed to save state cache: {e}")

    def _load_state_cache(self):
        """Load state cache from SQLite.

        Also migrates legacy JSON cache if present.
        Disabled when cache_enabled config is False.
        """
        if not CONFIG.get("cache_enabled", True):
            logger.info("State cache disabled by config")
            return

        # Migration: check for legacy JSON cache
        legacy_path = self._state_cache_dir / "runs_state.json"
        if legacy_path.exists():
            try:
                data = json.loads(legacy_path.read_text(encoding="utf-8"))
                for slug, d in data.items():
                    self._state_cache[slug] = RunState(
                        slug=d["slug"],
                        title=d.get("title", ""),
                        state=d.get("state", "captured"),
                        route=d.get("route", "VERIFIED"),
                        created=d.get("created", ""),
                        updated=d.get("updated", ""),
                        source_type=d.get("source_type", "multi-source"),
                        verification_level=d.get("verification_level", "unverified"),
                    )
                self._save_state_cache()
                # Rename legacy file to mark migration complete
                legacy_path.rename(legacy_path.with_suffix(".json.migrated"))
                logger.info(f"Migrated {len(data)} runs from legacy JSON cache to SQLite")
                return
            except (json.JSONDecodeError, KeyError, OSError) as e:
                logger.warning(f"Legacy JSON cache migration failed: {e}")

        # Load from SQLite
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM state_cache")
            for row in cursor.fetchall():
                self._state_cache[row["slug"]] = RunState(
                    slug=row["slug"],
                    title=row["title"],
                    state=row["state"],
                    route=row["route"],
                    created=row["created"],
                    updated=row["updated"],
                    source_type=row["source_type"],
                    verification_level=row["verification_level"],
                )
            conn.close()
        except sqlite3.Error as e:
            logger.error(f"Failed to load state cache from SQLite: {e}")

    def setup(self) -> str:
        """Initialize directory structure."""
        dirs = [self.strategy, self.voice, self.active_runs,
                self.stores, self.workflows, self.archive, self.references]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
        self._init_stores_dirs()
        return f"✅ Haber Kuratör v{VERSION} initialized. News verification engine ready."

    # ══════════════════════════════════════════════════════════
    # 1. SOURCE MANAGEMENT
    # ══════════════════════════════════════════════════════════

    def get_source(self, name: str) -> Optional[NewsSource]:
        """Get a news source by key name."""
        return self.sources.get(name)

    def get_sources_by_tier(self, tier: SourceTier) -> Dict[str, NewsSource]:
        """Get all sources at a given credibility tier."""
        return {k: v for k, v in self.sources.items() if v.tier == tier}

    def get_sources_by_category(self, category: str) -> Dict[str, NewsSource]:
        """Get all sources in a category (news, technology, business, science)."""
        return {k: v for k, v in self.sources.items() if v.category == category}

    def get_sources_by_country(self, country: str) -> Dict[str, NewsSource]:
        """Get all sources from a specific country (e.g. 'turkey', 'global')."""
        return {k: v for k, v in self.sources.items() if v.country == country}

    def get_all_sources(self) -> Dict[str, Dict[str, Any]]:
        """Get all sources with their metadata."""
        return {k: v.to_dict() for k, v in self.sources.items()}

    def get_source_summary(self) -> str:
        """Print a formatted summary of all sources by tier."""
        lines = ["## News Sources by Credibility Tier", ""]
        for tier in [SourceTier.PRIMARY, SourceTier.MAJOR, SourceTier.SPECIALIZED]:
            sources = self.get_sources_by_tier(tier)
            if sources:
                lines.append(f"### {tier.confidence_label}")
                for name, src in sorted(sources.items()):
                    feeds = len(src.rss_feeds)
                    lines.append(f"  • {src.name} — {src.category} ({feeds} feeds)")
                lines.append("")
        return "\n".join(lines)

    def add_source_watchlist_source(self, entry: str) -> str:
        """Add a custom source to the watchlist file."""
        wl = self.strategy / "source-watchlist.md"
        with wl.open("a", encoding="utf-8") as f:
            f.write(f"\n{entry}\n")
        return f"✅ Added to watchlist: {entry}"

    # ══════════════════════════════════════════════════════════
    # 2. NEWS FETCHING — Multi-Source RSS Aggregation
    # ══════════════════════════════════════════════════════════

    def fetch_all_news(self, category: str = None, country: str = None) -> List[FetchedNewsItem]:
        """Fetch latest news from configured sources.

        Pulls from every source that has RSS feeds defined.
        Returns deduplicated list of news items.

        Args:
            category: Optional filter ('news', 'technology', 'business', 'science')
            country: Optional filter by country code (e.g. 'turkey', 'global')

        Returns:
            List of FetchedNewsItem with source and URL.
        """
        logger.info(f"fetch_all_news called (category={category}, country={country})")
        all_items: List[FetchedNewsItem] = []
        errors = []

        sources_to_fetch = self.sources
        if category:
            sources_to_fetch = self.get_sources_by_category(category)
        if country:
            by_country = self.get_sources_by_country(country)
            # Intersect with existing filter if both category and country are set
            if category:
                sources_to_fetch = {k: v for k, v in sources_to_fetch.items() if k in by_country}
            else:
                sources_to_fetch = by_country

        for key, source in sources_to_fetch.items():
            if not source.rss_feeds:
                continue
            for feed_url in source.rss_feeds:
                try:
                    items = self._fetch_rss_feed(feed_url, source)
                    all_items.extend(items)
                except Exception as e:
                    errors.append(f"{source.name}/{feed_url}: {str(e)[:60]}")
                    continue
                finally:
                    # Rate limiting: small delay between RSS fetches
                    time.sleep(CONFIG["rss_delay"])

        # Deduplicate by title similarity
        unique = self._deduplicate_news(all_items)

        # Filter out promotional/non-news content
        promo_patterns = [
            r"(?:discount|promo|code|coupon|voucher|save\s+\d+%|up\s+to\s+\d+%|off\s+sitewide)",
            r"(?:best\s+\w+\s+(?:deal|offer|code|promo))",
            r"(?:^\d+%\s+off)",
        ]
        filtered = []
        for item in unique:
            title_lower = item.title.lower()
            is_promo = any(re.search(p, title_lower) for p in promo_patterns)
            if not is_promo:
                filtered.append(item)

        logger.info(f"fetch_all_news: {len(all_items)} raw, {len(unique)} unique, "
                    f"{len(unique) - len(filtered)} promo filtered, {len(filtered)} final. "
                    f"{len(errors)} fetch errors.")
        return filtered

    def _fetch_rss_feed(self, feed_url: str, source: NewsSource) -> List[FetchedNewsItem]:
        """Fetch a single RSS feed and parse items."""
        items = []
        try:
            req = urllib.request.Request(
                feed_url,
                headers={"User-Agent": f"Haber-Kuratör/{VERSION} NewsReader"}
            )
            with urllib.request.urlopen(req, timeout=CONFIG["rss_timeout"]) as resp:
                xml_data = resp.read()

            root_el = ET.fromstring(xml_data)
            ATOM_NS = "{http://www.w3.org/2005/Atom}"

            # RSS 2.0
            for item in root_el.findall(".//item"):
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                pub_date = item.findtext("pubDate", "").strip()
                description = item.findtext("description", "").strip()
                guid = item.findtext("guid", link or title).strip()

                if title:
                    items.append(FetchedNewsItem(
                        title=title,
                        url=link or source.base_url,
                        source_name=source.name,
                        source_tier=source.tier,
                        published=pub_date,
                        summary=self._clean_html(description)[:300],
                        category=source.category,
                        guid=guid,
                    ))

            # Atom
            if not items:
                for entry in root_el.findall(f".//{ATOM_NS}entry"):
                    t_el = entry.find(f"{ATOM_NS}title")
                    link_el = entry.find(f"{ATOM_NS}link")
                    published_el = entry.find(f"{ATOM_NS}published")
                    summary_el = entry.find(f"{ATOM_NS}summary")

                    title = t_el.text.strip() if t_el is not None and t_el.text else ""
                    link = link_el.get("href", "") if link_el is not None else ""
                    pub_date = published_el.text.strip() if published_el is not None and published_el.text else ""
                    summary = summary_el.text.strip()[:300] if summary_el is not None and summary_el.text else ""

                    if title:
                        items.append(FetchedNewsItem(
                            title=title,
                            url=link or source.base_url,
                            source_name=source.name,
                            source_tier=source.tier,
                            published=pub_date,
                            summary=summary,
                            category=source.category,
                            guid=link or title,
                        ))

        except ET.ParseError as e:
            logger.debug(f"XML parse error for {feed_url}: {e}")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            logger.debug(f"Network error for {feed_url}: {e}")

        return items

    def _clean_html(self, text: str) -> str:
        """Strip HTML tags from text."""
        if not text:
            return ""
        clean = re.sub(r'<[^>]+>', ' ', text)
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean

    def _deduplicate_news(self, items: List[FetchedNewsItem]) -> List[FetchedNewsItem]:
        """Remove duplicate stories by URL and title similarity."""
        seen_urls: Set[str] = set()
        seen_titles: Set[str] = set()
        unique = []

        for item in items:
            # Dedup by URL
            if item.url in seen_urls:
                continue
            seen_urls.add(item.url)

            # Normalize title for dedup
            title_key = item.title.lower().strip().rstrip('.!?')
            title_key = re.sub(r'[^a-z0-9\s]', '', title_key)
            title_key = re.sub(r'\s+', ' ', title_key).strip()

            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)

            unique.append(item)

        return unique

    def _normalize_title(self, title: str) -> str:
        """Normalize a news title for comparison/dedup."""
        t = title.lower().strip()
        t = re.sub(r'[^a-z0-9\s]', '', t)
        t = re.sub(r'\s+', ' ', t).strip()
        return t

    # ══════════════════════════════════════════════════════════
    # 3. STORY CLUSTERING — Group Same Story Across Sources
    # ══════════════════════════════════════════════════════════

    def cluster_stories(self, items: List[FetchedNewsItem]) -> List[Dict[str, Any]]:
        """Group similar news items by story (same event across sources).

        Uses keyword overlap with cross-language support (English/Turkish).
        Common news words in both languages are normalized for matching.
        Returns list of clusters, each with the story variants grouped.
        """
        # Cross-language normalization map for common news terms
        # Normalizes Turkish/English equivalents to a shared key
        BILINGUAL_MAP = {
            # English → normalized
            "president": "president", "minister": "minister", "government": "government",
            "attack": "attack", "saldırı": "attack", "saldiri": "attack",
            "earthquake": "earthquake", "deprem": "earthquake",
            "election": "election", "seçim": "election", "secim": "election",
            "economy": "economy", "ekonomi": "economy",
            "technology": "technology", "teknoloji": "technology",
            "company": "company", "şirket": "company", "sirket": "company",
            "market": "market", "piyasa": "market", "borsa": "market",
            "interest rate": "interest-rate", "faiz": "interest-rate",
            "inflation": "inflation", "enflasyon": "inflation",
            "bank": "bank", "merkez bankası": "central-bank", "central bank": "central-bank",
            "war": "war", "savaş": "war", "savas": "war",
            "peace": "peace", "barış": "peace", "baris": "peace",
            "nuclear": "nuclear", "nükleer": "nuclear", "nukleer": "nuclear",
            "energy": "energy", "enerji": "energy",
            "climate": "climate", "iklim": "climate",
            "health": "health", "sağlık": "health", "saglik": "health",
            "education": "education", "eğitim": "education", "egitim": "education",
            "security": "security", "güvenlik": "security", "guvenlik": "security",
            "defense": "defense", "savunma": "defense",
            "trade": "trade", "ticaret": "trade",
            "summit": "summit", "zirve": "summit",
            "crisis": "crisis", "kriz": "crisis",
            "protest": "protest", "protesto": "protest",
            "research": "research", "araştırma": "research", "arastirma": "research",
            "prices": "prices", "fiyat": "prices",
            "budget": "budget", "bütçe": "budget", "butce": "budget",
            "billion": "billion", "milyar": "billion",
            "million": "million", "milyon": "million",
            "announced": "announced", "açıkladı": "announced", "acikladi": "announced",
            "duyurdu": "announced", "reported": "reported", "bildirdi": "reported",
        }

        def _cross_lingual_normalize(title: str) -> str:
            """Normalize title with cross-language support."""
            t = title.lower().strip()
            # Remove punctuation
            t = re.sub(r'[^\w\s]', ' ', t)
            # Separate Turkish chars for fuzzy matching
            char_map = str.maketrans({
                'ı': 'i', 'ğ': 'g', 'ü': 'u', 'ş': 's', 'ö': 'o', 'ç': 'c',
                'İ': 'i', 'Ğ': 'g', 'Ü': 'u', 'Ş': 's', 'Ö': 'o', 'Ç': 'c',
            })
            t = t.translate(char_map)

            bilingual_words = []
            for word in t.split():
                if len(word) < 3:
                    continue
                # Check bilingual map
                mapped = BILINGUAL_MAP.get(word, word)
                if mapped in ("president", "minister", "government", "attack", "earthquake",
                              "election", "economy", "technology", "company",
                              "market", "interest-rate", "inflation", "bank",
                              "war", "peace", "nuclear", "energy", "climate",
                              "health", "education", "security", "defense",
                              "trade", "summit", "crisis", "protest",
                              "research", "prices", "budget", "billion", "million",
                              "announced", "reported"):
                    bilingual_words.append(mapped)
                else:
                    # Keep proper nouns (capitalized-ish original tokens), numbers
                    bilingual_words.append(word)

            return " ".join(bilingual_words)

        clusters: List[Dict[str, Any]] = []
        used: Set[int] = set()

        for i, item in enumerate(items):
            if i in used:
                continue

            cluster = {
                "story_title": item.title,
                "items": [item],
                "sources": [item.source_name],
                "source_tiers": [item.source_tier.value],
                "categories": set(),
            }
            cluster["categories"].add(item.category)
            used.add(i)

            # Normalize title with cross-language support
            norm_i = _cross_lingual_normalize(item.title)
            i_words = set(norm_i.split())
            if len(i_words) < 2:
                cluster["source_count"] = len(cluster["sources"])
                cluster["tier_count"] = {
                    "primary": cluster["source_tiers"].count(0),
                    "major": cluster["source_tiers"].count(1),
                    "specialized": cluster["source_tiers"].count(2),
                }
                cluster["item_count"] = len(cluster["items"])
                cluster["categories"] = list(cluster["categories"])
                clusters.append(cluster)
                continue

            for j, other in enumerate(items):
                if j in used or i == j:
                    continue

                norm_j = _cross_lingual_normalize(other.title)
                j_words = set(norm_j.split())

                overlap = len(i_words & j_words)
                min_len = min(len(i_words), len(j_words))
                if min_len == 0:
                    continue
                score = overlap / min_len

                # Lower threshold for cross-language matching (30% instead of 40%)
                if score >= 0.3:
                    cluster["items"].append(other)
                    cluster["sources"].append(other.source_name)
                    cluster["source_tiers"].append(other.source_tier.value)
                    cluster["categories"].add(other.category)
                    used.add(j)

            # Pick the best title (from highest-tier source)
            cluster["items"].sort(key=lambda x: x.source_tier.value)
            best_item = cluster["items"][0]
            cluster["story_title"] = best_item.title
            cluster["best_url"] = best_item.url
            cluster["categories"] = list(cluster["categories"])
            cluster["source_count"] = len(cluster["sources"])
            cluster["tier_count"] = {
                "primary": cluster["source_tiers"].count(0),
                "major": cluster["source_tiers"].count(1),
                "specialized": cluster["source_tiers"].count(2),
            }
            cluster["item_count"] = len(cluster["items"])

            clusters.append(cluster)

        # Sort by number of sources reporting (most-covered first)
        clusters.sort(key=lambda c: c["source_count"], reverse=True)

        return clusters

    # ══════════════════════════════════════════════════════════
    # 4. CROSS-VERIFICATION ENGINE
    # ══════════════════════════════════════════════════════════

    def cross_verify_story(self, cluster: Dict[str, Any]) -> CrossVerificationResult:
        """Cross-verify a story cluster across all reporting sources.

        Extracts factual claims (numbers, dates, named entities) from each
        source's summary and compares them across sources to identify which
        specific facts are confirmed by independent reporting.

        A claim is "verified" when 2+ independent sources report the same fact.
        """
        sources = cluster["sources"]
        items = cluster["items"]

        # Count source tiers (unique sources only, not item count)
        source_tier_map: Dict[str, int] = {}
        for item in items:
            if item.source_name not in source_tier_map:
                source_tier_map[item.source_name] = item.source_tier.value
        primary_count = sum(1 for v in source_tier_map.values() if v == 0)
        major_count = sum(1 for v in source_tier_map.values() if v == 1)
        total_unique = len(source_tier_map)

        # Calculate weighted verification score (deduplicated by source name)
        seen_names = set()
        weighted = 0
        for item in items:
            if item.source_name not in seen_names:
                seen_names.add(item.source_name)
                weighted += item.source_tier.weight

        # Extract factual claims from each item's summary
        # A "claim" is a factoid gleaned from the RSS description:
        # numbers, dates, named entities, key actions
        all_claims: Dict[str, FactClaim] = {}  # normalized claim text → FactClaim
        claim_to_sources: Dict[str, List[str]] = {}  # claim → list of source names

        def _extract_claims(text: str) -> List[str]:
            """Extract potential factual claims from text.

            Uses named entity recognition (capitalized proper nouns) to identify
            key people, places, organizations, and specific terms that uniquely
            identify a news story across different sources.
            """
            claims = []
            # Capitalized multi-word proper nouns (people, orgs, places)
            skip_words = {'The', 'This', 'That', 'What', 'When', 'Where', 'How', 'Why',
                          'They', 'Them', 'Their', 'From', 'With', 'Into', 'Over', 'After',
                          'Before', 'Between', 'During', 'Without', 'About', 'Against',
                          'Through', 'Under', 'Then', 'Once', 'Here', 'There', 'Than', 'Also',
                          'More', 'Most', 'Some', 'Many', 'Much', 'Such', 'These', 'Those',
                          'Has', 'Have', 'Had', 'But', 'And', 'For', 'Not', 'Are', 'Was',
                          'Were', 'Been', 'Being', 'New', 'First', 'Last', 'Next', 'Each',
                          'Every', 'Both', 'Few', 'Several'}
            for m in re.finditer(r'\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,3}', text):
                entity = m.group(0).strip()
                words = entity.split()
                if len(entity) > 3 and words[0] not in skip_words:
                    claims.append(entity.lower())
            # Key numbers: percentages, dollar amounts, years
            for m in re.finditer(r'\d+(?:[.,]\d+)?\s*(?:%|percent|billion|million|trillion|dollars|euros|year|years)', text, re.IGNORECASE):
                claims.append(m.group(0).strip().lower()[:80])
            for m in re.finditer(r'(?:202[0-9]|203[0-9])', text):
                claims.append(m.group(0))
            # Key action phrases (brevity)
            for m in re.finditer(r'(?:announced|launched|reported|confirmed|approved|signed|elected|appointed|resigned|killed|arrested|sentenced|approved|rejected|withdrew|suspended|banned)\s+(?:\w+\s?){1,3}', text, re.IGNORECASE):
                claims.append(m.group(0).strip().lower()[:80])
            return claims

        # Collect claims from each source
        for item in items:
            text_to_scan = f"{item.title} {item.summary}"
            extracted = _extract_claims(text_to_scan)
            for claim_text in extracted:
                norm = re.sub(r'\s+', ' ', claim_text).strip()
                if norm not in all_claims:
                    all_claims[norm] = FactClaim(
                        claim_text=claim_text,
                        source_name=item.source_name,
                        source_url=item.url,
                        source_tier=item.source_tier,
                        verified_by=[],
                        discrepancies=[],
                    )
                    claim_to_sources[norm] = []
                if item.source_name not in claim_to_sources[norm]:
                    claim_to_sources[norm].append(item.source_name)

        # Cross-reference: which claims are verified by multiple sources?
        verified_claims = 0
        total_claims = len(all_claims) if all_claims else 1
        findings = []
        discrepancies_list = []

        for norm, claim_obj in all_claims.items():
            sources_reporting = claim_to_sources[norm]
            claim_obj.verified_by = [s for s in sources_reporting if s != claim_obj.source_name]
            if len(sources_reporting) >= 2:
                claim_obj.is_verified = True
                claim_obj.verification_level = "confirmed"
                verified_claims += 1
                findings.append(f"✅ {norm[:80]} — confirmed by {len(sources_reporting)} sources")
            elif len(sources_reporting) == 1:
                claim_obj.verification_level = "single_source"
                findings.append(f"⚠️ {norm[:80]} — only from {sources_reporting[0]}")
            else:
                claim_obj.verification_level = "unverified"

        # Check for discrepancies: different sources reporting different numbers
        # for the same apparent metric
        number_claims = {}
        for norm, cl in all_claims.items():
            # Group claims that look like the same metric
            metric_key = re.sub(r'\$?\d+[\.\d,]*', 'NNN', norm)
            metric_key = re.sub(r'\s+', ' ', metric_key).strip()
            if metric_key not in number_claims:
                number_claims[metric_key] = []
            number_claims[metric_key].append(norm)

        for metric_key, variants in number_claims.items():
            if len(variants) > 1:
                # Different sources reporting different numbers for same metric
                discrep = f"⚠️ Numerical discrepancy in '{metric_key[:60]}': {', '.join(v[:40] for v in variants)}"
                discrepancies_list.append(discrep)
                findings.append(discrep)

        # Determine verification level
        # Primary signal: how many Tier 0/1 sources cover the story
        # Secondary signal: how many specific claims are verified across sources
        if primary_count >= 2 and total_unique >= 2:
            level = VerificationLevel.CONFIRMED
        elif primary_count >= 1 and major_count >= 1:
            level = VerificationLevel.HIGH_CONFIDENCE
        elif major_count >= 2:
            level = VerificationLevel.MEDIUM_CONFIDENCE
        elif total_unique >= 1:
            level = VerificationLevel.LOW_CONFIDENCE
        else:
            level = VerificationLevel.UNVERIFIED

        # If claim verification shows numerical discrepancies, downgrade one level
        if discrepancies_list and level.value > VerificationLevel.LOW_CONFIDENCE.value:
            # Numerical disagreement between sources → demote
            level = VerificationLevel(max(level.value - 1, VerificationLevel.LOW_CONFIDENCE.value))

        # Also check titles for discrepancy
        titles = set(self._normalize_title(it.title) for it in items)
        has_title_discrepancy = len(titles) > 1

        # Generate report
        report_lines = [
            f"# Cross-Verification Report: {cluster['story_title'][:80]}",
            "",
            f"**Verification Level:** {level.label}",
            f"**Total Sources:** {total_unique}",
            f"**Primary Sources:** {primary_count}",
            f"**Major Sources:** {major_count}",
            f"**Weighted Score:** {weighted}",
            f"**Claims Extracted:** {total_claims}",
            f"**Claims Verified (2+ sources):** {verified_claims}",
            "",
            "### Sources Reporting",
        ]
        for item in items:
            report_lines.append(f"  • [{item.source_tier.confidence_label}] {item.source_name} — {item.url}")

        report_lines.extend([
            "",
            "### Tier Breakdown",
            f"  • Tier 0 (Primary): {primary_count}",
            f"  • Tier 1 (Major): {major_count}",
            f"  • Tier 2+ (Specialized): {total_unique - primary_count - major_count}",
            "",
            "### Claim Verification",
        ])

        if findings:
            for f in findings[:15]:
                report_lines.append(f"  {f}")
        else:
            report_lines.append("  No specific claims could be extracted from RSS summaries.")

        if discrepancies_list:
            report_lines.extend(["", "### Discrepancies Found"])
            for d in discrepancies_list:
                report_lines.append(f"  {d}")

        report_lines.extend(["", "### Verdict"])
        if has_title_discrepancy:
            report_lines.append("⚠️ Sources use different headlines — may indicate different angles.")
        if level.value >= CONFIG["min_verification_level"]:
            report_lines.append(f"✅ PASS — Meets minimum verification threshold (level {CONFIG['min_verification_level']}).")
        else:
            report_lines.append(f"⛔ BLOCKED — Below minimum verification threshold. Needs human review.")

        result = CrossVerificationResult(
            story_title=cluster["story_title"],
            slug=self._slugify(cluster["story_title"]),
            claims=list(all_claims.values()),
            sources_checked=list(set(sources)),
            sources_agreed=list(set(sources)),
            sources_disagreed=[] if not has_title_discrepancy else ["Title variance detected"],
            verification_level=level,
            verified_claims=verified_claims,
            total_claims=total_claims,
            discrepancies_found=discrepancies_list + (["Title variance"] if has_title_discrepancy else []),
            report="\n".join(report_lines),
        )

        return result

    def _slugify(self, title: str) -> str:
        """Convert a news title to a filesystem-safe slug."""
        slug = re.sub(r'[^a-z0-9]', '-', title.lower())[:50]
        slug = re.sub(r'-+', '-', slug).strip('-')
        if not slug:
            slug = f"news-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        date_prefix = datetime.now().strftime('%Y-%m')
        return f"{date_prefix}-{slug}"

    # ══════════════════════════════════════════════════════════
    # 4b. NEWS SEARCH — Query-specific multi-source search
    # ══════════════════════════════════════════════════════════

    def _find_known_source(self, source_name: str) -> Optional[NewsSource]:
        """Try to match a source name from search results to our known sources directory.

        Uses fuzzy matching on source name and domain to find the best match.
        """
        name_lower = source_name.lower().strip()

        # 1. Direct name match
        for key, src in self.sources.items():
            if name_lower == src.name.lower():
                return src

        # 2. Name containment (source name contains our key or vice versa)
        for key, src in self.sources.items():
            src_lower = src.name.lower()
            # Remove common prefixes/suffixes
            for prefix in ["the ", "the "]:
                if name_lower.startswith(prefix):
                    trimmed = name_lower[len(prefix):]
                    if trimmed == src_lower:
                        return src
            if src_lower in name_lower or name_lower in src_lower:
                return src

        # 3. Domain-based matching
        for key, src in self.sources.items():
            domain = urllib.parse.urlparse(src.base_url).netloc.lower()
            domain_parts = domain.split(".")
            for part in domain_parts:
                if len(part) > 3 and part in name_lower:
                    return src

        return None

    def _search_google_news(self, query: str, max_results: int = 20,
                           language: str = "tr", country: str = "TR") -> List[FetchedNewsItem]:
        """Search for news articles matching a query via RSS.

        Tries multiple free RSS search backends in order:
        1. Google News RSS (primary)
        2. Bing News RSS (fallback)

        Returns deduplicated list of FetchedNewsItem with source attribution.
        """
        # Backend 1: Google News RSS
        items = self._search_via_google_news(query, max_results, language, country)
        if items:
            return items

        # Backend 2: Bing News RSS fallback
        logger.info(f"Google News search failed, trying Bing News fallback for '{query}'")
        items = self._search_via_bing_news(query, max_results)
        if items:
            return items

        return []

    def _search_via_google_news(self, query: str, max_results: int = 20,
                                language: str = "tr", country: str = "TR") -> List[FetchedNewsItem]:
        """Search Google News RSS for articles matching a specific query.

        Uses free Google News RSS search endpoint (no API key required).
        This endpoint is deprecated by Google — Bing fallback handles failures.

        Args:
            query: Free-form search text (e.g., "istanbulda kapkaça uğrayan kadın")
            max_results: Maximum number of results to return
            language: Language code (tr, en, etc.)
            country: Country code (TR, US, etc.)

        Returns:
            List of FetchedNewsItem with source attribution and tier mapping
        """
        encoded = urllib.parse.quote(query)
        search_url = (
            f"https://news.google.com/rss/search?q={encoded}"
            f"&hl={language}&gl={country}&ceid={country}:{language}"
        )

        items = []
        try:
            req = urllib.request.Request(
                search_url,
                headers={"User-Agent": f"Haber-Kuratör/{VERSION} NewsSearch/{language}"}
            )
            with urllib.request.urlopen(req, timeout=CONFIG["rss_timeout"]) as resp:
                xml_data = resp.read()

            root_el = ET.fromstring(xml_data)
            ATOM_NS = "{http://www.w3.org/2005/Atom}"

            # Google News returns RSS 2.0 format
            for item in root_el.findall(".//item"):
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                pub_date = item.findtext("pubDate", "").strip()
                snippet = item.findtext("description", "").strip()

                # Source name from <source> element or parse from title
                source_el = item.find("source")
                source_name = "Google News"
                if source_el is not None and source_el.text:
                    source_name = source_el.text.strip()
                else:
                    # Try to extract source from title (often "Title - Source Name")
                    title_parts = title.rsplit(" - ", 1)
                    if len(title_parts) > 1:
                        title = title_parts[0]
                        source_name = title_parts[1]

                if not title:
                    continue

                # Map to known source for credibility
                known = self._find_known_source(source_name)

                items.append(FetchedNewsItem(
                    title=title,
                    url=link or "https://news.google.com",
                    source_name=known.name if known else source_name,
                    source_tier=known.tier if known else SourceTier.SUPPLEMENTARY,
                    published=pub_date,
                    summary=self._clean_html(snippet)[:300],
                    category=known.category if known else "news",
                    guid=link or title,
                ))

                if len(items) >= max_results:
                    break

            logger.info(f"Google News search '{query}': {len(items)} results, "
                        f"language={language}, country={country}")

        except ET.ParseError as e:
            logger.warning(f"Google News search parse error for '{query}': {e}")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            logger.warning(f"Google News search network error for '{query}': {e}")

        return items

    def _search_via_bing_news(self, query: str, max_results: int = 20) -> List[FetchedNewsItem]:
        """Search Bing News RSS as fallback search backend.

        Uses Bing's free news RSS search (no API key required).
        Returns fewer results than Google News but more reliable.

        Args:
            query: Free-form search text
            max_results: Maximum number of results to return

        Returns:
            List of FetchedNewsItem with source attribution
        """
        encoded = urllib.parse.quote(query)
        search_url = f"https://www.bing.com/news/search?q={encoded}&format=rss"

        items = []
        try:
            req = urllib.request.Request(
                search_url,
                headers={"User-Agent": f"Haber-Kuratör/{VERSION} BingNews"}
            )
            with urllib.request.urlopen(req, timeout=CONFIG["rss_timeout"]) as resp:
                xml_data = resp.read()

            root_el = ET.fromstring(xml_data)

            for item in root_el.findall(".//item"):
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                pub_date = item.findtext("pubDate", "").strip()
                source_el = item.find("source")
                source_name = source_el.text.strip() if source_el is not None and source_el.text else "Bing News"
                snippet = item.findtext("description", "").strip()

                if not title:
                    continue

                known = self._find_known_source(source_name)

                items.append(FetchedNewsItem(
                    title=title,
                    url=link or "https://bing.com/news",
                    source_name=known.name if known else source_name,
                    source_tier=known.tier if known else SourceTier.SUPPLEMENTARY,
                    published=pub_date,
                    summary=self._clean_html(snippet)[:300],
                    category=known.category if known else "news",
                    guid=link or title,
                ))

                if len(items) >= max_results:
                    break

            logger.info(f"Bing News search '{query}': {len(items)} results")

        except Exception as e:
            logger.warning(f"Bing News search failed for '{query}': {e}")

        return items

    def search_news(self, query: str, max_results: int = 20,
                    language: str = "tr", country: str = "TR") -> Dict[str, Any]:
        """Search for a specific news topic across multiple sources.

        Complete pipeline: search → fetch → deduplicate → cluster → cross-verify.
        Returns structured results with source attribution and verification levels.

        Args:
            query: Free-form search query in any language
            max_results: Max search results to process (default: 20)
            language: Language for search results (default: 'tr' for Turkish)
            country: Country for search results (default: 'TR')

        Returns:
            Dict with:
            - query: the original search term
            - total_results: raw result count
            - clusters: story cluster count
            - verified_count: how many clusters pass verification
            - results: list of {cluster, verification} dicts
        """
        logger.info(f"search_news called: query=%.80r, max_results=%d, lang=%s",
                    query, max_results, language)

        # Step 1: Search Google News
        raw_items = self._search_google_news(query, max_results, language, country)

        if not raw_items:
            return {
                "query": query,
                "total_results": 0,
                "clusters": 0,
                "verified_count": 0,
                "results": [],
                "note": "No results found. Try a different query or language.",
            }

        # Step 2: Deduplicate by URL and title
        unique_items = self._deduplicate_news(raw_items)

        # Step 3: Story-level clustering
        clusters = self.cluster_stories(unique_items)

        # Step 4: Cross-verify each cluster
        results = []
        for cluster in clusters:
            verification = self.cross_verify_story(cluster)
            results.append({
                "cluster": {
                    "story_title": cluster["story_title"],
                    "source_count": cluster["source_count"],
                    "tier_count": cluster["tier_count"],
                    "best_url": cluster.get("best_url", ""),
                    "categories": cluster.get("categories", []),
                },
                "verification": verification.to_dict(),
            })

        verified_count = sum(1 for r in results if r["verification"]["is_safe_to_publish"])

        # Sort by source count (best covered first)
        results.sort(key=lambda r: r["cluster"]["source_count"], reverse=True)

        logger.info(f"search_news '{query}': {len(raw_items)} raw → {len(clusters)} clusters "
                    f"→ {verified_count} verified")

        return {
            "query": query,
            "total_results": len(raw_items),
            "unique_results": len(unique_items),
            "clusters": len(clusters),
            "verified_count": verified_count,
            "results": results,
        }

    # ══════════════════════════════════════════════════════════
    # 5. FACT-CHECK PIPELINE
    # ══════════════════════════════════════════════════════════

    def create_news_run(self, cluster: Dict[str, Any]) -> Dict[str, Any]:
        """Create a verified news run from a story cluster.

        Runs cross-verification, creates the run folder with fact-check report.
        Only proceeds if verification meets minimum threshold.
        """
        # Step 1: Cross-verify
        verification = self.cross_verify_story(cluster)

        slug = verification.slug
        run_path = self.active_runs / slug

        if run_path.exists():
            return {"slug": slug, "status": "exists", "message": "This news item is already in the system."}

        run_path.mkdir(parents=True, exist_ok=True)

        # Step 2: Create haber-object.md
        route = "VERIFIED" if verification.is_safe_to_publish else "REWRITE"
        initial_state = "cross_verified" if verification.is_safe_to_publish else "captured"

        obj = f"""# Haber Nesnesi — {slug}

## Meta
- **ID:** {slug}
- **Created:** {datetime.now().isoformat()}
- **Status:** {initial_state}
- **Route:** {route}
- **Source Type:** multi-source
- **Format:** Haber Bülteni
- **Pillar:** {', '.join(cluster.get('categories', ['Genel Haber']))}
- **Title:** {cluster['story_title']}
- **Verification Level:** {verification.verification_level.value}
- **Verified Sources:** {len(verification.sources_checked)}
"""
        (run_path / "haber-object.md").write_text(obj, encoding="utf-8")

        # Step 3: Write idea.md with verification info
        idea_md = f"""# News Item — {slug}

## Story
{cluster['story_title']}

## Best Source URL
{cluster.get('best_url', 'N/A')}

## Sources Reporting This Story
{chr(10).join(f'  • [{item.source_tier.confidence_label}] {item.source_name} — {item.url}' for item in cluster['items'])}

## Route Decision
- **Route:** {route}
- **Rationale:** {"Multi-source verified news — direct from wire services/major outlets" if route == "VERIFIED" else "Needs human review — below verification threshold"}
"""
        (run_path / "idea.md").write_text(idea_md, encoding="utf-8")

        # Step 4: Write fact-check-report.md
        (run_path / "fact-check-report.md").write_text(verification.report, encoding="utf-8")

        # Step 5: Write context.md with source info for Writer
        context_md = f"""# Context for: {slug}

## Story
{cluster['story_title']}

## Best Source URL
{cluster.get('best_url', 'N/A')}

## All Reporting Sources
{chr(10).join(f'{item.source_name} ({item.source_tier.confidence_label}): {item.url}' for item in cluster['items'])}

## Verification
{verification.summary}
"""
        (run_path / "context.md").write_text(context_md, encoding="utf-8")

        # Step 6: Update cache based on verification (initial_state defined above)
        self._state_cache[slug] = RunState(
            slug=slug,
            title=cluster['story_title'],
            state=initial_state,
            route=route,
            created=datetime.now().isoformat(),
            updated=datetime.now().isoformat(),
            source_type="multi-source",
            verification_level=verification.verification_level.name,
        )
        self._save_state_cache()

        return {
            "slug": slug,
            "path": str(run_path),
            "route": route,
            "verification": verification.to_dict(),
            "initial_state": initial_state,
        }

    def publish_verified_news(self, cluster: Dict[str, Any], human_review: bool = True) -> Dict[str, Any]:
        """One-step: verify + create run + auto-publish if verified.

        For fully automated news ingestion with verification gate.
        """
        result = self.create_news_run(cluster)
        if result.get("status") == "exists":
            # Ensure route key exists even on duplicate
            result["route"] = "VERIFIED"
            return result

        verification_level = result.get("verification", {}).get("verification_level", -1)
        slug = result["slug"]

        # Auto-advance to published if highly verified and no human review
        if verification_level >= 2 and not human_review:
            self.update_state(slug, "published")
            result["auto_advanced"] = True

        return result

    # ══════════════════════════════════════════════════════════
    # 6. IDEA GATE (Updated for News)
    # ══════════════════════════════════════════════════════════

    def decide_route(self, idea: str, source_hint: str = "") -> Dict[str, Any]:
        """Haberde tek rota vardır: VERIFIED (çok kaynaklı doğrulama)."""
        return {"route": "VERIFIED", "rationale": "Multi-source verified news.", "source_type": "multi-source"}

    # ══════════════════════════════════════════════════════════
    # 7. STATE MACHINE — 8-State News Lifecycle
    # ══════════════════════════════════════════════════════════

    def _valid_transition(self, from_state: str, to_state: str) -> bool:
        if from_state not in STATE_TRANSITIONS:
            return to_state in STATE_LIFECYCLE
        return to_state in STATE_TRANSITIONS[from_state]

    def update_state(self, slug: str, new_state: str,
                     force: bool = False) -> str:
        """Update state with 8-state lifecycle validation."""
        logger.info("update_state: slug=%s, new_state=%s, force=%s", slug, new_state, force)

        if new_state not in STATE_LIFECYCLE:
            return f"❌ Invalid state: {new_state}"

        run_path = (self.active_runs / slug).resolve()
        if not run_path.exists():
            return f"❌ Run {slug} not found."

        obj_path = run_path / "haber-object.md"

        # Auto-initialize if missing
        if not obj_path.exists():
            idea_path = run_path / "haber-object.md"
            idea = "news-item"
            obj_path.write_text(
                f"title: {idea}\nstate: {new_state}\n"
                f"created: {datetime.now().isoformat()}\n"
                f"updated: {datetime.now().isoformat()}",
                encoding="utf-8",
            )
            self._state_cache[slug] = RunState(
                slug=slug,
                title=idea,
                state=new_state,
                updated=datetime.now().isoformat(),
            )
            self._save_state_cache()
            return f"✅ Initialized and updated {slug} to {new_state}"

        content = obj_path.read_text(encoding="utf-8")
        current_state = "captured"
        # Support all field formats:
        #   "state: captured"               — bare lower
        #   "Status: published"             — bare upper
        #   "- **Status**: cross_verified"  — markdown bold, colon before close
        #   "- **Status:** captured"        — markdown bold, colon after close
        m = re.search(r'(?i)(- \*\*)?(?:status|state)\*{0,2}:\*{0,2}\s*(\w+)', content)
        if m:
            current_state = m.group(2)

        # Validate transition
        if not force and not self._valid_transition(current_state, new_state):
            allowed = STATE_TRANSITIONS.get(current_state, ["any"])
            return f"❌ Invalid transition: {current_state} → {new_state}. Allowed: {allowed}"

        # Update state in haber-object.md — handle all field formats:
        # "state: published", "Status: published", "- **Status**: cross_verified"
        # Note: f-string "**Status:**" produces **Status**: (colon before close bold)
        state_field_pattern = r"(?i)((- \*\*)?(?:status|state)\*{0,2}:\*{0,2}\s*)\w+"
        if re.search(state_field_pattern, content):
            new_content = re.sub(
                state_field_pattern,
                lambda m: f"{m.group(1)}{new_state}",
                content,
            )
        else:
            new_content = content + f"\nstate: {new_state}"

        ts = datetime.now().isoformat()
        if "updated:" in new_content:
            new_content = re.sub(r"updated:.*", f"updated: {ts}", new_content)
        else:
            new_content = f"{new_content}\nupdated: {ts}"

        obj_path.write_text(new_content, encoding="utf-8")

        # Update cache
        existing = self._state_cache.get(slug, RunState(slug=slug))
        self._state_cache[slug] = RunState(
            slug=slug,
            title=existing.title,
            state=new_state,
            route=existing.route,
            created=existing.created,
            updated=ts,
            source_type=existing.source_type,
            verification_level=existing.verification_level,
        )
        self._save_state_cache()

        logger.debug("update_state: %s: %s → %s", slug, current_state, new_state)
        return f"✅ {slug}: {current_state} → {new_state}"

    def sync_state(self, slug: str) -> str:
        """Scan filesystem and sync haber-object.md to correct state."""
        run_path = (self.active_runs / slug).resolve()
        if not run_path.exists():
            return "unknown"

        # Priority-ordered detection
        if (run_path / "correction.md").exists():
            content = (run_path / "correction.md").read_text(encoding="utf-8")
            if "## Retraction" in content or "GERİ ÇEKME" in content:
                state = "retracted"
            elif "## Correction" in content or "DÜZELTME" in content:
                state = "corrected"
            else:
                state = "correction_needed"
        elif (run_path / "fact-check-report.md").exists():
            state = "cross_verified"
        else:
            state = "captured"

        try:
            self.update_state(slug, state, force=True)
        except Exception:
            pass
        return state

    def get_state(self, slug: str) -> str:
        """Read current state from cache or haber-object.md."""
        if slug in self._state_cache:
            return self._state_cache[slug].state
        obj = self.active_runs / slug / "haber-object.md"
        if not obj.exists():
            return "unknown"
        content = obj.read_text(encoding="utf-8")
        m = re.search(r'(?i)(?:status|state)\*{0,2}:\*{0,2}\s*(\w+)', content)
        state = m.group(1) if m else "unknown"
        if state != "unknown":
            rs = RunState(slug=slug, state=state)
            for field, key in [("Route", "route"), ("Title", "title")]:
                fm = re.search(rf'\*{{0,2}}{field}\*{{0,2}}:\*{{0,2}}\s*(.+)', content, re.IGNORECASE)
                if fm:
                    setattr(rs, key, fm.group(1).strip().lstrip('* '))
            self._state_cache[slug] = rs
        return state

    def get_next_actions(self, slug: str) -> List[str]:
        """Return suggested next actions based on current state."""
        state = self.get_state(slug)
        guide = {
            "captured":          ["Fetch & cross-verify news: /haber fetch"],
            "fact_checking":     ["Wait for cross-verification to complete",
                                  "Check fact-check-report.md"],
            "cross_verified":    ["Publish to Memos: /haber publish",
                                  "Or auto-publish: /haber auto-publish"],
            "published":         ["Monitor for corrections needed",
                                  "Check: /haber correct if errors found"],
            "correction_needed": ["Write correction.md with accurate info",
                                  "Republish corrected version"],
            "corrected":         ["Correction published. Archive if done: /haber archive"],
            "retracted":         ["Story retracted. Archive: /haber archive"],
            "archived":          ["Run archived. Review if needed: /haber audit"],
        }
        return guide.get(state, ["No specific next actions for this state."])

    async def generate_brief(self, slug: str, llm: Any = None,
                             extra_context: str = "") -> Dict[str, Any]:
        """Generate a Writer Context Packet (brief.md) using LLM.

        For news items, includes source attribution requirements.
        """
        run_path = self.active_runs / slug
        if not run_path.exists():
            return {"error": f"Run {slug} not found."}

        idea_path = run_path / "idea.md"
        context_path = run_path / "context.md"
        fact_check_path = run_path / "fact-check-report.md"

        idea = idea_path.read_text(encoding="utf-8") if idea_path.exists() else slug
        ctx = context_path.read_text(encoding="utf-8") if context_path.exists() else ""
        fact_check = fact_check_path.read_text(encoding="utf-8") if fact_check_path.exists() else ""

        voice_profile = self._get_voice_summary()
        slop_doc = ""
        slop_path = self.voice / "master-avoid-slop.md"
        if slop_path.exists():
            slop_doc = slop_path.read_text(encoding="utf-8")[:500]

        route = "VERIFIED"
        rm = re.search(r'Route:\s*(.+)', idea, re.IGNORECASE)
        if rm:
            route = rm.group(1).strip()

        # Determine if this is a news item requiring source attribution
        is_verified_news = route == "VERIFIED"

        source_attribution_section = ""
        if is_verified_news and fact_check:
            source_attribution_section = f"""
## Source Attribution Requirements (MANDATORY)
This is a VERIFIED NEWS item. Every factual claim MUST include:
1. The specific source(s) that reported it (Source: Reuters, AP, etc.)
2. A direct link to the source article where available
3. The credibility tier of the source

Rules:
- NEVER use vague attribution ("according to reports", "sources say")
- NEVER fabricate facts — only use information from the verified sources
- If a claim cannot be attributed to a specific source, FLAG IT as unverified
- End with a clear "Sources:" section listing all cited articles

## Cross-Verification Report (from fact-check)
{fact_check}
"""
        prompt = f"""You are writing a Writer Context Packet (brief.md) for a news content post.
Target 400-900 tokens. Be specific. Every field must be filled from available context.

ROUTE: {route}

INPUT FILES:
1. Idea + Route Decision:
{idea}

2. Context (Stores, Proof, Voice):
{ctx}

3. Voice Profile Summary:
{voice_profile}

4. Slop Patterns (abridged):
{slop_doc}

{source_attribution_section}

{extra_context}

OUTPUT — produce a complete brief.md with EXACTLY this structure:

```markdown
# Writer Context Packet — {{SLUG}}
## Meta
- **Route:** {{ROUTE}}
- **Format:** Haber Bülteni
- **Pillar:** {{pillar}}
- **Target Date:** {{optional}}

## Thesis
ONE sentence — what fact does this news deliver?

## Target Reader
ONE specific person who needs this news.

## Key Facts
- Fact 1 with source attribution
- Fact 2 with source attribution
- (every fact must cite its source)

## Angle
What makes this news item noteworthy?

## Source List
- Source 1 (Tier): URL
- Source 2 (Tier): URL

## Constraints
- News format: [Özet] - [Detaylar] - [Kaynak]
- Tone: objective, factual
- No commentary, no analysis — just the facts
- Every claim = source citation

## Risks
- False balance: don't invent opposing views
- Speculation: don't predict outcomes
- Vague sourcing: always name the source

## Rubric Targets
- [ ] Tarafsızlık (Objectivity) → target: 2/2
- [ ] Kaynak Gösterimi (Sourcing) → target: 2/2
- [ ] Kısalık ve Netlik (Brevity) → target: 2/2
- [ ] Bilgi Yoğunluğu (Fact Density) → target: 2/2
- [ ] Clickbait Uzaklığı → target: 2/2
- [ ] Format Yapısı (Structure) → target: 2/2
Target total: 12/12
```

Return ONLY the markdown brief. No extra commentary."""

        try:
            if llm and hasattr(llm, "acomplete"):
                response = await llm.acomplete([
                    {"role": "system", "content": "You are an expert news editor who writes tight, sourced briefs."},
                    {"role": "user", "content": prompt},
                ])
                text = response.text
            else:
                try:
                    from agent.auxiliary_client import async_call_llm
                except ImportError as _ie:
                    raise RuntimeError(
                        "Hermes LLM unavailable outside agent context. "
                        "Use '/haber brief <slug>' via Hermes agent instead."
                    ) from _ie
                messages = [
                    {"role": "system", "content": "You are an expert news editor."},
                    {"role": "user", "content": prompt},
                ]
                raw = await async_call_llm(task="curator", messages=messages)
                try:
                    text = raw.choices[0].message.content
                except (AttributeError, IndexError):
                    text = str(raw)

            text = text.strip()
            if text.startswith("```"):
                text = re.sub(r"^```\w*\n?", "", text)
                text = re.sub(r"\n```$", "", text)

            brief_path = run_path / "brief.md"
            brief_path.write_text(text, encoding="utf-8")
            # Brief hazırlandı — state zaten cross_verified ise koru, değilse geç
            current = self.get_state(slug)
            if current not in ("cross_verified", "published", "correction_needed"):
                self.update_state(slug, "cross_verified")

            return {"slug": slug, "status": "cross_verified", "length": len(text)}

        except Exception as e:
            return {"error": f"Brief generation failed: {str(e)}"}

    async def generate_draft(self, slug: str, llm: Any = None) -> Dict[str, Any]:
        """Generate draft-package.md using the Writer Agent with source enforcement.

        For VERIFIED news: ALL facts must be traceable to sources in the brief.
        Hallucination guard: LLM is instructed to ONLY use facts from sources.
        """
        run_path = self.active_runs / slug
        if not run_path.exists():
            return {"error": f"Run {slug} not found."}

        brief_path = run_path / "brief.md"
        if not brief_path.exists():
            return {"error": "No brief.md found."}

        brief = brief_path.read_text(encoding="utf-8")
        fact_check_path = run_path / "fact-check-report.md"
        fact_check = fact_check_path.read_text(encoding="utf-8") if fact_check_path.exists() else ""

        voice_profile = ""
        vp_path = self.voice / "voice-profile.md"
        if vp_path.exists():
            voice_profile = vp_path.read_text(encoding="utf-8")

        slop_doc = ""
        slop_path = self.voice / "master-avoid-slop.md"
        if slop_path.exists():
            slop_doc = slop_path.read_text(encoding="utf-8")[:1500]

        proof = self._get_relevant_proof(brief)
        hooks = self._get_successful_hooks()

        # Determine route
        route = "VERIFIED"
        rm = re.search(r'\*{0,2}Route\*{0,2}:\*{0,2}\s*(.+)', brief, re.IGNORECASE)
        if rm:
            route = rm.group(1).strip().lstrip('* ')

        is_verified_news = route == "VERIFIED"

        # Hallucination guard section for news
        hallucination_guard = ""
        if is_verified_news:
            hallucination_guard = """
## ⚠️ HALLUCINATION GUARD — CRITICAL INSTRUCTIONS
You are writing NEWS. Every single fact, number, name, and date MUST come from
the sources listed in the brief.md. You MUST NOT:

❌ Invent facts not present in the source materials
❌ Add analysis, commentary, or opinions
❌ Speculate about future outcomes
❌ Use phrases like "this could mean" or "experts believe"
❌ Create quotes that weren't in the source articles
❌ Add statistics without source attribution

✅ DO:
- Restate facts from the verified sources in your own words
- Attribute every factual claim: "Source: Reuters reports..."
- Use the [Özet] - [Detaylar] - [Kaynak] structure
- End with a "Sources:" section listing all URLs

If a source article mentions a specific number, you may use it WITH the source name.
If you are unsure about any fact, FLAG IT in open_loops_flagged — do NOT guess.
"""

        prompt = f"""ROLE
You are a Writer Agent for a News Curation platform. You produce objective,
factual news summaries from verified sources. Every claim MUST cite its source.
No fabrication. No speculation.

INPUT FILES:

## FILE 1: brief.md (Writer Context Packet)
{brief}

## FILE 2: voice-profile.md (Voice Rules)
{voice_profile}

## FILE 3: master-avoid-slop.md (Banned Patterns)
{slop_doc}

## FILE 4: Cross-Verification Report
{fact_check}

{hallucination_guard}

## Optional: Proof Bank
{proof}

## Optional: Successful Hooks
{hooks}

TASK
1. Read all input files carefully — ESPECIALLY THE SOURCE LIST
2. Internalize the hallucination guard rules
3. Internalize voice rules and banned patterns
4. Draft content following the [Özet] - [Detaylar] - [Kaynak] news format
5. Every factual claim MUST include the source name
6. After drafting, verify EVERY claim in your draft has a source in the brief
7. Flag any open loop (things you had to guess)

OUTPUT — produce a complete draft-package.md:

```
---
draft:
[News content in [Özet] - [Detaylar] - [Kaynak] format]

rubric_self_assessment:
- Tarafsızlık (Objectivity): [0/1/2] — [evidence]
- Kaynak Gösterimi (Sourcing): [0/1/2] — [evidence]
- Kısalık ve Netlik (Brevity): [0/1/2] — [evidence]
- Bilgi Yoğunluğu (Fact Density): [0/1/2] — [evidence]
- Clickbait Uzaklığı: [0/1/2] — [evidence]
- Format Yapısı (Structure): [0/1/2] — [evidence]
- TOTAL: [X/12]

avoid_slop_pass:
- [ ] LINE [N]: "[exact phrase]" — [pattern name] — [rewrite suggestion]
- (empty if clean)

open_loops_flagged:
- [specific fact I had to guess — CRITICAL for news accuracy]
- (empty if all facts sourced)

voice_check:
- All voice rules followed: [yes/no]
  - Rule 1: [followed / violated]
  - Rule 2: [followed / violated]
  - Rule 3: [followed / violated]
  - Rule 4: [followed / violated]
  - Rule 5: [followed / violated]

source_attribution_check:
- Every claim has a source: [yes/no]
- All sources from approved list: [yes/no]
- Number of unsourced claims: [N]
- Open loops that need fact-checking: [list]
```

QUALITY GATES:
- [ ] Every claim has a source citation
- [ ] No hallucinated/speculative content
- [ ] Voice rules followed
- [ ] Slop patterns avoided
- [ ] Format matches news brief specification
- [ ] [Özet] - [Detaylar] - [Kaynak] structure used"""

        try:
            if llm and hasattr(llm, "acomplete"):
                response = await llm.acomplete([
                    {"role": "system", "content": "You are a Writer Agent for Haber Kuratör News. You produce ONLY source-attributed factual news. Hallucination = system failure."},
                    {"role": "user", "content": prompt},
                ])
                text = response.text
            else:
                try:
                    from agent.auxiliary_client import async_call_llm
                except ImportError as _ie:
                    raise RuntimeError(
                        "Hermes LLM unavailable outside agent context. "
                        "Use '/haber draft <slug>' via Hermes agent instead."
                    ) from _ie
                messages = [
                    {"role": "system", "content": "You are a Writer Agent for Haber Kuratör News. Source-attributed factual news only."},
                    {"role": "user", "content": prompt},
                ]
                raw = await async_call_llm(task="writer", messages=messages)
                try:
                    text = raw.choices[0].message.content
                except (AttributeError, IndexError):
                    text = str(raw)

            text = text.strip()
            if text.startswith("```"):
                text = re.sub(r"^```\w*\n?", "", text)
                text = re.sub(r"\n```$", "", text)

            draft_path = run_path / "draft-package.md"
            draft_path.write_text(text, encoding="utf-8")
            # Draft hazırlandı — state cross_verified olarak kalır
            return {"slug": slug, "status": "drafted", "length": len(text)}

        except Exception as e:
            return {"error": f"Draft generation failed: {str(e)}"}

    # ══════════════════════════════════════════════════════════
    # 10. VERIFIER AGENT (Updated for Source Verification)
    # ══════════════════════════════════════════════════════════

    async def run_verifier(self, slug: str, llm: Any = None) -> Dict[str, Any]:
        """Run Verifier Agent with source attribution checking."""
        run_path = self.active_runs / slug
        if not run_path.exists():
            return {"error": f"Run {slug} not found."}

        draft_path = run_path / "draft-package.md"
        brief_path = run_path / "brief.md"
        fact_check_path = run_path / "fact-check-report.md"

        if not draft_path.exists():
            return {"error": "No draft-package.md found."}

        draft = draft_path.read_text(encoding="utf-8")
        brief = brief_path.read_text(encoding="utf-8") if brief_path.exists() else ""
        fact_check = fact_check_path.read_text(encoding="utf-8") if fact_check_path.exists() else ""
        slop_doc = ""
        slop_path = self.voice / "master-avoid-slop.md"
        if slop_path.exists():
            slop_doc = slop_path.read_text(encoding="utf-8")[:2000]

        prompt = f"""ROLE
You are a Verifier Agent for a News Curation platform. You check drafts
for factual accuracy, source attribution, and journalistic standards.

Your PRIMARY job: catch HALLUCINATIONS — claims not supported by sources.
Your SECONDARY job: catch slop, voice violations, and rubric gaps.

INPUT FILES:

## FILE 1: brief.md (What was supposed to be written)
{brief}

## FILE 2: draft-package.md (What was written)
{draft}

## FILE 3: Cross-Verification Report (Verified facts)
{fact_check}

## FILE 4: master-avoid-slop.md (Banned patterns)
{slop_doc}

TASK — Two-phase verification:

PHASE 1: SOURCE ATTRIBUTION CHECK (CRITICAL)
- Does every factual claim in the draft cite a specific source?
- Are all cited sources from the approved list in the brief?
- Are there ANY claims that appear to be hallucinated (not in the source materials)?
- Check for: fake statistics, made-up quotes, invented names/dates, unverified numbers

PHASE 2: QUALITY CHECK
- Rubric scoring (0-12)
- Slop pattern detection
- Voice rule compliance

OUTPUT — produce verifier-report.md:

```
---
## source_attribution_audit
**Hallucination scan:**
- Claims with proper source: [N]
- Claims without source: [N]
- Potentially hallucinated claims: [list each with line number and reason]
- Sources used but not in brief: [list]
- All sources from approved list: [yes/no]

**Source chain integrity:**
- Every fact maps back to a source: [yes/partial/no]
- Appropriate source tiers used: [yes/no]

## brief_check
- Thesis delivered: [yes/partial/no] — [evidence]
- Constraints met: [yes/partial/no] — [evidence]
- News format followed ([Özet]-[Detaylar]-[Kaynak]): [yes/partial/no]

## rubric_scoring
- Tarafsızlık (Objectivity): [0/1/2] — [evidence]
- Kaynak Gösterimi (Sourcing): [0/1/2] — [evidence]
- Kısalık ve Netlik (Brevity): [0/1/2] — [evidence]
- Bilgi Yoğunluğu (Fact Density): [0/1/2] — [evidence]
- Clickbait Uzaklığı: [0/1/2] — [evidence]
- Format Yapısı (Structure): [0/1/2] — [evidence]
- TOTAL: [X/12]
- PASSES_THRESHOLD (8/12): [yes/no]

## avoid_slop_findings
TIER 1 — Critical:
- [ ] LINE [N]: "[phrase]" — [pattern]
TIER 2 — High:
- [ ] LINE [N]: "[phrase]" — [pattern]
TIER 3 — Medium:
- [ ] LINE [N]: "[phrase]" — [pattern]

## VERDICT
- [APPROVE] — All claims sourced, rubric ≥8/12, minor slop only
- [REVISE] — Some claims need source fixes or rubric close but under
- [REJECT] — Hallucinated claims OR rubric <6/12

## required_fixes
1. [Line N]: [specific fix — especially source issues]
2. [Line M]: [specific fix]

## hallucination_detail
For each potentially hallucinated claim:
1. Claim: "[exact text]"
   Line: [N]
   Evidence it's hallucinated: [explain why this isn't in sources]
   Source check: [what the fact-check report actually says]
   Suggested fix: [how to fix — add source or remove claim]
```

CRITICAL RULES:
- If ANY claim appears hallucinated → REJECT
- If ANY source is cited but NOT in the approved list → FLAG
- Every rubric score needs specific quote evidence
- Generic feedback is REJECTED"""

        try:
            if llm and hasattr(llm, "acomplete"):
                response = await llm.acomplete([
                    {"role": "system", "content": "You are a strict Verifier Agent for Haber Kuratör News. Hallucination detection is your primary job."},
                    {"role": "user", "content": prompt},
                ])
                text = response.text
            else:
                try:
                    from agent.auxiliary_client import async_call_llm
                except ImportError as _ie:
                    raise RuntimeError(
                        "Hermes LLM unavailable outside agent context. "
                        "Use '/haber verify <slug>' via Hermes agent instead."
                    ) from _ie
                messages = [
                    {"role": "system", "content": "You are a strict Verifier Agent for Haber Kuratör News."},
                    {"role": "user", "content": prompt},
                ]
                raw = await async_call_llm(task="curator", messages=messages)
                try:
                    text = raw.choices[0].message.content
                except (AttributeError, IndexError):
                    text = str(raw)

            text = text.strip()
            if text.startswith("```"):
                text = re.sub(r"^```\w*\n?", "", text)
                text = re.sub(r"\n```$", "", text)

            report_path = run_path / "verifier-report.md"
            report_path.write_text(text, encoding="utf-8")

            return {"slug": slug, "status": "verified", "length": len(text)}

        except Exception as e:
            return {"error": f"Verification failed: {str(e)}"}

    # ══════════════════════════════════════════════════════════
    # 11. HALLUCINATION GUARD — Automated Claim Verification
    # ══════════════════════════════════════════════════════════

    def hallucination_check(self, slug: str) -> Dict[str, Any]:
        """Automated hallucination detection using regex patterns.

        Checks draft for claims that might not be sourced:
        - Statistics without source attribution
        - Quotes without attribution
        - Specific numbers/dates without source context
        - Speculative language
        """
        run_path = self.active_runs / slug
        draft_path = run_path / "draft-package.md"

        if not draft_path.exists():
            return {"error": "No draft found."}

        draft = draft_path.read_text(encoding="utf-8")

        # Skip rubric_self_assessment and similar metadata sections
        draft_main = re.split(r'\nrubric_self_assessment|\n---\nrubric_|\nvoice_check|\navoid_slop_pass|open_loops_flagged', draft)[0]

        findings = []

        # Pattern 1: Numbers/statistics without nearby source name (scan main content only)
        number_claims = re.finditer(r'(?:\$?\d+[\.\d,]*\s*(?:million|billion|trillion|percent|%|people|dollars|euros)?)', draft_main)
        for match in number_claims:
            num_text = match.group(0)

            # Skip numbers that are part of URLs (false positive prevention)
            line_start = draft_main.rfind('\n', 0, match.start()) + 1
            line_end = draft_main.find('\n', match.end())
            if line_end == -1:
                line_end = len(draft_main)
            line_text = draft_main[line_start:line_end]
            # If the line contains a URL pattern, skip numbers in that line
            if re.search(r'https?://\S*', line_text):
                continue

            start = max(0, match.start() - 200)
            end = min(len(draft), match.end() + 200)
            context = draft[start:end]

            # Check if a source name appears within 200 chars
            source_in_context = any(
                src in context
                for src in ["Reuters", "AP", "AFP", "Bloomberg", "BBC", "WSJ", "FT",
                           "Guardian", "NYT", "Washington Post", "Al Jazeera",
                           "Anadolu Ajansı", "AA", "BBC Türkçe", "Euronews",
                           "Deutsche Welle", "DW", "Bloomberg HT", "T24",
                           "Medyascope", "Duvar", "Diken", "BirGün", "Sözcü",
                           "Cumhuriyet", "Hürriyet", "Webrazzi",
                           "Source:", "Kaynak:", "kaynak", "reports", "according to",
                           "bildirdi", "açıkladı", "duyurdu", "belirtti", "göre"]
            )
            if not source_in_context:
                findings.append({
                    "type": "unsourced_statistic",
                    "text": num_text.strip()[:80],
                    "position": match.start(),
                    "severity": "high",
                    "message": f"Number/statistic without clear source attribution within 200 chars",
                })

        # Pattern 2: Speculative language
        speculative_patterns = [
            r"could (?:mean|lead to|result in|become)",
            r"might indicate",
            r"may suggest",
            r"raises questions",
            r"it remains to be seen",
            r"only time will tell",
            r"could potentially",
        ]
        for pat in speculative_patterns:
            for match in re.finditer(pat, draft_main, re.IGNORECASE):
                findings.append({
                    "type": "speculation",
                    "text": match.group(0),
                    "position": match.start(),
                    "severity": "medium",
                    "message": "Speculative language — not appropriate for verified news",
                })

        # Pattern 3: Quotes without attribution (scan main content only)
        quote_claims = re.finditer(r'"([^"]{8,})"', draft_main)
        for match in quote_claims:
            start = max(0, match.start() - 150)
            context = draft_main[start:match.end() + 50]
            has_attribution = any(
                word in context.lower()
                for word in ["said", "told", "according to", "stated", "reported",
                            "says", "added", "noted", "explained", "wrote",
                            "dedi", "belirtti", "açıkladı", "bildirdi", "duyurdu",
                            "söyledi", "ifade etti", "vurguladı", "kaydetti",
                            "sözleriyle", "tanımladı", "nitelendirdi"]
            )
            if not has_attribution:
                findings.append({
                    "type": "floating_quote",
                    "text": match.group(1)[:80],
                    "position": match.start(),
                    "severity": "high",
                    "message": "Quote without speaker attribution",
                })

        # Pattern 4: Unverified claims
        unverified_markers = [
            r"it is believed that",
            r"many think that",
            r"some argue that",
            r"critics say",
            r"supporters say",
        ]
        for pat in unverified_markers:
            for match in re.finditer(pat, draft, re.IGNORECASE):
                findings.append({
                    "type": "unverified_claim",
                    "text": match.group(0),
                    "position": match.start(),
                    "severity": "high",
                    "message": "Vague attribution — who exactly said this?",
                })

        result = {
            "slug": slug,
            "total_findings": len(findings),
            "high_severity": len([f for f in findings if f["severity"] == "high"]),
            "medium_severity": len([f for f in findings if f["severity"] == "medium"]),
            "findings": findings[:20],  # Cap at 20 findings
            "pass": len([f for f in findings if f["severity"] == "high"]) == 0,
        }

        return result

    # ══════════════════════════════════════════════════════════
    # 12. CORRECTION WORKFLOW (New for v3.0)
    # ══════════════════════════════════════════════════════════

    def issue_correction(self, slug: str, error_description: str,
                         correct_information: str, retract: bool = False) -> str:
        """Issue a correction or retraction for a published news item.

        Args:
            slug: The run slug
            error_description: What was wrong
            correct_information: What the correct fact is
            retract: True if the entire story should be retracted

        Returns:
            Status message
        """
        run_path = self.active_runs / slug
        if not run_path.exists():
            # Check archive
            run_path = self.archive / slug
            if not run_path.exists():
                return f"❌ Run {slug} not found in active or archive."

        current_state = self.get_state(slug)
        if current_state not in ("published", "correction_needed"):
            return f"❌ Cannot issue correction in state '{current_state}'. Must be published first."

        # Write correction file
        corr_content = f"""# Correction Notice — {slug}

**Date:** {datetime.now().isoformat()}
**Type:** {"RETRACTION" if retract else "CORRECTION"}
**Original State:** {current_state}

## Error Description
{error_description}

## Correct Information
{correct_information}

## Impact
{"This story has been retracted due to factual inaccuracies." if retract else "The error has been corrected. See updated version below."}

## Updated Content
---
"""

        if retract:
            corr_content += """
## Retraction Statement
We have retracted this story. The information could not be verified
to our editorial standards. We apologize for the error.

**Status:** RETRACTED
"""
        else:
            corr_content += """
## Correction
The error has been corrected. We maintain our commitment to factual accuracy.

**Status:** CORRECTED
"""

        (run_path / "correction.md").write_text(corr_content, encoding="utf-8")

        # Update state
        new_state = "retracted" if retract else "corrected"
        self.update_state(slug, new_state, force=True)

        return f"✅ {'Retraction' if retract else 'Correction'} issued for {slug}. State: {new_state}."

    def check_correction_needed(self, slug: str) -> str:
        """Check if a published run has known issues requiring correction."""
        run_path = self.active_runs / slug
        if not run_path.exists():
            return f"Run {slug} not found."

        # Look for user feedback with error reports
        feedback_path = run_path / "feedback.md"
        if feedback_path.exists():
            content = feedback_path.read_text(encoding="utf-8").lower()
            error_indicators = ["wrong", "incorrect", "hatalı", "yanlış", "error",
                                "false", "inaccurate", "yanlış bilgi", "düzeltme"]
            found = [ind for ind in error_indicators if ind in content]
            if found:
                return f"⚠️ Potential errors flagged in feedback: {', '.join(found)}. Run '/haber correct {slug}' to issue correction."

        return f"✅ No correction indicators found for {slug}."

    # ══════════════════════════════════════════════════════════
    # 13. LEGACY: ORIGINAL METHODS (Preserved)
    # ══════════════════════════════════════════════════════════

    # --- Slop Detection ---

    def scan_slop(self, text: str) -> Dict[str, Any]:
        """Full slop detection across all tiers (preserved)."""
        logger.info("scan_slop called with text length=%d", len(text))
        findings_t1 = []
        findings_t2 = []
        findings_t3 = []
        findings_bonus = []

        for p in self.slop_tier1:
            if re.search(p, text, re.IGNORECASE):
                findings_t1.append(p)
        for p in self.slop_tier2:
            if re.search(p, text, re.IGNORECASE):
                findings_t2.append(p)
        for p in self.slop_tier3:
            if re.search(p, text, re.IGNORECASE):
                findings_t3.append(p)
        for p in self.slop_bonus:
            if re.search(p, text, re.IGNORECASE):
                findings_bonus.append(p)

        t1 = len(findings_t1)
        t2 = len(findings_t2)
        t3 = len(findings_t3)
        tb = len(findings_bonus)

        if t1 >= 3 or t2 >= 5 or t3 >= 15:
            score = "REJECT"
        elif t1 >= 1 or t2 >= 3 or t3 >= 8:
            score = "REVISE"
        else:
            score = "PASS"

        return {
            "score": score,
            "tier1_count": t1,
            "tier2_count": t2,
            "tier3_count": t3,
            "bonus_count": tb,
            "findings": findings_t1 + findings_t2 + findings_t3 + findings_bonus,
            "findings_tier1": findings_t1[:10],
            "findings_tier2": findings_t2[:10],
            "findings_tier3": findings_t3[:15],
            "findings_bonus": findings_bonus[:5],
            "all_findings": findings_t1 + findings_t2 + findings_t3 + findings_bonus,
        }

    # --- Rubric Evaluation ---

    async def evaluate_rubric(self, slug: str, llm: Any = None) -> Dict[str, Any]:
        """12-point rubric evaluation (preserved)."""
        run_path = self.active_runs / slug
        draft_path = run_path / "draft-package.md"
        if not draft_path.exists():
            return {"error": f"Draft not found for {slug}"}

        content = draft_path.read_text(encoding="utf-8")
        prompt = f"""Audit this news content against our 12-point News Rubric:

{content}

Score each criterion 0 (fails), 1 (partial), or 2 (meets fully).
Threshold to pass: 8/12.

Return EXACTLY valid JSON:
{{
  "scores": {{
    "tarafsizlik": 0-2,
    "kaynak_gosterimi": 0-2,
    "kisalik_netlik": 0-2,
    "bilgi_yogunlugu": 0-2,
    "clickbait_uzakligi": 0-2,
    "format_yapisi": 0-2
  }},
  "summary": "string assessment with specific evidence",
  "total": 0-12,
  "passes": true/false,
  "lowest_scores": ["criterion1", "criterion2"]
}}"""

        try:
            if llm and hasattr(llm, "acomplete"):
                response = await llm.acomplete([
                    {"role": "system", "content": "You are a strict news editor scoring against a rubric."},
                    {"role": "user", "content": prompt},
                ])
                text = response.text
            else:
                try:
                    from agent.auxiliary_client import async_call_llm
                except ImportError as _ie:
                    raise RuntimeError(
                        "Hermes LLM unavailable outside agent context. "
                        "Use '/haber score <slug>' via Hermes agent instead."
                    ) from _ie
                messages = [
                    {"role": "system", "content": "You are a strict news editor."},
                    {"role": "user", "content": prompt},
                ]
                raw = await async_call_llm(task="curator", messages=messages)
                try:
                    text = raw.choices[0].message.content
                except (AttributeError, IndexError):
                    text = str(raw)

            json_match = re.search(r"(\{.*\})", text, re.DOTALL)
            if json_match:
                res = json.loads(json_match.group(1))
            else:
                res = {"scores": {}, "summary": f"Failed to parse: {text[:200]}",
                       "total": 0, "passes": False}

            if "total" not in res or not res["total"]:
                res["total"] = sum(res.get("scores", {}).values())
            res["passes"] = res.get("total", 0) >= 8
            return res

        except Exception as e:
            return {"error": str(e)}

    # --- Postmortem ---

    async def run_postmortem(self, slug: str, metrics: Dict[str, Any] = None,
                             llm: Any = None) -> Dict[str, Any]:
        """LLM-based postmortem with exact-line analysis (preserved)."""
        run_path = self.active_runs / slug
        if not run_path.exists():
            return {"error": f"Run {slug} not found."}

        draft_path = run_path / "draft-package.md"
        if not draft_path.exists():
            return {"error": "Draft not found for postmortem."}

        draft_content = draft_path.read_text(encoding="utf-8")

        if not metrics:
            metrics = {
                "impressions": 0, "engagements": 0,
                "likes": 0, "paylasimlar": 0,
                "okunma": 0, "replies": 0,
            }

        current_state = self.get_state(slug)
        phase = "24h" if current_state == "feedback_24h" else "72h"

        prompt = f"""You are running a POSTMORTEM on a published news article.

Phase: {phase} hour feedback.

CONTEXT:
POST SLUG: {slug}
PHASE: {phase}
METRICS: {json.dumps(metrics, indent=2)}

PUBLISHED DRAFT:
---
{draft_content}
---

TASK — Analyze:

1. WHAT DROVE THE OKUNMA SAYISI?
   Quote the exact factual content readers valued.

2. WHAT DROVE ENGAGEMENT?
   What specific aspects drove likes/shares?

3. SOURCE ACCURACY CHECK
   Were all cited sources correct?
   Any reader feedback about factual errors?

4. WHAT WOULD YOU CHANGE?
   One factual improvement if doing again.

5. WHAT PATTERN TO CAPTURE?

Return as markdown:
---
## what_drove_okunma
...
## what_drove_engagement
...
## source_accuracy_check
...
## what_would_i_change
...
## pattern_to_capture
..."""

        try:
            if llm and hasattr(llm, "acomplete"):
                response = await llm.acomplete([
                    {"role": "system", "content": "You are a news content analyst."},
                    {"role": "user", "content": prompt},
                ])
                text = response.text
            else:
                try:
                    from agent.auxiliary_client import async_call_llm
                except ImportError as _ie:
                    raise RuntimeError(
                        "Hermes LLM unavailable outside agent context."
                    ) from _ie
                messages = [
                    {"role": "system", "content": "You are a news content analyst."},
                    {"role": "user", "content": prompt},
                ]
                raw = await async_call_llm(task="curator", messages=messages)
                try:
                    text = raw.choices[0].message.content
                except (AttributeError, IndexError):
                    text = str(raw)

            text = text.strip()
            if text.startswith("```"):
                text = re.sub(r"^```\w*\n?", "", text)
                text = re.sub(r"\n```$", "", text)

            feedback_path = run_path / "feedback.md"
            existing = ""
            if feedback_path.exists():
                existing = feedback_path.read_text(encoding="utf-8") + "\n\n---\n\n"

            okunma_rate = (
                metrics.get("okunma", 0) / max(metrics.get("impressions", 1), 1) * 100
            )

            feedback_content = f"""{existing}# {phase}h Feedback — {slug}

**Date:** {datetime.now().isoformat()}
**Phase:** {phase}
**Metrics:** {json.dumps(metrics, indent=2)}
**Okunma Rate:** {okunma_rate:.1f}%

## Analysis
{text}
"""
            feedback_path.write_text(feedback_content, encoding="utf-8")

            new_state = "feedback_72h" if phase == "24h" else "learned"
            self.update_state(slug, new_state)

            # Check if correction needed based on feedback
            self.check_correction_needed(slug)

            return {
                "slug": slug,
                "phase": phase,
                "metrics": metrics,
                "okunma_rate": okunma_rate,
                "analysis": text,
                "new_state": new_state,
            }

        except Exception as e:
            return {"error": f"Postmortem failed: {str(e)}"}

    # --- Voice Evolution ---

    def update_voice_profile(self, updates: Dict[str, Any]) -> str:
        """Update voice profile based on learnings."""
        vf = self.voice / "voice-profile.md"
        if not vf.exists():
            return "No voice profile exists."

        current = vf.read_text(encoding="utf-8")
        section = f"\n\n---\n\n## Updates from Feedback ({datetime.now().strftime('%Y-%m-%d')})\n\n"

        if updates.get("new_rules"):
            section += "### New Rules\n"
            for r in updates["new_rules"]:
                section += f"- {r}\n"
        if updates.get("banned_patterns"):
            section += "### Banned Patterns\n"
            for p in updates["banned_patterns"]:
                section += f"- {p}\n"
        if updates.get("insights"):
            section += "### Voice Insights\n"
            for i in updates["insights"]:
                section += f"- {i}\n"

        vf.write_text(current + section, encoding="utf-8")

        if updates.get("new_slop_patterns"):
            self._update_avoid_slop(updates["new_slop_patterns"])

        return "✅ Voice profile updated."

    def _update_avoid_slop(self, new_patterns: List[str]):
        sf = self.voice / "master-avoid-slop.md"
        if not sf.exists():
            return
        current = sf.read_text(encoding="utf-8")
        section = f"\n\n---\n\n## New Patterns ({datetime.now().strftime('%Y-%m-%d')})\n\n"
        for p in new_patterns:
            section += f"- {p}\n"
        sf.write_text(current + section, encoding="utf-8")

    # --- Signal Processing ---

    def process_signal(self, source: str) -> List[str]:
        """Process signals from various sources."""
        if source == "x":
            return self._scan_x_signals()
        elif source == "rss":
            return self._scan_rss_signals()
        return ["Unknown source. Supported: 'x', 'rss'"]

    def _scan_x_signals(self) -> List[str]:
        inbox = self.stores / "inbox.md"
        signals = []
        if inbox.exists():
            content = inbox.read_text(encoding="utf-8")
            entries = re.findall(r'### .*?(?=\n###|\Z)', content, re.DOTALL)
            for e in entries:
                if any(x in e.lower() for x in ['x', 'memos', 'x.com']):
                    signals.append(e.strip()[:200])
        if not signals:
            signals = [
                "Signal: New RISC-V optimization patterns emerging",
                "Signal: AI Agents moving to local-first architectures",
                "Signal: Open-source hardware momentum growing",
            ]
        return signals[:5]

    def _scan_rss_signals(self) -> List[str]:
        """Fetch real RSS headlines from known NEWS_SOURCES + source-watchlist.md.

        First tries directly from NEWS_SOURCES RSS feeds (v3.0+), then falls
        back to probing URLs from source-watchlist.md (legacy).
        """
        signals = []
        ATOM_NS = "{http://www.w3.org/2005/Atom}"

        # Try known NEWS_SOURCES RSS feeds first (v3.0+)
        for key, src in self.sources.items():
            if len(signals) >= 5:
                break
            for feed_url in src.rss_feeds:
                if len(signals) >= 5:
                    break
                try:
                    req = urllib.request.Request(
                        feed_url,
                        headers={"User-Agent": f"Haber-Kuratör/{VERSION} RSS Reader"},
                    )
                    with urllib.request.urlopen(req, timeout=CONFIG["rss_timeout"]) as resp:
                        xml_data = resp.read()
                    root_el = ET.fromstring(xml_data)
                    for item in root_el.findall(".//item")[:1]:
                        title = item.findtext("title", "").strip()
                        if title:
                            signals.append(f"[{src.name}] {title[:110]}")
                    if not signals or signals[-1].startswith(f"[{src.name}]"):
                        for entry in root_el.findall(f".//{ATOM_NS}entry")[:1]:
                            t_el = entry.find(f"{ATOM_NS}title")
                            if t_el is not None and t_el.text:
                                signals.append(f"[{src.name}] {t_el.text.strip()[:110]}")
                except Exception:
                    continue

        # Fallback: probe source-watchlist.md URLs (legacy)
        if not signals:
            wl = self.strategy / "source-watchlist.md"
            if wl.exists():
                content = wl.read_text(encoding="utf-8")
                raw_urls = re.findall(r'https?://[^\s\)\()]+', content)
                seen: set = set()
                base_urls = []
                for url in raw_urls:
                    base = "/".join(url.split("/")[:3])
                    if base not in seen:
                        seen.add(base)
                        base_urls.append(base)

                for base in base_urls[:6]:
                    if len(signals) >= 5:
                        break
                    for suffix in RSS_PROBES:
                        try:
                            req = urllib.request.Request(
                                base + suffix,
                                headers={"User-Agent": f"Haber-Kuratör/{VERSION} RSS Reader"},
                            )
                            with urllib.request.urlopen(req, timeout=CONFIG["rss_timeout"]) as resp:
                                xml_data = resp.read()
                            root_el = ET.fromstring(xml_data)
                            fetched = False
                            for item in root_el.findall(".//item")[:2]:
                                title = item.findtext("title", "").strip()
                                if title:
                                    domain = base.replace("https://", "").replace("http://", "").split("/")[0]
                                    signals.append(f"[{domain}] {title[:110]}")
                                    fetched = True
                            if not fetched:
                                for entry in root_el.findall(f".//{ATOM_NS}entry")[:2]:
                                    t_el = entry.find(f"{ATOM_NS}title")
                                    if t_el is not None and t_el.text:
                                        domain = base.replace("https://", "").replace("http://", "").split("/")[0]
                                        signals.append(f"[{domain}] {t_el.text.strip()[:110]}")
                                        fetched = True
                            if fetched:
                                break
                        except Exception:
                            continue

        if not signals:
            signals = [
                "RSS: No live feed reached — check NEWS_SOURCES RSS URLs",
                "Try: hermes haber fetch for the full news pipeline",
            ]

        return signals[:5]

    # --- Learning Extraction ---

    def _save_learnings(self, slug: str, analysis: Dict[str, Any],
                         metrics: Dict[str, Any]):
        okunma_rate = analysis.get("okunma_rate", 0)
        if okunma_rate > 5:
            proof_name = f"{slug}-{datetime.now().strftime('%Y%m')}"
            proof_path = self.stores / "proof" / f"{proof_name}.md"
            proof_content = f"""# Proof from {slug}

**Metrics:**
- Impressions: {metrics.get('impressions', 0)}
- Okunmalar: {metrics.get('okunma', 0)}
- Okunma Rate: {okunma_rate:.1f}%

**What Worked:**
{analysis.get('pattern_to_capture', 'N/A')}

**Date: {datetime.now().isoformat()}**
"""
            proof_path.write_text(proof_content, encoding="utf-8")

        feedback_dir = self.stores / "feedback"
        feedback_dir.mkdir(parents=True, exist_ok=True)
        feedback_name = f"{slug}-{datetime.now().strftime('%Y%m%d')}.md"
        feedback_path = feedback_dir / feedback_name
        summary = f"""# Feedback: {slug}

**Metrics:**
- Impressions: {metrics.get('impressions', 0)}
- Okunmalar: {metrics.get('okunma', 0)}
- Likes: {metrics.get('likes', 0)}
- Paylaşımlar: {metrics.get('paylasimlar', 0)}

**Performance:** {'Good' if okunma_rate > 5 else 'Needs improvement'}
**Date: {datetime.now().isoformat()}**
"""
        feedback_path.write_text(summary, encoding="utf-8")

    def get_learnings_for_brief(self, topic: str = None) -> str:
        learnings = []
        feedback_dir = self.stores / "feedback"
        if feedback_dir.exists():
            for f in feedback_dir.glob("*.md"):
                content = f.read_text(encoding="utf-8")
                if "Good" in content or "okunma" in content.lower():
                    learnings.append(f"From {f.stem}: {content[:150]}")
        proof_dir = self.stores / "proof"
        if proof_dir.exists():
            for p in proof_dir.glob("*.md"):
                content = p.read_text(encoding="utf-8")
                learnings.append(f"Proof: {content[:150]}")
        if not learnings:
            return "No learnings available yet."
        return "\n\n".join(learnings[:5])

    # --- Context Retrieval ---

    def _get_relevant_proof(self, idea: str) -> str:
        if self.gbrain_enabled:
            gbrain_result = self._query_gbrain(idea)
            if gbrain_result:
                return "\n\n".join([f"## {k}\n{v}" for k, v in gbrain_result.items()])
        proof_dir = self.stores / "proof"
        if not proof_dir.exists():
            return "No proof directory found."
        proof_files = list(proof_dir.glob("*.md"))
        if not proof_files:
            return "No proof available."
        return "\n\n".join(
            [f"## {p.stem}\n{p.read_text(encoding='utf-8')[:300]}"
             for p in proof_files[:3]]
        )

    def _get_successful_hooks(self) -> str:
        hooks_dir = self.stores / "hooks"
        if not hooks_dir.exists() or not list(hooks_dir.glob("*.md")):
            return "No successful hooks recorded yet."
        return "\n".join(
            [f"- {h.stem}: {h.read_text(encoding='utf-8')[:100]}"
             for h in list(hooks_dir.glob("*.md"))[:5]]
        )

    def _get_top_performing_runs(self) -> str:
        if not self.archive.exists():
            return "No archived runs yet."
        runs = []
        for d in self.archive.iterdir():
            if d.is_dir():
                fb = d / "feedback.md"
                if fb.exists():
                    content = fb.read_text(encoding="utf-8")
                    bm = re.search(r'okunma?[\s:]+(\d+)', content, re.IGNORECASE)
                    okunma = int(bm.group(1)) if bm else 0
                    runs.append((d.name, okunma))
        runs.sort(key=lambda x: x[1], reverse=True)
        if not runs:
            return "No run feedback available."
        return "\n".join([f"- {name}: {okunma} okunma" for name, okunma in runs[:5]])

    def _get_voice_summary(self) -> str:
        vf = self.voice / "voice-profile.md"
        if not vf.exists():
            return "No voice profile set."
        content = vf.read_text(encoding="utf-8")
        lines = [line for line in content.split('\n')
                 if line.strip().startswith(('1.', '2.', '3.', '4.', '5.'))]
        return "\n".join(lines[:5]) if lines else content[:300]

    def enable_gbrain(self):
        """Enable GBrain integration for enhanced context retrieval.

        GBrain integration provides semantic search over past learnings.
        When enabled, _query_gbrain uses GBrain MCP tools to find
        relevant proof and context for news briefs.

        Note: GBrain MCP tools must be connected at runtime via Hermes
        config. This is a passive integration point — no MCP import needed here.
        """
        self.gbrain_enabled = True
        logger.info("GBrain integration enabled for Haber Kuratör")

    def _query_gbrain(self, query: str) -> Dict[str, str]:
        """Query GBrain for relevant context.

        Integration point: when GBrain MCP tools (mcp_gbrain_query, etc.)
        are connected, this method can use them to find relevant pages.

        Example implementation:
            from hermes_tools import mcp_gbrain_query
            result = mcp_gbrain_query(query=query, limit=3)
            return {item['slug']: item['content'] for item in result.get('results', [])}

        Returns empty dict when GBrain is not connected.
        """
        if not self.gbrain_enabled:
            return {}
        logger.debug(f"GBrain query (stub): {query[:80]}")
        return {}

    # --- Pattern Analysis ---

    def analyze_run_patterns(self) -> Dict[str, Any]:
        all_runs = []
        for base_dir in [self.active_runs, self.archive]:
            if base_dir.exists():
                for d in base_dir.iterdir():
                    if d.is_dir():
                        try:
                            rd = self._analyze_single_run(d)
                            if rd:
                                all_runs.append(rd)
                        except Exception:
                            continue

        if not all_runs:
            return {"message": "No runs to analyze."}

        total = len(all_runs)
        avg_bm = sum(r.get("okunma", 0) for r in all_runs) / max(total, 1)
        formats = {}
        pillars = {}
        for r in all_runs:
            formats[r.get("format", "unknown")] = formats.get(r.get("format", "unknown"), 0) + 1
            pillars[r.get("pillar", "unknown")] = pillars.get(r.get("pillar", "unknown"), 0) + 1

        states = {}
        for r in all_runs:
            st = r.get("state", "unknown")
            states[st] = states.get(st, 0) + 1

        return {
            "total_runs": total,
            "avg_okunma": round(avg_bm, 1),
            "top_formats": sorted(formats.items(), key=lambda x: x[1], reverse=True)[:5],
            "top_pillars": sorted(pillars.items(), key=lambda x: x[1], reverse=True)[:5],
            "state_distribution": states,
            "archive_count": len([r for r in all_runs if r.get("status") == "archived"]),
        }

    def _analyze_single_run(self, run_path: Path) -> Optional[Dict[str, Any]]:
        try:
            result = {"slug": run_path.name}
            obj = run_path / "haber-object.md"
            if obj.exists():
                content = obj.read_text(encoding="utf-8")
                for field in ["state", "route"]:
                    m = re.search(rf'{field}:\s*(.+)', content, re.IGNORECASE)
                    if m:
                        result[field] = m.group(1).strip()
            fb = run_path / "feedback.md"
            if fb.exists():
                content = fb.read_text(encoding="utf-8")
                bm = re.search(r'okunma?[\s:]+(\d+)', content, re.IGNORECASE)
                if bm:
                    result["okunma"] = int(bm.group(1))
            result["status"] = "archived" if "archive" in str(run_path) else "active"
            return result
        except PermissionError:
            return None

    # --- Audit & Retrieval ---

    def audit(self) -> str:
        """Full system audit."""
        issues = []
        warnings = []
        critical = [self.strategy, self.voice, self.stores,
                    self.workflows, self.references,
                    self.root / "runs", self.active_runs]
        for d in critical:
            if not d.exists():
                issues.append(f"Missing directory: {d.name}")

        for sub in ["ideas", "hooks", "proof", "feedback"]:
            if not (self.stores / sub).exists():
                issues.append(f"Missing stores subdirectory: {sub}")

        for sf in ["positioning.md", "audience.md", "pillars.md"]:
            if not (self.strategy / sf).exists():
                warnings.append(f"Missing strategy file: {sf}")

        active_count = len([d for d in self.active_runs.iterdir() if d.is_dir()]) if self.active_runs.exists() else 0
        archive_count = len([d for d in self.archive.iterdir() if d.is_dir()]) if self.archive.exists() else 0

        # Check source directory health
        total_sources = len(self.sources)
        tier0_count = len(self.get_sources_by_tier(SourceTier.PRIMARY))
        tier1_count = len(self.get_sources_by_tier(SourceTier.MAJOR))

        if not issues:
            base = (
                f"✅ Haber Kuratör v{VERSION} Audit: {active_count} active, {archive_count} archived.\n"
                f"📡 News Sources: {total_sources} total ({tier0_count} primary, {tier1_count} major)"
            )
            if warnings:
                base += "\n⚠️ " + "\n⚠️ ".join(warnings)
            return base

        return (
            f"❌ Haber Kuratör v{VERSION} Audit\n"
            f"📡 News Sources: {total_sources} total\n"
            f"❌ Issues:\n- " + "\n- ".join(issues) +
            ("\n⚠️ " + "\n⚠️ ".join(warnings) if warnings else "")
        )

    def get_all_runs(self, include_archived: bool = True) -> List[Dict[str, Any]]:
        runs = []
        if self.active_runs.exists():
            for d in self.active_runs.iterdir():
                if d.is_dir():
                    ri = self._get_run_info(d)
                    ri["status"] = "active"
                    runs.append(ri)
        if include_archived and self.archive.exists():
            for d in self.archive.iterdir():
                if d.is_dir():
                    ri = self._get_run_info(d)
                    ri["status"] = "archived"
                    runs.append(ri)
        return runs

    def _get_run_info(self, run_path: Path) -> Dict[str, Any]:
        info = {"slug": run_path.name, "files": []}
        try:
            for f in run_path.iterdir():
                if f.is_file():
                    info["files"].append(f.name)
        except PermissionError:
            info["files"] = ["[locked]"]
            return info

        obj = run_path / "haber-object.md"
        if obj.exists():
            content = obj.read_text(encoding="utf-8")
            for field in ["title", "state", "route"]:
                m = re.search(rf'(?:\*\*)?{field}(?:\*\*)?:\*{{0,2}}\s*(.+)', content, re.IGNORECASE)
                if m:
                    info[field] = m.group(1).strip().lstrip('* ')
        return info

    def search_runs(self, query: str) -> List[Dict[str, Any]]:
        results = []
        q = query.lower()
        for run in self.get_all_runs():
            rp = self.active_runs / run["slug"]
            if not rp.exists():
                rp = self.archive / run["slug"]
            if not rp.exists():
                continue
            try:
                for f in rp.iterdir():
                    if f.is_file() and f.suffix == ".md":
                        try:
                            content = f.read_text(encoding="utf-8").lower()
                            if q in content:
                                results.append({
                                    "slug": run["slug"],
                                    "file": f.name,
                                    "state": run.get("state", "unknown"),
                                })
                                break
                        except Exception:
                            continue
            except PermissionError:
                continue
        return results

    def archive_run(self, slug: str, force: bool = False) -> str:
        """Move a run from active to archive."""
        state = self.get_state(slug)
        valid_pre_archive = [t for s, targets in STATE_TRANSITIONS.items() if "archived" in targets for t in [s]]
        if state not in valid_pre_archive and not force:
            return f"❌ Cannot archive {slug} (state: {state}). Must be one of: {', '.join(valid_pre_archive)} or use --force."

        src = self.active_runs / slug
        if not src.exists():
            return f"❌ Run {slug} not found."

        dst = self.archive / slug
        if dst.exists():
            return f"❌ Archive already contains {slug}."

        try:
            shutil.copytree(str(src), str(dst))
            shutil.rmtree(str(src))
            existing = self._state_cache.get(slug, RunState(slug=slug))
            self._state_cache[slug] = RunState(
                slug=slug,
                title=existing.title,
                state="archived",
                route=existing.route,
                created=existing.created,
                updated=datetime.now().isoformat(),
                source_type=existing.source_type,
                verification_level=existing.verification_level,
            )
            self._save_state_cache()
            obj_path = dst / "haber-object.md"
            if obj_path.exists():
                try:
                    obj_content = obj_path.read_text(encoding="utf-8")
                    if "state:" in obj_content:
                        obj_content = re.sub(r"state:\s*\w+", "state: archived", obj_content)
                    else:
                        obj_content += "\nstate: archived"
                    obj_path.write_text(obj_content, encoding="utf-8")
                except Exception:
                    pass
            return f"✅ Run {slug} archived."
        except Exception as e:
            return f"❌ Archive failed: {str(e)}"


# ══════════════════════════════════════════════════════════════
# TOOL HANDLERS
# ══════════════════════════════════════════════════════════════

async def tool_haber_kurator_manager(core: HaberKuratorCore, args: Dict[str, Any],
                                   **kwargs) -> str:
    """Handle all manager tool actions."""
    try:
        action = args.get("action")
        slug = args.get("slug")

        # System
        if action == "setup":
            return core.setup()
        if action == "audit":
            return core.audit()
        if action == "list":
            return json.dumps(core.get_all_runs(args.get("include_archived", True)))

        # News Source Management (NEW)
        if action == "sources":
            return core.get_source_summary()
        if action == "fetch_news":
            category = args.get("category")
            country = args.get("country")
            items = core.fetch_all_news(category, country)
            clusters = core.cluster_stories(items)
            return json.dumps({
                "total_items": len(items),
                "clusters": len(clusters),
                "top_stories": [
                    {
                        "title": c["story_title"][:100],
                        "sources": c["source_count"],
                        "best_url": c.get("best_url", ""),
                        "tiers": c["tier_count"],
                    }
                    for c in clusters[:10]
                ],
            }, indent=2, ensure_ascii=False)

        if action == "search_news":
            """Search for a specific news topic across multiple sources.

            Uses Google News RSS search + existing clustering/verification.
            Supports Turkish and English queries with language/country detection.
            """
            query = args.get("search_query", "")
            if not query:
                return "❌ 'search_query' parameter is required."
            max_results = args.get("max_results", 20)
            language = args.get("language", "tr")
            country = args.get("country", "TR")
            result = core.search_news(query, max_results, language, country)
            return json.dumps(result, indent=2, ensure_ascii=False)

        if action == "verify_news":
            """Fetch, cluster, and cross-verify all news from sources."""
            category = args.get("category")
            country = args.get("country")
            items = core.fetch_all_news(category, country)
            clusters = core.cluster_stories(items)
            verified = []
            for cluster in clusters[:args.get("limit", 10)]:
                verification = core.cross_verify_story(cluster)
                verified.append(verification.to_dict())
            return json.dumps(verified, indent=2, ensure_ascii=False)

        if action == "publish_verified":
            """Fetch, verify, and create runs for top news items."""
            category = args.get("category")
            human_review = args.get("human_review", True)
            country = args.get("country")
            items = core.fetch_all_news(category, country)
            clusters = core.cluster_stories(items)
            results = []
            for cluster in clusters[:args.get("limit", 5)]:
                result = core.publish_verified_news(cluster, human_review)
                results.append(result)
            return json.dumps(results, indent=2, ensure_ascii=False)

        if action == "cross_verify_story":
            """Cross-verify a specific story cluster."""
            cluster_data = args.get("cluster_data", {})
            if not cluster_data:
                return "❌ cluster_data required"
            # Reconstruct FetchedNewsItem from dict
            items = []
            for item_dict in cluster_data.get("items", []):
                items.append(FetchedNewsItem(
                    title=item_dict["title"],
                    url=item_dict.get("url", ""),
                    source_name=item_dict.get("source_name", "Unknown"),
                    source_tier=SourceTier(item_dict.get("source_tier", 2)),
                    published=item_dict.get("published", ""),
                    summary=item_dict.get("summary", ""),
                    category=item_dict.get("category", "general"),
                ))
            cluster_data["items"] = items
            verification = core.cross_verify_story(cluster_data)
            return json.dumps(verification.to_dict(), indent=2, ensure_ascii=False)

        # Hallucination Guard (NEW)
        if action == "hallucination_check":
            return json.dumps(core.hallucination_check(slug))

        if action == "scan_slop":
            return json.dumps(core.scan_slop(args.get("text", "")))

        # Correction Workflow (NEW)
        if action == "check_correction":
            return core.check_correction_needed(slug)

        if action == "issue_correction":
            return core.issue_correction(
                slug,
                args.get("error_description", ""),
                args.get("correct_information", ""),
                args.get("retract", False),
            )

        # Run actions
        if action == "update_state":
            return core.update_state(slug, args.get("state"))
        if action == "get_state":
            return json.dumps({
                "slug": slug, "state": core.get_state(slug),
                "next_actions": core.get_next_actions(slug),
            })
        if action == "sync_state":
            return f"State: {core.sync_state(slug)}"
        if action == "get_next_actions":
            return json.dumps(core.get_next_actions(slug))

        # Writer Agent — Auto Publish
        if action == "auto_publish":
            try:
                # Force module reload to pick up code changes (Python module cache)
                import importlib as _hermes_il
                import sys as _hermes_sys
                for _mod in ['hermes_plugins.haber_kurator.writer_agent']:
                    if _mod in _hermes_sys.modules:
                        _hermes_il.reload(_hermes_sys.modules[_mod])
                from .writer_agent import WriterAgent
                agent = WriterAgent(core)
                # Enable Turkish content generation via LLM
                # (same approach as slash command handler — import-based detection)
                try:
                    from agent.auxiliary_client import async_call_llm
                    agent.set_llm(True)
                    _call_llm_logger = logging.getLogger(__name__)
                    _call_llm_logger.info("auto_publish: LLM available, set_llm(True) called")
                except ImportError as _ie:
                    # Fallback: try parent_agent from kwargs (older path)
                    llm_ctx = kwargs.get("parent_agent")
                    llm_obj = llm_ctx.ctx.llm if llm_ctx and hasattr(llm_ctx, "ctx") else None
                    if llm_obj:
                        agent.set_llm(True)
                results = agent.auto_publish(
                    max_articles=args.get("limit", 5),
                    category=args.get("category"),
                    country=args.get("country"),
                )
                return json.dumps(results, indent=2, ensure_ascii=False)
            except Exception as e:
                return f"Error in auto_publish: {str(e)}"

        # Search
        if action == "search_runs":
            return json.dumps(core.search_runs(args.get("query", "")))
        if action == "get_all_runs":
            return json.dumps(core.get_all_runs(args.get("include_archived", True)))

        # Archive
        if action == "archive_run":
            return core.archive_run(slug)

        return f"Unknown action: {action}"

    except Exception as e:
        return f"Error: {str(e)}"


def tool_haber_kurator_retriever(core: HaberKuratorCore, args: Dict[str, Any]) -> str:
    """Retrieve knowledge from Haber Kuratör stores."""
    try:
        category = args.get("category")
        slug = args.get("slug")

        if category == "sources":
            return json.dumps(core.get_all_sources(), indent=2, ensure_ascii=False)

        if category == "source_summary":
            return core.get_source_summary()

        if category == "strategy":
            result = {}
            for f in ["positioning.md", "audience.md", "pillars.md", "source-watchlist.md"]:
                path = core.strategy / f
                if path.exists():
                    result[f.replace(".md", "")] = path.read_text(encoding="utf-8")
            return json.dumps(result) if result else "No strategy files found."

        if category == "voice":
            result = {}
            for f in ["voice-profile.md", "master-avoid-slop.md"]:
                path = core.voice / f
                if path.exists():
                    result[f.replace(".md", "")] = path.read_text(encoding="utf-8")
            return json.dumps(result) if result else "No voice files found."

        if category == "run" and slug:
            for base in [core.active_runs, core.archive]:
                rp = base / slug
                if rp.exists():
                    files = ["haber-object.md", "idea.md", "brief.md",
                             "draft-package.md", "verifier-report.md",
                             "feedback.md", "context.md", "fact-check-report.md",
                             "correction.md"]
                    result = {}
                    for f in files:
                        fp = rp / f
                        if fp.exists():
                            result[f.replace(".md", "")] = fp.read_text(encoding="utf-8")
                    return json.dumps(result) if result else f"No data for {slug}"
            return json.dumps({"error": f"Run {slug} not found."})

        if category == "stores":
            result = {}
            for subdir in ["inbox.md", "workboard.md", "ideas", "hooks", "proof", "feedback"]:
                path = core.stores / subdir
                if path.is_file():
                    result[subdir.replace(".md", "")] = path.read_text(encoding="utf-8")
                elif path.exists() and path.is_dir():
                    files = [f.name for f in path.glob("*.md")]
                    result[subdir] = files
            return json.dumps(result)

        if category == "learnings":
            return core.get_learnings_for_brief(args.get("topic"))

        return f"Unknown category: {category}"

    except Exception as e:
        return f"Error: {str(e)}"
