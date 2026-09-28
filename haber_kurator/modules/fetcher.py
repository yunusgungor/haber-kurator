"""
Haber Kuratör — Fetcher Module
==================================
FetcherMixin for HaberKuratorCore.

Handles: source management, RSS fetching, search, clustering,
cross-verification, slug creation, run management.
"""

import json
import logging
import re
import time
import urllib.request
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple


from haber_kurator.modules.models import (
    VERSION,
    SourceTier, VerificationLevel,
    NewsSource, FactClaim, CrossVerificationResult,
    FetchedNewsItem, RunState,
    CONFIG, ROUTE_VERIFIED,
    STATE_ALIAS_MAP, STATE_LIFECYCLE,
    SourceError,
)

logger = logging.getLogger(__name__)


class FetcherMixin:
    """Mixin providing news fetching and cross-verification capabilities."""

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

    # ══════════════════════════════════════════════════════════

    def fetch_all_news(self, category: str = None, country: str = None,
                       trending: bool = False, today_only: bool = False) -> List[FetchedNewsItem]:
        """Fetch latest news from configured sources.

        Pulls from every source that has RSS feeds defined.
        Returns deduplicated list of news items.

        Args:
            category: Optional filter ('news', 'technology', 'business', 'science')
            country: Optional filter by country code (e.g. 'turkey', 'global')
            trending: When True, also fetch from sources' trending_feeds and
                      apply tighter recency (24h instead of 48h).
            today_only: When True, filter to current calendar day only (kullanıcının
                       "bugünün haberleri" beklentisi için).

        Returns:
            List of FetchedNewsItem with source and URL.
        """
        logger.info(f"fetch_all_news called (category={category}, country={country}, "
                    f"trending={trending}, today_only={today_only})")
        all_items: List[FetchedNewsItem] = []
        errors = []

        sources_to_fetch = self.sources
        if category:
            sources_to_fetch = self.get_sources_by_category(category)
        if country:
            by_country = self.get_sources_by_country(country)
            if category:
                sources_to_fetch = {k: v for k, v in sources_to_fetch.items() if k in by_country}
            else:
                sources_to_fetch = by_country

        # Collect (feed_url, source) pairs
        feed_tasks: List[Tuple[str, NewsSource]] = []
        for key, source in sources_to_fetch.items():
            if not source.rss_feeds:
                continue
            for feed_url in source.rss_feeds:
                feed_tasks.append((feed_url, source))
            # In trending mode, also fetch trending_feeds from matching sources
            if trending and source.trending_feeds:
                for feed_url in source.trending_feeds:
                    feed_tasks.append((feed_url, source))

        # Fetch in parallel with ThreadPoolExecutor (v3.2.0)
        all_items: List[FetchedNewsItem] = []
        errors: List[str] = []
        with ThreadPoolExecutor(max_workers=CONFIG["rss_max_workers"]) as pool:
            futures = {
                pool.submit(self._fetch_rss_feed, url, src): (url, src.name)
                for url, src in feed_tasks
            }
            for fut in as_completed(futures):
                url, name = futures[fut]
                try:
                    items = fut.result()
                    all_items.extend(items)
                except Exception as e:
                    errors.append(f"{name}/{url}: {str(e)[:60]}")

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

        # Filter out old news (recency check — tighter 24h in trending mode)
        max_age = 24 if trending else CONFIG.get("news_max_age_hours", 48)
        fresh = []
        stale_count = 0
        for item in filtered:
            passes_age = self._is_today(item.published) if today_only else self._is_fresh(item.published, max_age_hours=max_age)
            if passes_age:
                fresh.append(item)
            else:
                stale_count += 1

        label = "today" if today_only else f"{max_age}h"
        logger.info(f"fetch_all_news: {len(all_items)} raw, {len(unique)} unique, "
                    f"{len(unique) - len(filtered)} promo filtered, "
                    f"{stale_count} stale (> {label}), "
                    f"{len(fresh)} final. "
                    f"{len(errors)} fetch errors.")
        return fresh


    def _fetch_url_with_retry(self, url: str, headers: Dict[str, str],
                               timeout: int) -> Tuple[bytes, Any]:
        """Fetch URL with exponential backoff retry for transient errors.

        Retries on: HTTP 429/5xx, URLError, OSError (connection reset).
        Does NOT retry: 304 (propagated to caller), 4xx (except 429), parse errors.

        Returns:
            (raw_body_bytes, response_headers)
        Raises:
            urllib.error.HTTPError: non-retryable HTTP error (incl. 304)
            urllib.error.URLError: network error after all retries exhausted
            OSError: connection error after all retries exhausted
        """
        retry_delays = CONFIG["rss_retry_delays"]
        last_exc = None
        for attempt in range(len(retry_delays) + 1):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read(), resp.headers
            except urllib.error.HTTPError as e:
                # 304 should be handled by the caller (cache hit)
                if e.code == 304:
                    raise
                # Retry on rate-limit (429) and server errors (5xx)
                if e.code in (429, 500, 502, 503) and attempt < len(retry_delays):
                    last_exc = e
                    logger.debug(f"Retry {url} (attempt {attempt+1}) after HTTP {e.code}")
                    time.sleep(retry_delays[attempt])
                    continue
                raise
            except (urllib.error.URLError, OSError) as e:
                if attempt < len(retry_delays):
                    last_exc = e
                    logger.debug(f"Retry {url} (attempt {attempt+1}) after {type(e).__name__}")
                    time.sleep(retry_delays[attempt])
                    continue
                raise
        # All retries exhausted
        raise last_exc  # type: ignore


    def _fetch_rss_feed(self, feed_url: str, source: NewsSource) -> List[FetchedNewsItem]:
        """Fetch a single RSS feed with HTTP Conditional GET (ETag/Last-Modified)
        and exponential backoff retry for transient errors.

        Returns cached items (from a prior scan in this session) when the
        server responds 304 Not Modified, saving bandwidth on unchanged feeds.
        Cache is per-session (ephemeral) — lost on process restart.
        """
        items: List[FetchedNewsItem] = []
        cached = self._rss_cache.get(feed_url, {})
        headers = {"User-Agent": f"Haber-Kuratör/{VERSION} NewsReader"}
        etag = cached.get("etag")
        lm = cached.get("last_modified")

        if etag:
            headers["If-None-Match"] = etag
        if lm:
            headers["If-Modified-Since"] = lm

        try:
            xml_data, resp_headers = self._fetch_url_with_retry(
                feed_url, headers, CONFIG["rss_timeout"],
            )
            resp_etag = resp_headers.get("ETag")
            resp_lm = resp_headers.get("Last-Modified")
            self._rss_cache[feed_url] = {
                "etag": resp_etag,
                "last_modified": resp_lm,
            }

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

            # Atom fallback
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

            # Store parsed items in cache for future 304 hits
            self._rss_cache[feed_url]["items"] = items

        except urllib.error.HTTPError as e:
            if e.code == 304 and cached.get("items"):
                # 304 Not Modified — return previously cached items
                logger.debug(f"304 for {feed_url} — using cached items ({len(cached['items'])})")
                return cached["items"]
            logger.debug(f"HTTP {e.code} for {feed_url}: {e}")
        except ET.ParseError as e:
            logger.debug(f"XML parse error for {feed_url}: {e}")
        except (urllib.error.URLError, OSError) as e:
            logger.debug(f"Network error for {feed_url}: {e}")

        return items

    @staticmethod
    def _is_fresh(published: str, max_age_hours: int = 48) -> bool:
        """Check if a published-date string is within max_age_hours.

        Parses RFC 2822 (RSS pubDate), ISO-8601 (Atom), Turkish/DMY formats.
        Returns True if the item is fresh enough (or date is unparseable).
        """
        if not published or not published.strip():
            return True  # no date → keep (better than dropping everything)

        now = datetime.now(timezone.utc)

        # Try RFC 2822 (e.g. "Mon, 25 Sep 2026 14:30:00 +0300")
        try:
            dt = datetime.strptime(published[:25], "%a, %d %b %Y %H:%M:%S")
        except (ValueError, IndexError):
            pass
        else:
            # RFC 2822 parsed without tz → assume UTC for comparison
            return (now - dt.replace(tzinfo=timezone.utc)).total_seconds() < max_age_hours * 3600

        # Try ISO-8601 (e.g. "2026-09-25T14:30:00Z" or "2026-09-25T14:30:00+03:00")
        try:
            dt = datetime.fromisoformat(published.rstrip("Z"))
        except (ValueError, TypeError):
            pass
        else:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (now - dt).total_seconds() < max_age_hours * 3600

        # Try Turkish-style (e.g. "25 Eylül 2026 Pazartesi 14:30")
        # Fallback: just check if mentioned year is current year
        for y in range(datetime.now().year - 2, datetime.now().year):
            if str(y) in published:
                return False

        return True  # unparseable → keep

    @staticmethod
    def _is_today(published: str) -> bool:
        """Check if a published-date string falls on the current calendar day.

        Uses local timezone for calendar day boundary. Returns True for
        unparseable dates (fail-open — better than dropping everything).
        """
        if not published or not published.strip():
            return True

        today = datetime.now(timezone.utc).date()

        # Try RFC 2822 (e.g. "Mon, 28 Sep 2026 14:30:00 +0300")
        try:
            dt = datetime.strptime(published[:25], "%a, %d %b %Y %H:%M:%S")
            return dt.replace(tzinfo=timezone.utc).date() == today
        except (ValueError, IndexError):
            pass

        # Try ISO-8601 (e.g. "2026-09-28T14:30:00Z")
        try:
            dt = datetime.fromisoformat(published.rstrip("Z"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.date() == today
        except (ValueError, TypeError):
            pass

        # Try date prefix match (e.g. "2026-09-28" anywhere in the string)
        today_str = today.isoformat()
        if today_str in published:
            return True

        return True  # unparseable → keep


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
        initial_state = "verified" if verification.is_safe_to_publish else "captured"

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

    # ══════════════════════════════════════════════════════════
        return to_state in STATE_TRANSITIONS[from_state]
        return guide.get(state, ["No specific next actions for this state."])


    def process_signal(self, source: str) -> List[str]:
        """Process signals from various sources."""
        if source == "x":
            return self._scan_x_signals()
        elif source == "rss":
            return self._scan_rss_signals()
        return ["Unknown source. Supported: 'x', 'rss'"]


    def enable_gbrain(self):
        """Enable GBrain integration (stub).

        GBrain integration placeholder for enhanced context retrieval.
        """
        logger.info("GBrain integration enabled (stub)")


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
                        except (OSError, PermissionError):
                            continue
            except PermissionError:
                continue
        return results

# ══════════════════════════════════════════════════════════════

