---
name: haber-kurator
description: "News Verification Engine v3.1.0 — Simplified news-only architecture. Multi-source fetch → cross-verify → publish → correct. Powered by Reuters, AP, AFP, BBC with 4-tier credibility and 8-state lifecycle."
version: 3.1.0
category: productivity
author: "Memos Küratörü"
tags: [news, verification, fact-check, journalism, curation, Reuters, AP, AFP, BBC, multi-source, cross-reference]
triggers:
  - "haber sistemi nasıl çalışır"
  - "haber doğrulama"
  - "news verification"
  - "fact check"
  - "çok kaynaklı haber"
  - "güvenilir haber nasıl üretilir"
  - "haber kaynakları"
  - "haber doğrulama motoru"
  - "news curation system"
  - "cross verification"
  - "haber-kurator nedir"
allowed_toolsets: [web, terminal, file, delegation, session_search, cronjob]
---

# Haber Kuratör v3.1.0 — News Verification Engine (News Only)

## Safe Refactor Notice

All non-news features (ORIGINAL, REPURPOSE, REWRITE, RESEARCH+IDEATE routes, idea gate, brief/draft/verify-draft/score/voice/signal/postmortem/learnings/patterns) have been **removed** in v3.1.0 to create a pure news verification system.

## Architecture

```
NEWS SOURCES (42+ sources, 4 tiers)
    │
    ▼
fetch_all_news()      ← RSS aggregation from Reuters, AP, AFP, BBC, etc.
    │
    ▼
cluster_stories()     ← Cross-language keyword overlap clustering
    │
    ▼
cross_verify_story()  ← 4-tier credibility scoring
    │
    ▼
create_news_run()     ← Fact-check report + run creation
    │
    ▼
auto_publish()        ← WriterAgent → Memos publish
```

## 8-State Lifecycle

```
captured → fact_checking → cross_verified → published → correction_needed → corrected/retracted → archived
```

## CLI Komutları (News Only)

- `hermes haber fetch [--category]` — Fetch & cluster news
- `hermes haber verify [--category]` — Cross-verify
- `hermes haber publish [--category] [--auto]` — Publish verified
- `hermes haber auto-publish [--limit]` — Full auto pipeline
- `hermes haber correct <slug> [--retract]` — Issue correction
- `hermes haber hallucination <slug>` — Hallucination check
- `hermes haber search <query>` — Search runs
- `hermes haber sources` — List sources
- `hermes haber status/audit/setup/runs/archive`

## Telegram Slash Commands

```
/haber fetch          → Fetch & cluster
/haber verify         → Cross-verify
/haber publish        → Publish verified
/haber correct        → Issue correction
/haber hallucination  → Hallucination scan
/haber ara            → News search
/haber sources        → List sources
/haber status/audit/setup/runs/archive
/haber auto-publish   → WriterAgent auto-publish
```

## Version History

- v3.1.0 — **News only refactor**: removed all non-news features (ORIGINAL/REPURPOSE/REWRITE/RESEARCH+IDEATE routes, idea gate, voice/signal/learnings/patterns, brief/draft/verify/score). Simplified to 8-state lifecycle, pure news pipeline.
- v3.0.0 — News Verification Engine: multi-source RSS, cross-verification, 4-tier credibility, hallucination guard, correction workflow.
- v2.4.0 — Legacy Content-OS fork with non-news routes.

> **Bu bir haber sistemidir.** Sonuçlar gerçek olmalı, sahte haber infiale yol açmaz.
> Dünyanın önde gelen, doğruluğu kanıtlanmış medya kaynaklarından haber çeker,
> çapraz doğrulama yapar ve kaynak atıflarıyla yayınlar.

---

## 🎯 Sistemin Özü

```
KAYNAKLAR ──► TOPLAMA ──► KÜMELEME ──► ÇAPRAZ DOĞRULAMA ──► FACT-CHECK ──► YAZIM ──► YAYIN
(Reuters,   (RSS/Atom  (Aynı haber   (2+ kaynakta     (Her iddia      (Sadece      (Kaynak
 AP, AFP,    besleme)   farklı         doğrulama)       kaynak          kaynaktaki   atıflarıyla
 BBC...)                kaynaktan)                       atıflı)         bilgiler)    Memos'a)
```

---

## 📡 Kaynak Güvenilirlik Kademeleri

Sistem, her haber kaynağını 4 kademede sınıflandırır (v3.1.0: 38 kaynak):

| Kademe | Açıklama | Örnekler | Doğrulama Etkisi |
|--------|----------|---------|------------------|
| **Tier 0 (PRIMARY)** | Wire servisler — en yüksek güvenilirlik | Reuters, AP, AFP, BBC | 2+ Tier 0 → **CONFIRMED** (otomatik) |
| **Tier 1 (MAJOR)** | Büyük yayıncılar | Bloomberg, WSJ, FT, NYT, Guardian, WaPo, CNN, NBC, Fox | 1 Tier 0 + 1 Tier 1 → **HIGH CONFIDENCE** |
| **Tier 2 (SPECIALIZED)** | Uzman yayıncılar | Nature, MIT Tech Review, Wired | 2+ Tier 1 → **MEDIUM CONFIDENCE** |
| **Tier 3 (SUPPLEMENTARY)** | Yerel kaynaklar | AA, Euronews TR, BBC Türkçe | Tek kaynak → **LOW CONFIDENCE** (insan onayı zorunlu) |

**Kural:** Hiçbir haber kaynaksız veya tek kaynaklı olarak doğrudan yayınlanamaz.

---

## 🔄 Çalışma Prensibi — Adım Adım

### 1. HABER TOPLAMA (`fetch`)
```
hermes haber fetch
/haber fetch
```
Tüm Tier 0-1 kaynaklarından RSS/Atom beslemeleri otomatik çekilir.
URL ve başlık bazında tekilleştirme yapılır.

### 2. KÜMELEME & DOĞRULAMA (`verify`)
```
hermes haber verify
/haber verify
```
Aynı haber farklı kaynaklardan gelirse kümelenir (kelime örtüşmesi ≥%40).
Her küme için:
- Kaç kaynak bildiriyor?
- Hangi güvenilirlik kademesindeler?
- Varsa tutarsızlıklar neler?

**Cross-Verification Seviyeleri:**
- ✅ **CONFIRMED** (Level 3): 2+ Tier 0 kaynak → otomatik onay
- 🟡 **HIGH CONFIDENCE** (Level 2): 1 Tier 0 + 1+ Tier 1 → güvenli
- 🟠 **MEDIUM CONFIDENCE** (Level 1): 2+ Tier 1 → insan kontrolü
- 🔴 **LOW CONFIDENCE** (Level 0): Tek kaynak → İNSAN ONAYI ZORUNLU
- ⛔ **UNVERIFIED**: Güvenilir kaynak yok → yayınlanamaz

### 3. NEWS RUN OLUŞTURMA (`publish`)
```
hermes haber publish
/haber publish
```
Doğrulanan haberler otomatik `runs/active/` klasörüne eklenir.
İçerik:
- `haber-object.md` — ID, state, route, verification level
- `idea.md` — Hangi kaynaklardan geldiği
- `fact-check-report.md` — Çapraz doğrulama raporu (YENİ)
- `context.md` — Writer için kaynak özeti

### 4. WRITER AGENT (Otomatik Yayın)
```
/haber auto-publish [--limit 5]
```
WriterAgent, doğrulanmış haberleri otomatik olarak [Özet] - [Detaylar] - [Kaynak] formatında oluşturup Memos'a yayınlar.
- Her iddia kaynak atıflı
- Sadece kaynaktaki bilgiler kullanılır
- Slop taraması + dinamik rubrik skoru ile kalite kontrol

### 5. HALÜSİNASYON TARAMASI
```
/haber hallucination <slug>
```
Yayın öncesi otomatik halüsinasyon kontrolü:
- Kaynaksız istatistik/rakam
- Spekülatif dil ("could mean", "might indicate")
- Atıfsız alıntılar
- Doğrulanmamış iddialar

### 6. DÜZELTME (Correction)
```
/haber correct <slug> "hata açıklaması"
/haber correct <slug> --retract
```
Yayın sonrası hata tespit edilirse:
- **Correction:** Hata düzeltilir, güncel sürüm yayınlanır
- **Retraction:** Haber tamamen geri çekilir (ciddi hatalarda)

---

## 📋 State Makinesi — 8 Aşama (News Only)

```
captured → fact_checking → cross_verified → published
→ correction_needed → corrected / retracted → archived
```

---

## 📁 Klasör Yapısı

```
haber-kurator/
├── strategy/
│   ├── source-watchlist.md     ← 26+ güvenilir kaynak (TIER 0-3)
│   ├── positioning.md
│   ├── audience.md
│   └── pillars.md
├── voice/
│   ├── voice-profile.md        ← Haber odaklı üslup kuralları
│   └── master-avoid-slop.md    ← 54+ slop kalıbı
├── runs/active/{slug}/
│   ├── haber-object.md         ← State, route, verification level
│   ├── fact-check-report.md    ← Cross-verification raporu
│   ├── context.md              ← Writer context
│   └── correction.md           ← Düzeltme/retraction
├── references/
└── tests/
```

---

## Kullanım Komutları

### Haber Toplama & Doğrulama
```
/hermes haber fetch [--category news|technology|business|science]
/hermes haber verify [--category ...] [--limit 10]
/hermes haber publish [--category ...] [--limit 5] [--auto]
/hermes haber sources
```

### Halüsinasyon & Düzeltme
```
/hermes haber hallucination <slug>
/hermes haber correct <slug> "hata" --info "doğru"
/hermes haber correct <slug> --retract
```

### Otomatik Yayın & Sistem
```
/hermes haber auto-publish [--limit 5]
/hermes haber status
/hermes haber audit
/hermes haber runs
/hermes haber archive <slug>
/hermes haber setup
```
