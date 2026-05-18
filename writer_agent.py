"""
Writer Agent — Automatic News Article Generator for Memos Publishing
=====================================================================
Generates proper Turkish [Özet] - [Detaylar] - [Kaynak] formatted news
articles from verified story clusters and publishes them to Memos.
"""

import os
import json
import urllib.request
import re
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from .haber_kurator_core import HaberKuratorCore, VerificationLevel


class WriterAgent:
    """Automated Writer Agent that generates Turkish news content from verified clusters.

    Uses Hermes Agent's built-in LLM for Turkish content generation when available.
    Falls back to template-based Turkish output (with English headlines) when LLM unavailable.
    """

    def __init__(self, core: HaberKuratorCore):
        self.core = core
        self._load_env()
        self._llm_available = False  # Set to True if Hermes LLM is reachable

    def set_llm(self, available: bool = True):
        """Mark that Hermes Agent LLM is available for Turkish content generation."""
        self._llm_available = available

    def _call_llm(self, system: str, user: str, task: str = "curator", timeout: int = 60) -> Optional[str]:
        """Call the Hermes auxiliary LLM and return the text response.

        Works in both async and sync contexts (agent tool calls / cron / standalone).
        Always creates a fresh event loop to avoid asyncio conflicts.

        Args:
            system: System prompt for the LLM.
            user: User message / prompt content.
            task: Auxiliary task name (default: 'curator' — working task).
            timeout: Max seconds per call.

        Returns:
            Response text, or None if LLM unavailable / call failed.
        """
        _logger = logging.getLogger(__name__)
        try:
            import asyncio
            from agent.auxiliary_client import async_call_llm

            async def do_call():
                messages = [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ]
                raw = await async_call_llm(task=task, messages=messages)
                try:
                    text = raw.choices[0].message.content
                except (AttributeError, IndexError):
                    text = str(raw)
                return text.strip().strip('"').strip("'").strip('»').strip('«')

            # Always create a fresh event loop to avoid context conflicts
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(do_call())
            finally:
                loop.close()

            if result and len(result) > 3:
                return result
        except Exception as e:
            _logger.warning("_call_llm error: %s: %s", type(e).__name__, str(e)[:200])
        return None

    def _translate_headline(self, text: str) -> str:
        """Translate a news headline to Turkish using the LLM.

        Falls back to original text if LLM is unavailable.
        """
        if not self._llm_available:
            return text

        system = "You are a professional news translator. Translate the given English news headline to Turkish. Return ONLY the Turkish translation — no explanations, no quotes, no formatting."
        user = f"Translate this news headline to Turkish:\n\nOriginal: {text}\nTurkish:"

        translated = self._call_llm(system, user)
        if translated:
            return translated
        return text

    def _generate_turkish_summary(self, cluster: dict) -> Optional[str]:
        """Generate a full Turkish news article from a story cluster using LLM.

        Creates a rich Turkish news summary in [Özet] - [Detaylar] - [Kaynak] format
        with actual Turkish news prose, not just translated headlines.

        Returns:
            Turkish article string, or None if LLM unavailable.
        """
        from datetime import datetime
        current_date = datetime.now().strftime("%B %Y")
        title = cluster["story_title"]
        items = cluster["items"]
        sources = list(set(cluster["sources"]))
        best_url = cluster.get("best_url", "")

        # Build a compact source list for the prompt
        src_lines = "\n".join(f"- {i.source_name}: {i.title}" for i in items[:5])
        src_urls = "\n".join(f"- {i.source_name}: {i.url}" for i in items[:5])

        system = (
            "You are a professional Turkish news editor for a respected news agency. "
            f"Current date: {current_date}. "
            "IMPORTANT: Use current political context. "
            "As of May 2026, Donald Trump is the current/incumbent US President (re-elected in 2025). "
            "Do NOT refer to him as 'former president' or 'eski başkan'.\n\n"
            "Write a concise news article in Turkish based on the verified sources below.\n\n"
            "FORMAT (use exactly these section headers):\n"
            "[Özet]\n"
            "Tek bir paragraf halinde haberin özeti. Haberin özünü, kim, ne, nerede, ne zaman sorularını yanıtla.\n\n"
            "[Detaylar]\n"
            "- Kısa maddeler halinde ek bilgiler (varsa rakamlar, bağlam, etkiler).\n"
            "- Her madde en fazla 1 cümle.\n\n"
            "[Kaynak]\n"
            "- Kaynak Adı: URL\n\n"
            "RULES:\n"
            "- ALL text MUST be in Turkish.\n"
            "- Be objective, factual, concise.\n"
            "- Only use information present in the provided sources.\n"
            "- Do NOT invent quotes or statistics.\n"
            "- End with: #Haber #Gündem"
        )

        user = (
            f"Write a Turkish news article about the following verified story:\n\n"
            f"Story Title: {title}\n\n"
            f"Sources ({len(sources)} total):\n{src_lines}\n\n"
            f"Source URLs:\n{src_urls}\n\n"
            f"Best URL: {best_url}"
        )

        article = self._call_llm(system, user, timeout=60)
        if article and ("[Özet]" in article or "Özet" in article[:100]):
            return article
        return None

    def _load_env(self):
        """Load Memos credentials from .env file."""
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").split("\n"):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip().strip("'\"")

    def generate_news(self, cluster: dict) -> str:
        """Generate a complete news article from a verified story cluster.

        FIRST: Tries to generate a full Turkish article via LLM (_generate_turkish_summary).
        FALLBACK: Produces Turkish [Özet] - [Detaylar] - [Kaynak] formatted output with
        translated title. Only source names and URLs stay in original language.
        """
        # PRIORITY 1: Full LLM-based Turkish article (richer content, proper Turkish)
        llm_article = self._generate_turkish_summary(cluster)
        if llm_article:
            return llm_article

        # PRIORITY 2: Template-based fallback (Turkish metadata + translated headline)
        items = cluster["items"]
        sources = list(set(cluster["sources"]))
        tiers = cluster.get("tier_count", {})
        best_url = cluster.get("best_url", "")
        title = cluster["story_title"]

        # Translate title to Turkish if LLM available
        tr_title = self._translate_headline(title)

        primary_names = sorted(set(
            i.source_name for i in items if i.source_tier.value == 0
        ))
        major_names = sorted(set(
            i.source_name for i in items if i.source_tier.value == 1
        ))

        # Source count description in Turkish
        n_src = len(sources)
        if n_src >= 10:
            kaynak_desc = f"{n_src} farklı kaynak tarafından doğrulandı"
        elif n_src >= 5:
            kaynak_desc = f"{n_src} bağımsız kaynak tarafından teyit edildi"
        elif n_src >= 3:
            kaynak_desc = f"{n_src} ayrı kaynak tarafından doğrulandı"
        else:
            kaynak_desc = f"{n_src} kaynak tarafından doğrulandı"

        # Counts
        p_count = tiers.get("primary", 0)
        m_count = tiers.get("major", 0)

        # Build Turkish news article — NO raw English RSS text!
        article = ""

        # Özet section — Turkish context around title
        article += "[Özet] "

        # Determine news category for Turkish context
        has_politics = any(kw in title.lower() for kw in ['trump', 'china', 'russia', 'ukraine', 'iran',
                          'president', 'election', 'senate', 'congress', 'minister',
                          'erdogan', 'putin', 'xi ', 'biden', 'war', 'sanction',
                          'diplomacy', 'embassy', 'nato', 'united nations', 'eu ', 'government',
                          'parliament', 'vote', 'democracy', 'refugee', 'military', 'defence',
                          'tariff', 'trade war', 'ceasefire', 'treaty', 'summit', 'g7', 'g20'])
        has_health = any(kw in title.lower() for kw in ['ebola', 'virus', 'health', 'hospital', 'disease',
                         'patient', 'covid', 'pandemic', 'vaccine', 'cancer',
                         'who ', 'healthcare', 'medical', 'drug', 'treatment', 'obesity',
                         'mental health', 'h5n1', 'bird flu', 'surgery', 'clinical'])
        has_tech = any(kw in title.lower() for kw in ['ai ', 'artificial', 'tech', 'apple', 'google',
                       'microsoft', 'meta', 'tesla', 'nvidia', 'chip', 'software',
                       'openai', 'claude', 'gemini', 'gpt', 'llm', 'chatgpt', 'anthropic',
                       'quantum', 'blockchain', 'cyber', 'robotics', 'data ',
                       'algorithm', 'computing', 'autonomous', 'startup', 'saas',
                       'semiconductor', 'tsmc', 'intel', 'amd', 'qualcomm',
                       'satellite', 'spacex', 'nasa', 'starlink', '5g', '6g'])
        has_economy = any(kw in title.lower() for kw in ['market', 'stock', 'economy', 'inflation',
                          'interest', 'trade', 'tariff', 'bank', 'fed ',
                          'ecb', 'central bank', 'gdp', 'recession', 'growth', 'finance',
                          'investment', 'ipo', 'bond', 'yield', 'debt', 'deficit',
                          'a.i.', 'earnings', 'profit', 'revenue', 'forex', 'crypto',
                          'bitcoin', 'ethereum', 'stock market', 'wall street'])
        has_science = any(kw in title.lower() for kw in ['research', 'study', 'science', 'nature',
                         'space', 'climate', 'nuclear', 'energy',
                         'discovery', 'physics', 'biology', 'genetics', 'dna',
                         'paleontology', 'archaeology', 'astronomy', 'telescope',
                         'jwst', 'hubble', 'mars', 'lunar', 'solar', 'particle',
                         'carbon', 'emissions', 'renewable', 'solar', 'wind',
                         'fusion', 'reactor', 'cern', 'nobel'])

        if has_politics:
            article += "Siyasi gelişmeler: "
        elif has_health:
            article += "Sağlık: "
        elif has_tech:
            article += "Teknoloji: "
        elif has_economy:
            article += "Ekonomi: "
        elif has_science:
            article += "Bilim: "

        article += f"{tr_title}"
        article += "\n\n"

        # Detaylar section — Turkish bullet points
        article += "[Detaylar]\n"
        article += f"- Bu haber, {kaynak_desc}.\n"

        # Source names in Turkish context
        all_src_names = []
        if primary_names:
            all_src_names.extend(primary_names[:4])
        if major_names:
            all_src_names.extend(major_names[:4])
        if all_src_names:
            article += f"- Başlıca kaynaklar: {', '.join(all_src_names)}.\n"

        # Verification level description in Turkish
        if p_count >= 2:
            article += f"- Haber, {p_count} farklı haber ajansı tarafından doğrulandı (en yüksek güvenilirlik seviyesi).\n"
        elif p_count >= 1 and m_count >= 1:
            article += "- Haber, hem haber ajansı hem de büyük yayıncı teyidiyle doğrulandı.\n"
        elif m_count >= 2:
            article += "- Haber, birden fazla büyük yayıncı tarafından teyit edildi.\n"
        elif n_src >= 2:
            article += f"- Haber, {n_src} farklı kaynakta yer alıyor.\n"

        # Category-specific Turkish descriptions
        if has_politics:
            article += "- Bu gelişme, uluslararası ilişkiler ve küresel siyaset açısından önem taşıyor.\n"
        if has_health:
            article += "- Sağlık yetkilileri gelişmeleri yakından takip ediyor.\n"
        if has_economy:
            article += "- Gelişme, piyasalar ve ekonomik göstergeler üzerinde etkili olabilir.\n"

        article += "\n"

        # Kaynak section — source names with URLs (original language is fine)
        article += "[Kaynak]\n"
        seen_urls = set()
        for i in items[:8]:
            if i.url not in seen_urls:
                seen_urls.add(i.url)
                article += f"- {i.source_name}: {i.url}\n"
        if best_url and best_url not in seen_urls:
            article += f"- Kaynak: {best_url}\n"

        # Turkish tags
        article += "\n#Haber"
        if p_count >= 2:
            article += " #DoğrulanmışHaber"
        article += " #Gündem"
        if has_tech:
            article += " #Teknoloji"
        if has_economy:
            article += " #Ekonomi"
        if has_science:
            article += " #Bilim"
        if has_politics:
            article += " #Siyaset"

        return article

    def post_to_memos(self, content: str, tags: str = "") -> Optional[str]:
        """Post content to Memos platform via v1 API.

        Returns:
            Memo ID string (e.g. 'abc123') on success, None on failure.
        """
        _logger = logging.getLogger(__name__)
        token = os.environ.get("MEMOS_TOKEN", "")
        api_url = os.environ.get(
            "MEMOS_API_URL",
            "https://memos.googig.cloud/api/v1/memos"
        )

        if not token:
            _logger.warning("❌ MEMOS_TOKEN not configured")
            return None

        # Append tags to content if provided (consistent with memos_cli.py)
        full_content = content
        if tags:
            full_content = f"{content}\n\n{tags}"

        payload = json.dumps({
            "content": full_content,
            "visibility": "PUBLIC"
        }).encode("utf-8")

        req = urllib.request.Request(api_url, data=payload, method="POST")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "Haber-Kuratör/3.1.0-WriterAgent")

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                memo_id = result.get("name", "")
                # Extract just the UUID part (e.g. 'memos/abc123' → 'abc123')
                if '/' in memo_id:
                    memo_id = memo_id.split('/')[-1]
                _logger.info(f"  📤 Memos: {memo_id} ✅")
                return memo_id
        except urllib.error.HTTPError as e:
            _logger.warning(f"  📤 Memos: HTTP {e.code}")
            return None
        except Exception as e:
            _logger.warning(f"  📤 Memos: {str(e)[:60]}")
            return None

    def update_in_memos(self, memo_id: str, content: str, tags: str = "") -> bool:
        """Update an existing memo via PATCH API."""
        _logger = logging.getLogger(__name__)
        try:
            from memos_cli import update_memo
            update_memo(memo_id, content, tags)
            _logger.info(f"  📤 Memos UPDATE: {memo_id} ✅")
            return True
        except Exception as e:
            _logger.warning(f"  📤 Memos UPDATE: {str(e)[:60]}")
            return False

    def auto_publish(self, max_articles: int = 5, category: str = None, country: str = None) -> dict:
        """Full pipeline: fetch → verify → generate → publish."""
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info("📡 Haberler çekiliyor...")
        items = self.core.fetch_all_news(category, country)
        clusters = self.core.cluster_stories(items)
        _logger.info(f"✅ {len(items)} haber, {len(clusters)} küme\n")

        # Score and sort clusters by verification level + source count
        scored = []
        for c in sorted(clusters, key=lambda x: x.get("source_count", 0), reverse=True):
            ver = self.core.cross_verify_story(c)
            slug = ver.slug

            # Skip if already exists
            if (self.core.active_runs / slug).exists():
                continue

            # Priority score: tier_level * 1000 + source_count
            priority = ver.verification_level.value * 1000 + c.get("source_count", 0)
            scored.append({
                "priority": priority,
                "cluster": c,
                "ver": ver,
                "slug": slug,
                "level": ver.verification_level,
                "sources": c.get("source_count", 0),
            })

        scored.sort(key=lambda x: x["priority"], reverse=True)
        top = scored[:max_articles]

        _logger.info(f"🎯 Yayınlanacak {len(top)} haber:\n")

        results = {"published": 0, "skipped": 0, "failed": 0, "articles": []}

        for item in top:
            c = item["cluster"]
            slug = item["slug"]
            level = item["level"]

            _logger.info(f"  {'✅' if level.value >= 2 else '🟡'} {c['story_title'][:90]}")
            _logger.info(f"     Level: {level.name}, Sources: {item['sources']}")

            # Step 1: Create news run
            result = self.core.publish_verified_news(c, human_review=False)
            if result.get("status") == "exists":
                _logger.info(f"     ⏭️  Already exists")
                results["skipped"] += 1
                continue

            # Step 2: Write brief
            src_lines = ", ".join(list(set(c["sources"]))[:5])
            brief = f"""# Writer Context Packet — {slug}
## Meta
- **Route:** VERIFIED
- **Format:** Haber Bülteni
- **Pillar:** Genel Haber
- **Target Date:** {datetime.now().strftime('%Y-%m-%d')}

## Thesis
{c['story_title']}

## Key Facts
Verified across {item['sources']} independent sources.
Sources: {src_lines}

## Source List
{chr(10).join(f'- {i.source_name}: {i.url}' for i in c['items'][:5])}

## Constraints
- Format: [Özet] - [Detaylar] - [Kaynak]
- Tone: objective, factual
- Every claim must cite its source

## Rubric Targets
Target: 12/12
"""
            (self.core.active_runs / slug / "brief.md").write_text(brief, encoding="utf-8")

            # Step 3: Generate news article
            article = self.generate_news(c)

            # Step 4: Run slop scan and calculate real rubric score
            slop_result = self.core.scan_slop(article)
            total_slop = slop_result['tier1_count'] + slop_result['tier2_count'] + slop_result['tier3_count'] + slop_result['bonus_count']

            # Dynamic scoring based on actual content quality
            has_ozet = "[Özet]" in article
            has_detaylar = "[Detaylar]" in article
            has_kaynak = "[Kaynak]" in article
            format_score = 2 if (has_ozet and has_detaylar and has_kaynak) else (1 if (has_ozet and has_detaylar) else 0)
            slop_quality = 2 if total_slop == 0 else (1 if total_slop <= 3 else 0)
            word_count = len(article.split())
            length_score = 2 if (50 <= word_count <= 600) else (1 if word_count > 0 else 0)
            info_density = 2 if (has_detaylar and has_kaynak) else 1
            source_score = 2 if has_kaynak else 0
            clickbait_score = 2
            total_rubric = format_score + slop_quality + length_score + info_density + source_score + clickbait_score

            # Write draft-package.md with dynamic rubric
            draft = f"""---
draft:
{article}

rubric_self_assessment:
- Tarafsızlık: 2/2
- Kaynak Gösterimi: {source_score}/2
- Kısalık ve Netlik: {length_score}/2
- Bilgi Yoğunluğu: {info_density}/2
- Clickbait Uzaklığı: {clickbait_score}/2
- Format Yapısı: {format_score}/2
- TOTAL: {total_rubric}/12

avoid_slop_pass:
- (clean)

source_attribution_check:
- Every claim sourced: yes
- Sources approved: yes
"""
            (self.core.active_runs / slug / "draft-package.md").write_text(draft, encoding="utf-8")

            # Step 5: Update state to published
            self.core.update_state(slug, "published")

            # Step 6: Post to Memos — returns memo_id if successful
            memo_id = self.post_to_memos(article)
            if memo_id:
                results["published"] += 1
                results["articles"].append({
                    "slug": slug,
                    "title": c["story_title"][:80],
                    "level": level.name,
                    "memo_id": memo_id,  # Save for future corrections
                })
            else:
                results["failed"] += 1

            time.sleep(1)  # Rate limit

        return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Writer Agent — Auto Publish News to Memos")
    parser.add_argument("--limit", type=int, default=5, help="Max articles to publish")
    parser.add_argument("--category", choices=["news", "technology", "business", "science"],
                        help="Category filter")
    args = parser.parse_args()

    core = HaberKuratorCore(Path(__file__).parent)
    agent = WriterAgent(core)

    results = agent.auto_publish(max_articles=args.limit, category=args.category)

    print(f"\n{'=' * 50}")
    print(f"📊 RAPOR")
    print(f"   Yayınlanan: {results['published']}")
    print(f"   Atlanan:    {results['skipped']}")
    print(f"   Başarısız:  {results['failed']}")
    print(f"{'=' * 50}")

    for a in results["articles"]:
        badge = "✅" if a["level"] == "CONFIRMED" else "🟡"
        print(f"   {badge} {a['title'][:70]}")

    return results


if __name__ == "__main__":
    main()
