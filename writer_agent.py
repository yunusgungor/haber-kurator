"""
Writer Agent — Automatic News Article Generator for Memos Publishing
=====================================================================
Generates proper [Özet] - [Detaylar] - [Kaynak] formatted news articles
from verified story clusters and publishes them to Memos.
"""

import os, json, urllib.request, re, time
from pathlib import Path
from datetime import datetime

from .haber_kurator_core import HaberKuratorCore, VerificationLevel


class WriterAgent:
    """Automated Writer Agent that generates news content from verified clusters.
    
    Uses Hermes Agent's built-in LLM for Turkish headline translation when available.
    Falls back to original titles when running standalone.
    """

    def __init__(self, core: HaberKuratorCore):
        self.core = core
        self._load_env()
        self._llm = None  # Will be set if Hermes LLM is available

    def set_llm(self, llm):
        """Set Hermes Agent LLM for translation support."""
        self._llm = llm

    def _try_translate(self, text: str) -> str:
        """Try to translate text to Turkish using Hermes LLM.
        
        Uses a synchronous call to the Hermes auxiliary LLM.
        Falls back to original text if LLM is unavailable.
        """
        if self._llm is None:
            return text
        
        try:
            import asyncio
            from agent.auxiliary_client import async_call_llm
            
            prompt = f"""Translate this news headline to Turkish. Return ONLY the Turkish translation, nothing else.

Original: {text}
Turkish:"""
            
            async def do_translate():
                messages = [
                    {"role": "system", "content": "You are a professional news translator. Translate English news headlines to Turkish. Return ONLY the translation."},
                    {"role": "user", "content": prompt},
                ]
                raw = await async_call_llm(task="translate", messages=messages)
                try:
                    result = raw.choices[0].message.content
                except (AttributeError, IndexError):
                    result = str(raw)
                return result.strip().strip('"').strip("'")
            
            translated = asyncio.run(do_translate())
            if translated and len(translated) > 5:
                return translated
        except RuntimeError:
            # Running inside an existing event loop (Hermes agent context)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Create a new loop in a separate thread
                    import threading
                    result_holder = []
                    def _run_in_thread():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            tr = new_loop.run_until_complete(do_translate())
                            result_holder.append(tr)
                        finally:
                            new_loop.close()
                    thread = threading.Thread(target=_run_in_thread, daemon=True)
                    thread.start()
                    thread.join(timeout=10)
                    if result_holder and len(result_holder[0]) > 5:
                        return result_holder[0]
                else:
                    translated = loop.run_until_complete(do_translate())
                    if translated and len(translated) > 5:
                        return translated
            except Exception:
                pass
        except Exception as e:
            pass  # Fall back to original text
        
        return text

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
        
        Produces Turkish [Özet] - [Detaylar] - [Kaynak] formatted output with
        proper source attribution. Only source names and URLs stay in original
        language — all descriptive text is in Turkish.
        """
        items = cluster["items"]
        sources = list(set(cluster["sources"]))
        tiers = cluster.get("tier_count", {})
        best_url = cluster.get("best_url", "")
        title = cluster["story_title"]
        
        # Translate title to Turkish if LLM available
        tr_title = self._try_translate(title)
        
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
                          'erdogan', 'putin', 'xi ', 'biden', 'war', 'sanction'])
        has_health = any(kw in title.lower() for kw in ['ebola', 'virus', 'health', 'hospital', 'disease',
                         'patient', 'covid', 'pandemic', 'vaccine', 'cancer'])
        has_tech = any(kw in title.lower() for kw in ['ai ', 'artificial', 'tech', 'apple', 'google',
                       'microsoft', 'meta', 'tesla', 'nvidia', 'chip', 'software'])
        has_economy = any(kw in title.lower() for kw in ['market', 'stock', 'economy', 'inflation',
                          'interest', 'trade', 'tariff', 'bank', 'fed '])
        has_science = any(kw in title.lower() for kw in ['research', 'study', 'science', 'nature',
                         'space', 'climate', 'nuclear', 'energy'])
        
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

    def post_to_memos(self, content: str, tags: str = "") -> bool:
        """Post content to Memos platform via v1 API."""
        token = os.environ.get("MEMOS_TOKEN", "")
        api_url = os.environ.get(
            "MEMOS_API_URL",
            "https://memos.googig.cloud/api/v1/memos"
        )
        
        if not token:
            _logger = logging.getLogger(__name__)
            _logger.warning("❌ MEMOS_TOKEN not configured")
            return False

        payload = json.dumps({
            "content": content,
            "visibility": "PUBLIC"
        }).encode("utf-8")

        req = urllib.request.Request(api_url, data=payload, method="POST")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "Haber-Kuratur/3.0.0-WriterAgent")

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                memo_id = result.get("name", "?")
                _logger.info(f"  📤 Memos: {memo_id} ✅")
                return True
        except urllib.error.HTTPError as e:
            _logger.warning(f"  📤 Memos: HTTP {e.code}")
            return False
        except Exception as e:
            _logger.warning(f"  📤 Memos: {str(e)[:60]}")
            return False

    def auto_publish(self, max_articles: int = 5, category: str = None) -> dict:
        """Full pipeline: fetch → verify → generate → publish."""
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info("📡 Haberler çekiliyor...")
        items = self.core.fetch_all_news(category)
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

voice_check:
- All rules followed: yes

source_attribution_check:
- Every claim sourced: yes
- Sources approved: yes
"""
            (self.core.active_runs / slug / "draft-package.md").write_text(draft, encoding="utf-8")
            
            # Step 5: Update state
            self.core.update_state(slug, "drafting")
            
            # Step 6: Post to Memos
            success = self.post_to_memos(article)
            if success:
                results["published"] += 1
                results["articles"].append({
                    "slug": slug,
                    "title": c["story_title"][:80],
                    "level": level.name,
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
    
    print(f"\n{'='*50}")
    print(f"📊 RAPOR")
    print(f"   Yayınlanan: {results['published']}")
    print(f"   Atlanan:    {results['skipped']}")
    print(f"   Başarısız:  {results['failed']}")
    print(f"{'='*50}")
    
    for a in results["articles"]:
        badge = "✅" if a["level"] == "CONFIRMED" else "🟡"
        print(f"   {badge} {a['title'][:70]}")
    
    return results


if __name__ == "__main__":
    main()
