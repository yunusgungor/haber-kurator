#!/usr/bin/env python3
"""Measure embedding-based clustering quality vs keyword-overlap (Jaccard).

Test pairs: 5 same-story (cross-source, sometimes cross-language),
5 different-story. Reports accuracy at best threshold.
Output format parseable by the methodology gate.
"""

import json
import re
import sys
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# ── Test pairs: (title_a, title_b, expected_same) ──
# 5 same-story (cross-source, cross-language) + 5 different-story
TEST_PAIRS = [
    # SAME-STORY pairs (expected_same = True)
    ("Fed keeps interest rates steady at 4.5%, signals cautious approach to 2025",
     "Fed faiz oranını %4.5'te sabit tuttu, 2025'e temkinli sinyal",
     True),
    ("Powerful 7.1 magnitude earthquake strikes Japan's Ishikawa prefecture",
     "Japonya'da 7.1 büyüklüğünde deprem: Ishikawa prefektörlüğü sarsıldı",
     True),
    ("SpaceX successfully launches Starship on fifth test flight, booster caught by tower",
     "SpaceX, Starship'i beşinci test uçuşunda başarıyla fırlattı, güçlendirici yakalandı",
     True),
    ("US Senate passes $1.2 trillion infrastructure bill with bipartisan support",
     "ABD Senatosu 1.2 trilyon dolarlık altyapı yasasını iki partili destekle geçirdi",
     True),
    ("Apple unveils iPhone 16 Pro with AI-powered features, A18 chip",
     "Apple, yapay zeka özellikleri ve A18 çipiyle iPhone 16 Pro'yu tanıttı",
     True),
    # DIFFERENT-STORY pairs (expected_same = False)
    ("Manchester City wins Premier League title after dramatic final day",
     "NASA's Perseverance rover discovers ancient microbial fossils on Mars",
     False),
    ("Bitcoin price surges past $100,000 for the first time in history",
     "WHO declares new variant of concern as COVID-19 cases rise globally",
     False),
    ("OPEC+ agrees to cut oil production by 2 million barrels per day",
     "Real Madrid signs record-breaking sponsorship deal with tech giant",
     False),
    ("European Central Bank raises interest rates to combat rising inflation",
     "Netflix launches ad-supported tier, adds 5 million new subscribers",
     False),
    ("Germany announces $50 billion investment in renewable energy infrastructure",
     "Los Angeles Lakers win NBA championship in five-game series victory",
     False),
]


def seed_measure(seed: int = 42) -> None:
    np.random.seed(seed)


def keyword_overlap(title_a: str, title_b: str) -> float:
    """Jaccard similarity between two titles (used by current cluster_stories)."""
    a_words = set(re.sub(r'[^\w\s]', ' ', title_a.lower()).split())
    b_words = set(re.sub(r'[^\w\s]', ' ', title_b.lower()).split())
    a_words = {w for w in a_words if len(w) >= 3}
    b_words = {w for w in b_words if len(w) >= 3}
    intersection = a_words & b_words
    union = a_words | b_words
    if not union:
        return 0.0
    return len(intersection) / len(union)


def main() -> None:
    seed_measure()

    # Load lightweight embedding model
    model = SentenceTransformer("all-MiniLM-L6-v2")

    # Compute embeddings for all titles
    all_titles = []
    for a, b, _ in TEST_PAIRS:
        all_titles.append(a)
        all_titles.append(b)

    embeddings = model.encode(all_titles, normalize_embeddings=True)
    n = len(TEST_PAIRS)

    correct_jaccard = 0
    correct_embedding = 0
    jaccard_results = []
    embedding_results = []

    for i in range(n):
        a_emb = embeddings[i * 2]
        b_emb = embeddings[i * 2 + 1]
        sim = float(cosine_similarity([a_emb], [b_emb])[0][0])

        title_a = TEST_PAIRS[i][0]
        title_b = TEST_PAIRS[i][1]
        jacc = keyword_overlap(title_a, title_b)
        expected = TEST_PAIRS[i][2]

        jaccard_results.append((jacc, expected))
        embedding_results.append((sim, expected))

    # Find best threshold for embedding
    best_emb_acc = 0.0
    best_emb_threshold = 0.5
    for threshold in np.arange(0.1, 1.0, 0.02):
        correct = sum(
            1 for sim, expected in embedding_results
            if (sim >= threshold) == expected
        )
        acc = correct / n
        if acc > best_emb_acc:
            best_emb_acc = acc
            best_emb_threshold = threshold

    # Jaccard accuracy at its best threshold
    best_jacc_acc = 0.0
    best_jacc_threshold = 0.3
    for threshold in np.arange(0.05, 1.0, 0.02):
        correct = sum(
            1 for jacc, expected in jaccard_results
            if (jacc >= threshold) == expected
        )
        acc = correct / n
        if acc > best_jacc_acc:
            best_jacc_acc = acc
            best_jacc_threshold = threshold

    # Print detailed results
    print("=" * 72)
    print("EMBEDDING CLUSTERING QUALITY MEASUREMENT")
    print("=" * 72)
    print(f"Pairs: {n} (5 same-story, 5 different-story)")
    print(f"Model: all-MiniLM-L6-v2")
    print()

    print(f"{'Pair':<6} {'Jaccard':<9} {'Embedding':<10} {'Expected':<9} {'Jaccard OK':<10} {'Emb OK':<9}")
    print("-" * 56)
    for i in range(n):
        jacc, expected = jaccard_results[i]
        sim, _ = embedding_results[i]
        j_ok = (jacc >= best_jacc_threshold) == expected
        e_ok = (sim >= best_emb_threshold) == expected
        print(f"{i + 1:<6} {jacc:<9.3f} {sim:<10.3f} {str(expected):<9} {str(j_ok):<10} {str(e_ok):<9}")

    print()
    print("─" * 72)
    print("BEST THRESHOLDS & ACCURACY")
    print("─" * 72)
    print(f"Jaccard best threshold: {best_jacc_threshold:.2f}")
    print(f"Jaccard best accuracy:  {best_jacc_acc:.2f}  ({int(best_jacc_acc * n)}/{n})")
    print(f"Embedding best threshold: {best_emb_threshold:.2f}")
    print(f"Embedding best accuracy:  {best_emb_acc:.2f}  ({int(best_emb_acc * n)}/{n})")

    embedding_clustering_quality = best_emb_acc

    print()
    print("─" * 72)
    print("GATE METRIC")
    print("─" * 72)
    print(f"metric_embedding_clustering_quality={embedding_clustering_quality:.2f} ({int(embedding_clustering_quality * n)}/{n})")
    print(f"threshold=0.85")

    # Save raw data
    raw_dir = Path("docs/experiments/E-017/raw")
    raw_dir.mkdir(parents=True, exist_ok=True)
    with open(raw_dir / "measurement.json", "w") as f:
        json.dump({
            "pairs": [
                {
                    "title_a": a,
                    "title_b": b,
                    "expected": e,
                    "jaccard": round(jaccard_results[i][0], 4),
                    "embedding_similarity": round(embedding_results[i][0], 4),
                }
                for i, (a, b, e) in enumerate(TEST_PAIRS)
            ],
            "best_jaccard_threshold": round(best_jacc_threshold, 2),
            "best_jaccard_accuracy": round(best_jacc_acc, 2),
            "best_embedding_threshold": round(best_emb_threshold, 2),
            "best_embedding_accuracy": round(best_emb_acc, 2),
        }, f, indent=2, ensure_ascii=False)

    sys.exit(0 if embedding_clustering_quality >= 0.85 else 1)


if __name__ == "__main__":
    main()
