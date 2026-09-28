"""
Writer Agent — Backward-compatible wrapper around WriterMixin
===============================================================
Delegates to HaberKuratorCore (which now includes WriterMixin).
Kept for backward compatibility; new code should use core directly.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from haber_kurator_core import HaberKuratorCore


class WriterAgent:
    """Backward-compatible Writer Agent wrapping HaberKuratorCore.

    All generation logic is now in WriterMixin (modules/writer.py).
    This class exists so existing callers continue to work unchanged.
    """

    def __init__(self, core: HaberKuratorCore):
        self.core = core
        self._load_env()

    def _load_env(self):
        """Load credentials via WriterMixin's _load_env."""
        self.core._load_env()

    @property
    def _llm_available(self) -> bool:
        return self.core._llm_available

    @_llm_available.setter
    def _llm_available(self, value: bool):
        if value:
            self.core.set_llm(True)

    def set_llm(self, available: bool = True):
        """Mark that Hermes Agent LLM is available for Turkish content generation."""
        self.core.set_llm(available)

    def _call_llm(self, system: str, user: str, task: str = "curator",
                  timeout: int = 60) -> Optional[str]:
        return self.core._call_llm(system, user, task, timeout)

    def _translate_headline(self, text: str) -> str:
        return self.core._translate_headline(text)

    def _generate_turkish_summary(self, cluster: dict) -> Optional[str]:
        return self.core._generate_turkish_summary(cluster)

    def generate_news(self, cluster: dict) -> str:
        return self.core.generate_news(cluster)

    def post_to_memos(self, content: str, tags: str = "") -> Optional[str]:
        return self.core.post_to_memos(content, tags)

    def update_in_memos(self, memo_id: str, content: str,
                        tags: str = "") -> bool:
        return self.core.update_in_memos(memo_id, content, tags)

    def auto_publish(self, max_articles: int = 5, category: str = None,
                     country: str = None, trending: bool = False,
                     today_only: bool = False) -> dict:
        return self.core.auto_publish(
            max_articles=max_articles,
            category=category,
            country=country,
            trending=trending,
            today_only=today_only,
        )


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Writer Agent — Auto Publish News to Memos")
    parser.add_argument("--limit", type=int, default=5,
                        help="Max articles to publish")
    parser.add_argument("--category",
                        choices=["news", "technology", "business", "science"],
                        help="Category filter")
    args = parser.parse_args()

    core = HaberKuratorCore(Path(__file__).parent)
    agent = WriterAgent(core)

    results = agent.auto_publish(max_articles=args.limit,
                                 category=args.category)

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
