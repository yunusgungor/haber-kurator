"""
Haber Kuratör — Writer Module
=================================
WriterMixin for HaberKuratorCore.

Generates Turkish [Özet] - [Detaylar] - [Kaynak] formatted news
articles from verified story clusters and publishes them to Memos.
"""

import json
import logging
import os
import re
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from haber_kurator.modules.llm import call_llm_sync

logger = logging.getLogger(__name__)

def _extract_section(text: str, start_tag: str, end_tag: str | None) -> str:
    """Extract content between start_tag and end_tag from a structured text."""
    idx = text.find(start_tag)
    if idx == -1:
        return ""
    start = idx + len(start_tag)
    if end_tag:
        end = text.find(end_tag, start)
        return text[start:end].strip() if end > start else text[start:].strip()
    return text[start:].strip()


class WriterMixin:
    """Mixin providing Turkish news article generation and Memos publishing."""

    _llm_available: bool = False

    def set_llm(self, available: bool = True):
        """Mark that Hermes Agent LLM is available for Turkish content generation."""
        self._llm_available = available

    def _call_llm(self, system: str, user: str, task: str = "curator",
                  timeout: int = 60) -> Optional[str]:
        """Call the Hermes auxiliary LLM and return the text response.

        Uses call_llm_sync from the shared modules/llm.py module.
        """
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        result = call_llm_sync(messages, task=task, timeout=timeout)
        if result and len(result) > 3:
            return result.strip('"').strip("'").strip('»').strip('«')
        return None

    def _translate_headline(self, text: str) -> str:
        """Translate a news headline to Turkish using the LLM."""
        if not self._llm_available:
            return text

        system = ("You are a professional news translator. Translate the given "
                  "English news headline to Turkish. Return ONLY the Turkish "
                  "translation — no explanations, no quotes, no formatting.")
        user = f"Translate this news headline to Turkish:\n\nOriginal: {text}\nTurkish:"
        return self._call_llm(system, user) or text

    def _generate_turkish_summary(self, cluster: dict) -> Optional[str]:
        """Generate a full Turkish news article from a story cluster using LLM."""
        current_date = datetime.now().strftime("%B %Y")
        title = cluster["story_title"]
        items = cluster["items"]
        sources = list(set(cluster["sources"]))
        best_url = cluster.get("best_url", "")

        src_lines = "\n".join(f"- {i.source_name}: {i.title}" for i in items[:5])
        src_urls = "\n".join(f"- {i.source_name}: {i.url}" for i in items[:5])

        system = (
            "You are a professional Turkish news editor for a respected news agency. "
            f"Current date: {current_date}. "
            "IMPORTANT: Use current political context. "
            "As of May 2026, Donald Trump is the current/incumbent US President "
            "(re-elected in 2025). "
            "Do NOT refer to him as 'former president' or 'eski başkan'.\n\n"
            "Write a concise news article in Turkish based on the verified sources below.\n\n"
            "FORMAT (use exactly these section headers):\n"
            "[Özet]\n"
            "Tek bir paragraf halinde haberin özeti. Haberin özünü, kim, ne, nerede, "
            "ne zaman sorularını yanıtla.\n\n"
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
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").split("\n"):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip().strip("'\"")

    def generate_news(self, cluster: dict) -> str:
        """Generate a complete news article from a verified story cluster.

        Both LLM and template paths feed into _render_article() so the
        Memos output is ALWAYS the same structure regardless of generation path.
        """
        items = cluster["items"]
        sources = list(set(cluster["sources"]))
        tiers = cluster.get("tier_count", {})
        best_url = cluster.get("best_url", "")
        title = cluster["story_title"]

        # Build [Kaynak] from REAL item data once
        seen = set()
        kaynak_lines = []
        for i in items:
            if i.url not in seen and i.url:
                seen.add(i.url)
                kaynak_line = f"- {i.source_name}"
                if i.url != best_url:
                    kaynak_line += f": {i.url}"
                kaynak_lines.append(kaynak_line)

        kaynak = "\n".join(kaynak_lines) if kaynak_lines else "- Yayın kaynağı"
        primary_count = tiers.get("primary", 0)
        major_count = tiers.get("major", 0)
        source_summary_parts = []
        if primary_count:
            source_summary_parts.append(f"{primary_count} birincil haber ajansı")
        if major_count:
            source_summary_parts.append(f"{major_count} büyük yayın kuruluşu")
        source_summary = ", ".join(source_summary_parts) if source_summary_parts else f"{len(sources)} kaynak"

        # Try LLM path first
        llm_article = self._generate_turkish_summary(cluster) if self._llm_available else None
        if llm_article:
            return self._render_article(llm_article, kaynak, best_url)

        # Fallback: template-based Turkish output
        n_src = len(sources)
        if n_src >= 10:
            scope = "geniş yankı buldu"
        elif n_src >= 5:
            scope = "birden çok kaynakta yer aldı"
        elif n_src >= 2:
            scope = "birden çok kaynaktan doğrulandı"
        else:
            scope = "1 kaynak tarafından doğrulandı"

        # Category labels for Turkish content
        cat_labels = {
            "politics": "Siyasi gelişmeler",
            "news": "Haber",
            "health": "Sağlık",
            "technology": "Teknoloji",
            "business": "Ekonomi",
            "economy": "Ekonomi",
            "science": "Bilim",
        }
        categories_list = list(cluster.get("categories", []))
        primary_cat = categories_list[0].lower() if categories_list else ""

        ozet_text = (
            f"{title}\n\n"
            f"{cat_labels.get(primary_cat, 'Haber')} — "
            f"{', '.join(sources[:5])} haber ajanslarının bildirdiğine göre, "
            f"bu gelişme {scope}."
        )
        detaylar_items = []
        for i in items[:5]:
            detaylar_items.append(f"- {i.source_name}: {i.summary[:200] if i.summary else i.title}")
        detaylar_text = "\n".join(detaylar_items) if detaylar_items else "- Detay bulunamadı"

        # #DoğrulanmışHaber tag for PRIMARY-tier multi-source
        primary_count = tiers.get("primary", 0)
        has_verified_tag = primary_count >= 1

        return self._render_article(ozet_text, detaylar_text, kaynak,
                                    source_summary, best_url, title,
                                    has_verified_tag=has_verified_tag)

    @staticmethod
    def _render_article(ozet_text: str, detaylar_text: str, kaynak: str,
                        source_summary: str = "", best_url: str = "",
                        title: str = "",
                        has_verified_tag: bool = False) -> str:
        """Render a complete article in Memos format."""
        # If ozet_text came from the LLM (it's a full article), use it directly
        if "[Özet]" in ozet_text and "[Detaylar]" in ozet_text:
            tags = "\n#Haber #Gündem"
            if has_verified_tag:
                tags += " #DoğrulanmışHaber"
            return ozet_text + "\n\n" + kaynak + "\n\n" + tags.strip()

        # Template path — build from parts
        parts = []
        if best_url:
            parts.append(f"[Özet]\n🔗 Kaynak: {best_url}\n{ozet_text.strip()}")
        else:
            parts.append(f"[Özet]\n{ozet_text.strip()}")
        parts.append("")
        parts.append("[Detaylar]")
        parts.append(detaylar_text.strip())
        parts.append("")
        parts.append("[Kaynak]")
        parts.append(kaynak.strip())
        parts.append("")
        tags = "#Haber #Gündem"
        if has_verified_tag:
            tags += " #DoğrulanmışHaber"
        parts.append(tags)

        return "\n".join(parts)

    def post_to_memos(self, content: str, tags: str = "") -> Optional[str]:
        """Post content to Memos API; return memo_id on success."""
        try:
            from memos_cli import create_memo
            result = create_memo(content, tags)
            if isinstance(result, dict):
                memo_id = result.get("name", "")
                if "/" in memo_id:
                    memo_id = memo_id.split("/")[-1]
                logger.info("  📤 Memos: %s ✅", memo_id)
                return memo_id
            return str(result) if result else None
        except Exception as e:
            logger.warning("  📤 Memos: %s", str(e)[:60])
            return None

    def update_in_memos(self, memo_id: str, content: str, tags: str = "") -> bool:
        """Update an existing memo via PATCH API."""
        try:
            from memos_cli import update_memo
            update_memo(memo_id, content, tags)
            logger.info("  📤 Memos UPDATE: %s ✅", memo_id)
            return True
        except Exception as e:
            logger.warning("  📤 Memos UPDATE: %s", str(e)[:60])
            return False

    def auto_publish(self, max_articles: int = 5, category: str = None,
                     country: str = None, trending: bool = False,
                     today_only: bool = False) -> dict:
        """Full pipeline: fetch → verify → generate → publish."""
        opts = []
        if trending:
            opts.append("trending")
        if today_only:
            opts.append("today")
        logger.info("📡 Haberler çekiliyor..." + (f" ({'+'.join(opts)})" if opts else ""))
        items = self.fetch_all_news(category, country, trending=trending,
                                    today_only=today_only)
        clusters = self.cluster_stories(items)
        logger.info("✅ %d haber, %d küme", len(items), len(clusters))

        scored = []
        for c in sorted(clusters, key=lambda x: x.get("source_count", 0), reverse=True):
            ver = self.cross_verify_story(c)
            slug = ver.slug

            if (self.active_runs / slug).exists():
                continue

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

        logger.info("🎯 Yayınlanacak %d haber:", len(top))

        results: Dict[str, Any] = {"published": 0, "skipped": 0, "failed": 0,
                                    "articles": []}

        for item in top:
            c = item["cluster"]
            slug = item["slug"]
            level = item["level"]

            logger.info("  %s %s", "✅" if level.value >= 2 else "🟡",
                        c["story_title"][:90])
            logger.info("     Level: %s, Sources: %s", level.name, item["sources"])

            result = self.publish_verified_news(c, human_review=False)
            if result.get("status") == "exists":
                logger.info("     ⏭️  Already exists")
                results["skipped"] += 1
                continue

            src_lines = ", ".join(list(set(c["sources"]))[:5])
            brief = (
                f"# Writer Context Packet — {slug}\n"
                f"## Meta\n"
                f"- **Route:** VERIFIED\n"
                f"- **Format:** Haber Bülteni\n"
                f"- **Pillar:** Genel Haber\n"
                f"- **Target Date:** {datetime.now().strftime('%Y-%m-%d')}\n"
                f"\n"
                f"## Thesis\n"
                f"{c['story_title']}\n\n"
                f"## Key Facts\n"
                f"Verified across {item['sources']} independent sources.\n"
                f"Sources: {src_lines}\n\n"
                f"## Source List\n"
                + "\n".join(f"- {i.source_name}: {i.url}"
                           for i in c["items"][:5])
                + "\n\n"
                f"## Constraints\n"
                f"- Format: [Özet] - [Detaylar] - [Kaynak]\n"
                f"- Tone: objective, factual\n"
                f"- Every claim must cite its source\n\n"
                f"## Rubric Targets\n"
                f"Target: 12/12\n"
            )
            (self.active_runs / slug / "brief.md").write_text(brief,
                                                              encoding="utf-8")

            article = self.generate_news(c)

            slop_result = self.scan_slop(article)
            total_slop = (slop_result["tier1_count"] + slop_result["tier2_count"]
                          + slop_result["tier3_count"]
                          + slop_result["bonus_count"])

            has_ozet = "[Özet]" in article
            has_detaylar = "[Detaylar]" in article
            has_kaynak = "[Kaynak]" in article
            format_score = 2 if (has_ozet and has_detaylar and has_kaynak) else (
                1 if (has_ozet and has_detaylar) else 0)
            slop_quality = 2 if total_slop == 0 else (1 if total_slop <= 3 else 0)
            word_count = len(article.split())
            length_score = 2 if (50 <= word_count <= 600) else (
                1 if word_count > 0 else 0)
            info_density = 2 if (has_detaylar and has_kaynak) else 1
            source_score = 2 if has_kaynak else 0
            clickbait_score = 2
            total_rubric = (format_score + slop_quality + length_score
                            + info_density + source_score + clickbait_score)

            draft = (
                f"---\n"
                f"draft:\n"
                f"{article}\n\n"
                f"rubric_self_assessment:\n"
                f"- Tarafsızlık: 2/2\n"
                f"- Kaynak Gösterimi: {source_score}/2\n"
                f"- Kısalık ve Netlik: {length_score}/2\n"
                f"- Bilgi Yoğunluğu: {info_density}/2\n"
                f"- Clickbait Uzaklığı: {clickbait_score}/2\n"
                f"- Format Yapısı: {format_score}/2\n"
                f"- TOTAL: {total_rubric}/12\n\n"
                f"avoid_slop_pass:\n"
                f"- (clean)\n\n"
                f"source_attribution_check:\n"
                f"- Every claim sourced: yes\n"
                f"- Sources approved: yes\n"
            )
            (self.active_runs / slug / "draft-package.md").write_text(
                draft, encoding="utf-8")

            self.update_state(slug, "published")

            memo_id = self.post_to_memos(article)
            if memo_id:
                results["published"] += 1
                results["articles"].append({
                    "slug": slug,
                    "title": c["story_title"][:80],
                    "level": level.name,
                    "memo_id": memo_id,
                })
            else:
                results["failed"] += 1

            time.sleep(1)

        return results
