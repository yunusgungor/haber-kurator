# Haber-Kuratör v3.1.0 — Kapsamlı Kullanım Kılavuzu

> **Çok kaynaklı haber doğrulama ve yayın motoru.**
> 40+ küresel ve Türk güvenilir kaynaktan RSS beslemeleriyle haber toplar,
> aynı haberleri otomatik kümeler, 2+ bağımsız kaynakta çapraz doğrular
> ve kaynak atıflarıyla Memos platformuna yayınlar.

**Yazar:** Memos Küratörü
**Lisans:** MIT
**Versiyon:** 3.1.0
**Teknolojiler:** Python 3.11+, Hermes Agent Plugin Sistemi, RSS/Atom XML, Memos REST API

---

## İçindekiler

1. [Sistem Mimarisi](#1-sistem-mimarisi)
2. [Veri Modeli ve Sınıf Yapısı](#2-veri-modeli-ve-sınıf-yapısı)
3. [Kurulum ve Yapılandırma](#3-kurulum-ve-yapılandırma)
4. [Uçtan Uca Çalışma Döngüsü](#4-uçtan-uca-çalışma-döngüsü)
5. [Kaynak Güvenilirlik Sistemi](#5-kaynak-güvenilirlik-sistemi)
6. [Çapraz Doğrulama Algoritması](#6-çapraz-doğrulama-algoritması)
7. [Kümeleme ve Çapraz Dil Desteği](#7-kümeleme-ve-çapraz-dil-desteği)
8. [8-State News Lifecycle](#8-8-state-news-lifecycle)
9. [Halüsinasyon Koruması](#9-halüsinasyon-koruması)
10. [120+ Slop Tespit Kalıbı](#10-120-slop-tespit-kalıbı)
11. [Writer Agent ve Otomatik Haber Üretimi](#11-writer-agent-ve-otomatik-haber-üretimi)
12. [Düzeltme ve Geri Çekme Mekanizması](#12-düzeltme-ve-geri-çekme-mekanizması)
13. [State Cache ve Persistence](#13-state-cache-ve-persistence)
14. [Memos Yayınlama](#14-memos-yayınlama)
15. [Tam Komut Referansı](#15-tam-komut-referansı)
16. [Adım Adım Örnek Senaryo](#16-adım-adım-örnek-senaryo)
17. [Sık Sorulan Sorular ve Hata Çözümleri](#17-sık-sorulan-sorular-ve-hata-çözümleri)

---

## 1. Sistem Mimarisi

### 1.1 Genel Akış Diyagramı

```
                    KAYNAK KATMANI (Source Layer)
                    ┌──────────────────────────────────────────┐
                    │  Tier 0: Reuters, AP, AFP, BBC            │
                    │  Tier 1: Bloomberg, WSJ, FT, NYT, AA...   │  ← 40+ kaynak
                    │  Tier 2: Nature, Verge, Wired, T24...    │    4 güven kademesi
                    └──────────┬───────────────────────────────┘
                               │ RSS/Atom HTTP GET
                               ▼
                     TOPLAMA (fetch_all_news)
                    ┌──────────────────────────────────────────┐
                    │  • Her kaynağın RSS URL'lerine istek      │
                    │  • XML çözümleme (RSS 2.0 + Atom)         │
                    │  • Başlık/URL/tarih/özet çıkarma          │
                    │  • URL bazında deduplikasyon              │
                    │  • Promosyon içerik filtreleme            │
                    │  • Hatalı kaynakları atla + log           │
                    └──────────┬───────────────────────────────┘
                               ▼
                     KÜMELEME (cluster_stories)
                    ┌──────────────────────────────────────────┐
                    │  • Cross-lingual normalizasyon            │
                    │  • Kelime örtüşmesi ≥ %30                │
                    │  • Türkçe↔İngilizce eşleştirme           │
                    │    (savaş→war, ekonomi→economy)          │
                    │  • En yüksek tier'dan başlık seçimi      │
                    │  • Kaynak sayısına göre sıralama         │
                    └──────────┬───────────────────────────────┘
                               ▼
                  ÇAPRAZ DOĞRULAMA (cross_verify_story)
                 ┌─────────────────────────────────────────────┐
                 │  • İddia çıkarma (NER + sayısal + fiil)     │
                 │  • Çok kaynaklı teyit (weighted score)      │
                 │  • Sayısal tutarsızlık tespiti              │
                 │  • VerificationLevel ataması                │
                 │  • Detaylı rapor (fact-check-report.md)     │
                 └──────────┬──────────────────────────────────┘
                            │
             ┌──────────────┴──────────────┐
             │                              │
     verification_level ≥ 1          verification_level < 1
     (CONFIRMED/HIGH/MEDIUM)         (LOW/UNVERIFIED)
             │                              │
             ▼                              ▼
    ┌──────────────────┐          ┌──────────────────┐
    │  create_news_run │          │  İnsan onayı     │
    │  → cross_verified│          │  gerekli         │
    └────────┬─────────┘          └──────────────────┘
             │
             ▼
    ┌──────────────────────────────────────────────────────┐
    │                  PRODUKSİYON PIPELINE                 │
    │                                                      │
    │  cross_verified → published                          │
    │        │              │                              │
    │        │     ┌────────┴────────┐                     │
    │        │     │ hallucination   │                     │
    │        │     │ check + slop    │                     │
    │        │     │ scan            │                     │
    │        │     └─────────────────┘                     │
    │        │              │                              │
    │        ▼              ▼                              │
    │  correction.md  draft-package.md + Memos POST        │
    └──────────────────────────────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────────────────────┐
    │              YAYIN SONRASI (Post-Publication)         │
    │                                                      │
    │  published → correction_needed → corrected/retracted │
    │                                                │     │
    │                                          archived    │
    └──────────────────────────────────────────────────────┘
```

### 1.2 Python Katman Mimarisi

```
hermes_plugins.haber_kurator (namespace package)
│
├── __init__.py                  ← Plugin giriş noktası (v3.1.0)
│   • register(ctx)             ← Hermes plugin API'sine kayıt
│   • ctx.register_tool()       ← haber_kurator_manager, retriever, memos_publisher
│   • ctx.register_command()    ← /haber slash command
│   • ctx.register_cli_command() ← hermes haber CLI ağacı
│   • ctx.register_hook()       ← on_session_start, post_tool_call
│   • ctx.register_skill()      ← SKILL.md
│
├── haber_kurator_core.py       ← Ana motor (~3740 satır)
│   • HaberKuratorCore sınıfı   ← Tüm iş mantığı
│   • Veri modelleri            ← NewsSource, FactClaim, FetchedNewsItem
│   • Enum'lar                  ← SourceTier, VerificationLevel
│   • Sabitler                  ← NEWS_SOURCES (40+ kaynak), STATE_LIFECYCLE, FULL_SLOP_TIER1/2/3/BONUS
│
├── cli.py                      ← CLI handler (~280 satır)
│   • register_cli()            ← Argparse ağacı kurulumu
│   • handler(args)             ← 15 alt komut dağıtıcısı
│
├── writer_agent.py             ← Otomatik haber yazma ajanı (~445 satır)
│   • WriterAgent sınıfı        ← generate_news(), auto_publish(), post_to_memos()
│
├── memos_cli.py                ← Memos REST API istemcisi
│   • post_memo()               ← POST /api/v1/memos
│   • load_env()                ← .env dosyasından MEMOS_TOKEN okuma
│
├── SKILL.md                    ← Hermes Agent skill tanımı
├── plugin.yaml                 ← Plugin manifest (v3.1.0)
│
├── strategy/                   ← Stratejik dokümanlar
│   ├── source-watchlist.md     ← 40+ kaynak listesi (tier, RSS, notlar)
│   ├── positioning.md          ← Konumlandırma cümlesi
│   ├── audience.md             ← Hedef kitle profili
│   └── pillars.md              ← İçerik sütunları
│
├── voice/                      ← Üslup kuralları
│   ├── voice-profile.md        ← 5 prensip, yasaklı kalıplar, format
│   └── master-avoid-slop.md    ← Tier 1-3 slop kalıpları
│
├── runs/active/{slug}/         ← Aktif haber run'ları
│   ├── haber-object.md         ← State, route, verification level
│   ├── idea.md                 ← Kaynak listesi
│   ├── fact-check-report.md    ← Çapraz doğrulama raporu
│   ├── context.md              ← Writer için kaynak özeti
│   ├── brief.md                ← Writer Context Packet
│   ├── draft-package.md        ← Taslak + self-assessment
│   ├── verifier-report.md      ← Denetim raporu
│   ├── feedback.md             ← Yayın sonrası geri bildirim
│   └── correction.md           ← Düzeltme/retraction kaydı
│
├── stores/                     ← İçerik depoları
│   ├── inbox.md                ← Fikir giriş kutusu
│   ├── ideas/                  ← Fikir dosyaları
│   ├── hooks/                  ← Başarılı açılış pattern'leri
│   ├── proof/                  ← Kanıt/metrik dosyaları
│   └── feedback/               ← Yayın sonrası analizler
│
├── workflows/                  ← Playbook'lar
│   ├── idea-to-published-post.md
│   ├── verifier-checklist.md
│   ├── scheduler-handoff.md
│   ├── feedback-loop.md
│   └── archiveling.md
│
├── references/                 ← Yardımcı dokümanlar
│   ├── rubric-template.md
│   ├── production-prompts.md
│   ├── avoid-slop-patterns.md
│   ├── setup-workflow.md
│   ├── audit-technique.md
│   └── skill-audit-checklist.md
│
├── tests/                      ← Pytest birim testleri (48 test)
│   ├── test_haber_kurator_core.py
│   └── conftest.py
│
└── .state_cache/               ← Otomatik oluşturulan state cache
    └── runs_state.json         ← JSON formatında state veritabanı
```

---

## 2. Veri Modeli ve Sınıf Yapısı

### 2.1 Temel Veri Tipleri

```python
@dataclass
class NewsSource:
    """Bir haber kaynağının metadata'sı."""
    name: str                    # Görünen ad (örn: "Reuters")
    base_url: str                # Ana sayfa URL'si
    category: str                # news, technology, business, science
    tier: SourceTier             # PRIMARY=0, MAJOR=1, SPECIALIZED=2
    rss_feeds: List[str]         # RSS/Atom besleme URL'leri
    language: str = "en"         # tr, en
    country: str = "global"
    notes: str = ""              # Açıklama ve güven notu
    
    @property
    def tier_name(self) -> str:
        return self.tier.confidence_label
```

```python
@dataclass
class FetchedNewsItem:
    """RSS'den çekilen tek bir haber öğesi."""
    title: str                   # Başlık
    url: str                     # Haber URL'si
    source_name: str             # Kaynak adı (örn: "Reuters")
    source_tier: SourceTier      # Kaynağın güven kademesi
    published: str               # Yayın tarihi (ham RSS metni)
    summary: str                 # Özet/description (max 300 karakter)
    category: str                # Kategori
    guid: str = ""               # RSS GUID (deduplikasyon için)
```

```python
@dataclass
class FactClaim:
    """Bir haberden çıkarılan tek bir iddia/factoid."""
    claim_text: str             # İddia metni
    source_name: str            # Hangi kaynak bildirdi
    source_url: str             # Kaynağın URL'si
    source_tier: SourceTier     # Kaynağın güven kademesi
    verified_by: List[str]      # Teyit eden diğer kaynaklar
    discrepancies: List[str]    # Çelişen raporlar
    is_verified: bool           # 2+ kaynak tarafından doğrulandı mı?
    verification_level: str     # confirmed / single_source / unverified
```

```python
@dataclass
class CrossVerificationResult:
    """Bir haber kümesinin çapraz doğrulama sonucu."""
    story_title: str
    slug: str
    claims: List[FactClaim]
    sources_checked: List[str]
    sources_agreed: List[str]
    sources_disagreed: List[str]
    verification_level: VerificationLevel
    verified_claims: int
    total_claims: int
    discrepancies_found: List[str]
    report: str                  # İnsan tarafından okunabilir rapor

    @property
    def is_safe_to_publish(self) -> bool:
        """Yayın eşiği kontrolü (min_verification_level=1)."""
        return self.verification_level.value >= 1
```

### 2.2 Enum'lar

```python
class SourceTier(Enum):
    """Kaynak güvenilirlik kademeleri."""
    PRIMARY = 0           # Reuters, AP, AFP, BBC
    MAJOR = 1             # Bloomberg, WSJ, FT, Guardian, NYT, WaPo...
    SPECIALIZED = 2       # Nature, MIT Tech Review, The Verge...
    SUPPLEMENTARY = 3     # (genişletilebilir)

    @property
    def weight(self) -> int:
        """Doğrulama skorlamasında kullanılan ağırlık."""
        return {0: 3, 1: 2, 2: 1, 3: 1}[self.value]
```

```python
class VerificationLevel(Enum):
    """Çapraz doğrulama güven seviyeleri."""
    CONFIRMED = 3         # 2+ Tier 0 kaynak → en yüksek güven
    HIGH_CONFIDENCE = 2   # 1 Tier 0 + 1+ Tier 1
    MEDIUM_CONFIDENCE = 1 # 2+ Tier 1 kaynak
    LOW_CONFIDENCE = 0    # Tek kaynak / Tier 2+ only
    UNVERIFIED = -1       # Doğrulanamaz → yayın engeli

    @property
    def can_publish(self) -> bool:
        return self.value >= CONFIG["min_verification_level"]  # ≥ 1
```

### 2.3 RunState (State Cache)

```python
@dataclass
class RunState:
    """Her run'ın state bilgisi. JSON cache'te tutulur."""
    slug: str
    title: str = ""
    state: str = "captured"         # 8-state lifecycle
    route: str = "VERIFIED"
    created: str = ""
    updated: str = ""
    source_type: str = "multi-source"
    verification_level: str = "unverified"
```

---

## 3. Kurulum ve Yapılandırma

### 3.1 Ön Koşullar

| Bileşen | Gereksinim |
|---------|-----------|
| Hermes Agent | v2.x+ (plugin sistemi ile) |
| Python | 3.11+ |
| Memos hesabı | API token ile |
| Paketler | rich (CLI çıktıları için) |
| İnternet | RSS beslemelerine erişim (TCP 80/443) |

### 3.2 Kurulum Adımları

```bash
# 1. Plugin'in etkin olduğunu kontrol et
hermes plugins list
# → haber-kurator enabled olarak görünmeli

# 2. Memos kimlik bilgilerini ayarla
echo 'MEMOS_TOKEN=your_memos_token' >> ~/.hermes/.env
echo 'MEMOS_API_URL=https://memos.googig.cloud/api/v1/memos' >> ~/.hermes/.env

# Veya plugin dizinine .env dosyası kopyala:
cp plugins/haber-kurator/.env.example plugins/haber-kurator/.env
# ve MEMOS_TOKEN'ı düzenle

# 3. Dizin yapısını oluştur
hermes haber setup

# 4. Sistem sağlık kontrolü
hermes haber audit
# Beklenen: "✅ Haber Kuratör v3.1.0 Audit: 0 active, 0 archived."
```

### 3.3 .env Dosya Yapısı

```bash
# plugins/haber-kurator/.env
MEMOS_TOKEN=hkp_xxxxxxxxxxxxxxxxxxxxxx
MEMOS_API_URL=https://memos.googig.cloud/api/v1/memos
```

**Önemli:** Memos API'si `User-Agent` header'ı gerektirir. `memos_cli.py` otomatik olarak `"Haber-Kuratör/3.1.0"` ekler.

### 3.4 Dizin Yapısı ve Setup

`hermes haber setup` komutu şu dizinleri oluşturur:

```
haber-kurator/
├── runs/active/          ← Aktif haber run'ları
├── runs/archive/         ← Arşivlenmiş run'lar
├── .state_cache/         ← State cache JSON dosyası
├── strategy/             ← İnsan tarafından doldurulacak
├── voice/                ← İnsan tarafından doldurulacak
├── stores/               ← İnsan tarafından doldurulacak
│   ├── ideas/
│   ├── hooks/
│   ├── proof/
│   └── feedback/
```

**`hermes haber audit`** komutu şunları kontrol eder:

| Kontrol | Ne Denetlenir |
|---------|---------------|
| ✅ Kritik dizinler | strategy, voice, stores, runs, workflows, references var mı? |
| ✅ Store alt dizinleri | ideas, hooks, proof, feedback var mı? |
| ⚠️ Strateji dosyaları | positioning.md, audience.md, pillars.md var mı? (opsiyonel) |
| ✅ Kaynak sayısı | Toplam kaynak, Tier 0, Tier 1 sayıları |
| ✅ Run sayısı | Aktif ve arşivlenmiş run sayıları |

---

## 4. Uçtan Uca Çalışma Döngüsü

### ══════════════════════════════════════════════════════════
### AŞAMA 1: Haber Toplama (fetch_all_news)
### ══════════════════════════════════════════════════════════

**Python metodu:** `HaberKuratorCore.fetch_all_news(category: str = None) → List[FetchedNewsItem]`

**CLI:** `hermes haber fetch [--category news|technology|business|science] [--limit N]`

**İç Çalışma Algoritması:**

```
fetch_all_news(category=None):
1. Filtreleme:
   - Eğer category verilmişse: sadece o kategorideki kaynakları kullan
   - Verilmemişse: tüm kaynaklar (40+)

2. RSS Çekme (sıralı):
   for each source in filtered_sources:
       for each feed_url in source.rss_feeds:
           GET feed_url
           timeout=5sn
           if hata: log + atla, sonraki kaynağa geç

3. XML Çözümleme:
   if RSS 2.0 (//item):
       title = item.findtext("title")
       link = item.findtext("link")
       pubDate = item.findtext("pubDate")
       description = item.findtext("description")
       guid = item.findtext("guid")
   elif Atom (//entry):
       title = entry.find("title").text
       link = entry.find("link").get("href")
       published = entry.find("published").text
       summary = entry.find("summary").text

4. Deduplikasyon:
   - URL bazında: aynı URL daha önce görüldüyse atla
   - Başlık bazında: normalize edilmiş başlık (lowercase + noktalama temiz) daha önce görüldüyse atla

5. Promosyon Filtreleme:
   - (?:discount|promo|code|coupon|voucher|save\\s+\\d+%|...)
   - Başlıkta bu pattern'ler varsa atla

6. Dönüş: FetchedNewsItem listesi
```

**RSS Zaman Aşımı ve Hata Yönetimi:**

- Her besleme için `timeout=5` saniye (`CONFIG["rss_timeout"]`)
- XML Parse Hatası (`ET.ParseError`): atlanır, loglanır
- Ağ Hatası (`urllib.error.URLError`, `HTTPError`): atlanır, loglanır
- **Tüm kaynaklar hata verirse:** boş liste döner, hata yükseltilmez

### ══════════════════════════════════════════════════════════
### AŞAMA 2: Kümeleme (cluster_stories)
### ══════════════════════════════════════════════════════════

**Python metodu:** `HaberKuratorCore.cluster_stories(items) → List[Dict]`

Detaylar için [Bölüm 7 — Kümeleme ve Çapraz Dil Desteği]'ne bakın.

### ══════════════════════════════════════════════════════════
### AŞAMA 3: Çapraz Doğrulama (cross_verify_story)
### ══════════════════════════════════════════════════════════

**Python metodu:** `HaberKuratorCore.cross_verify_story(cluster) → CrossVerificationResult`

**CLI:** `hermes haber verify [--category ...] [--limit N]`

Detaylar için [Bölüm 6 — Çapraz Doğrulama Algoritması]'na bakın.

### ══════════════════════════════════════════════════════════
### AŞAMA 4: News Run Oluşturma (publish_verified_news)
### ══════════════════════════════════════════════════════════

**Python metodu:** `HaberKuratorCore.publish_verified_news(cluster, human_review=True) → Dict`

**CLI:** `hermes haber publish [--category ...] [--limit N] [--auto]`

**Adım Adım:**

```
publish_verified_news(cluster, human_review=True):
1. create_news_run(cluster):
   a. cross_verify_story(cluster) → verification sonucu
   b. runs/active/{slug}/ klasörünü oluştur
   c. haber-object.md yaz:
      - ID, Created, Status=cross_verified/captured
      - Route=VERIFIED (güvenli) veya REWRITE (düşük güven)
      - Title, Verification Level, Verified Sources
   d. idea.md yaz: Story, Best Source URL, tüm kaynaklar
   e. fact-check-report.md yaz: verification raporu
   f. context.md yaz: Writer için kaynak özeti
   g. State cache'e ekle + persist et

2. Eğer zaten varsa: {"status": "exists"} dön

3. Eğer verification_level ≥ 2 ve human_review=False:
   - State otomatik: fact_checking → cross_verified → published
   - auto_advanced = True
```

**haber-object.md Formatı:**

```markdown
# Haber Nesnesi — 2026-05-israel-says-it-killed-hamas-s-top-leader-in-gaza

## Meta
- **ID:** 2026-05-israel-says-it-killed-hamas-s-top-leader-in-gaza
- **Created:** 2026-05-16T15:28:59.322940
- **Status:** cross_verified
- **Route:** VERIFIED
- **Source Type:** multi-source
- **Format:** Haber Bülteni
- **Pillar:** news
- **Title:** Israel Says It Killed Hamas's Top Leader in Gaza
- **Verification Level:** 3
- **Verified Sources:** 3

state: cross_verified
updated: 2026-05-16T15:37:16.092810
```

### ══════════════════════════════════════════════════════════
### AŞAMA 5: Writer Agent ile Otomatik Yayın
### ══════════════════════════════════════════════════════════

**CLI:** `hermes haber auto-publish [--limit N] [--category ...]`

WriterAgent.auto_publish() tam otomatik pipeline:

```
auto_publish(max_articles=5, category=None):
1. fetch_all_news(category) → haberleri çek
2. cluster_stories(items) → kümeler
3. Her küme için:
   a. cross_verify_story(cluster) → doğrula
   b. priority_score = verification_level * 1000 + source_count
4. En yüksek priority'den başlayarak sırala
5. Zaten var olan slug'ları atla (slug collision check)
6. İlk N haber için:
   a. publish_verified_news(human_review=False) → run oluştur
   b. Template brief yaz (Writer Context Packet)
   c. generate_news(cluster) → Türkçe [Özet]-[Detaylar]-[Kaynak] metni
   d. Draft package yaz (rubric + slop + attribution check)
   e. State: published
   f. post_to_memos() → Memos'a yayınla
   g. 1 saniye bekle (rate limit)
7. Rapor dön: {published, skipped, failed, articles[]}
```

### ══════════════════════════════════════════════════════════
### AŞAMA 6: Arşivleme
### ══════════════════════════════════════════════════════════

**CLI:** `hermes haber archive {slug} [--force]`

- Normal: state `published` sonrası arşivlenebilir
- `--force`: her state'te arşivler
- Arşivleme: `runs/active/{slug}` → `runs/archive/{slug}` taşınır
- State cache "archived" olarak güncellenir

---

## 5. Kaynak Güvenilirlik Sistemi

### 5.1 Kademe Tanımları

| Kademe | Değer | Ağırlık | Tanım |
|--------|-------|---------|-------|
| **PRIMARY** | 0 | 3 | Wire servis / haber ajansı |
| **MAJOR** | 1 | 2 | Büyük yayıncı / gazete |
| **SPECIALIZED** | 2 | 1 | Uzman / niş yayıncı |
| **SUPPLEMENTARY** | 3 | 1 | Yerel / bölgesel (genişletilebilir) |

### 5.2 Kaynak Listesi (40+)

**Tier 0 — PRIMARY (Wire Services):**

| Kaynak | Kategori | RSS Feed Sayısı |
|--------|----------|-----------------|
| Reuters | news | 3 |
| Associated Press (AP) | news | 3 |
| Agence France-Presse (AFP) | news | 1 |
| BBC News | news | 5 |

**Tier 1 — MAJOR (Major Outlets):**

| Kaynak | Kategori | Dil |
|--------|----------|-----|
| Bloomberg | business | EN |
| The Wall Street Journal | business | EN |
| Financial Times | business | EN |
| The Guardian | news | EN |
| The New York Times | news | EN |
| The Washington Post | news | EN |
| Al Jazeera English | news | EN |
| NPR | news | EN |
| The Economist | news | EN |
| CNBC | business | EN |
| Anadolu Ajansı (AA) | news | TR |
| BBC Türkçe | news | TR |
| Euronews Türkçe | news | TR |
| Deutsche Welle Türkçe | news | TR |
| Bloomberg HT | business | TR |

**Tier 2 — SPECIALIZED (Uzman Yayıncılar):**

| Kaynak | Kategori | Dil |
|--------|----------|-----|
| Nature | science | EN |
| MIT Technology Review | technology | EN |
| The Verge | technology | EN |
| Wired | technology | EN |
| Harvard Business Review | business | EN |
| ScienceDaily | science | EN |
| T24 | news | TR |
| Medyascope | news | TR |
| Gazete Duvar | news | TR |
| Diken | news | TR |
| BirGün | news | TR |
| Sözcü | news | TR |
| Cumhuriyet | news | TR |
| Hürriyet | news | TR |
| Webrazzi | technology | TR |

### 5.3 Çapraz Doğrulama Kuralları (Türkiye Haberleri)

| Senaryo | Minimum Doğrulama |
|----------|------------------|
| Uluslararası haber (Türkçe) | BBC Türkçe + Euronews TR veya 1 Tier 0 + 1 Türk kaynağı |
| Türkiye iç politika | AA + T24/Medyascope/Diken (2 bağımsız) |
| Ekonomi | Bloomberg HT + AA veya uluslararası Tier 1 |
| Teknoloji | Webrazzi + uluslararası Tier 2 veya 2 Türk kaynağı |

---

## 6. Çapraz Doğrulama Algoritması

### 6.1 Weighted Score Hesaplama

Her kaynağın ağırlığı `SourceTier.weight` ile belirlenir:
- PRIMARY = 3
- MAJOR = 2
- SPECIALIZED = 1

```python
# weighted_score = sum(her benzersiz kaynağın ağırlığı)
# primary_count = Tier 0 benzersiz kaynak sayısı
# major_count = Tier 1 benzersiz kaynak sayısı
# total_unique = toplam benzersiz kaynak sayısı
```

### 6.2 İddia Çıkarma (Claim Extraction)

Her haberin başlık + özetinden 3 tür iddia çıkarılır:

1. **Büyük Harfli Özel İsimler** (NER benzeri):
   ```
   r'\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,3}'
   ```
   - Kişi adları: "Donald Trump", "Joe Biden"
   - Kurum adları: "Associated Press", "BBC News"
   - Yer adları: "Washington", "Gaza"
   - Skip words filtrelenir: "The", "This", "That", "What"...

2. **Sayısal Değerler:**
   ```
   r'\d+(?:[.,]\d+)?\s*(?:%|percent|billion|million|dollars|...)'
   r'(?:202[0-9]|203[0-9])'  # Yıl
   ```

3. **Eylem Fiilleri:**
   ```
   r'(?:announced|launched|reported|confirmed|approved|killed|...)'
   ```

### 6.3 VerificationLevel Atama Mantığı

```python
if primary_count >= 2 and total_unique >= 2:
    level = CONFIRMED          # Level 3
elif primary_count >= 1 and major_count >= 1:
    level = HIGH_CONFIDENCE    # Level 2
elif major_count >= 2:
    level = MEDIUM_CONFIDENCE  # Level 1
elif total_unique >= 1:
    level = LOW_CONFIDENCE     # Level 0
else:
    level = UNVERIFIED         # Level -1

# Sayısal tutarsızlık varsa: bir kademe düşür
if discrepancies_list and level > LOW_CONFIDENCE:
    level = max(level - 1, LOW_CONFIDENCE)
```

### 6.4 Yayın Eşiği

| Seviye | Otomatik Yayın? |
|--------|-----------------|
| CONFIRMED (3) | ✅ Evet (`--auto` ile) |
| HIGH_CONFIDENCE (2) | ✅ Evet |
| MEDIUM_CONFIDENCE (1) | ⚠️ İnsan onayı önerilir |
| LOW_CONFIDENCE (0) | ❌ İnsan onayı ZORUNLU |
| UNVERIFIED (-1) | ❌ YAYINLANAMAZ |

---

## 7. Kümeleme ve Çapraz Dil Desteği

### 7.1 Normalizasyon

```python
def _cross_lingual_normalize(title: str) -> str:
    1. Küçük harfe çevir
    2. Noktalama işaretlerini kaldır
    3. Türkçe karakterleri ASCII'ye çevir (ışık→isik, ç→c, ğ→g, ...)
    4. İkili dil sözlüğünde ara:
       - "savaş" → "war", "saldırı" → "attack"
       - "ekonomi" → "economy", "enflasyon" → "inflation"
       - 50+ eşleştirme kuralı
    5. Ortak kelimeleri koru, diğerlerini olduğu gibi bırak
    6. Boşlukla birleştir
```

### 7.2 Kümeleme Eşiği

- **İngilizce-İngilizce:** kelime örtüşmesi ≥ %40
- **Türkçe-İngilizce:** kelime örtüşmesi ≥ %30

```python
overlap = len(set(norm_i_words) & set(norm_j_words))
min_len = min(len(norm_i_words), len(norm_j_words))
if min_len == 0: continue
score = overlap / min_len
if score >= 0.3:  # Aynı küme
    cluster.append(other_item)
```

### 7.3 İkili Dil Sözlüğü (Örnek)

| İngilizce | Türkçe | Normalize |
|-----------|--------|-----------|
| president | cumhurbaşkanı | president |
| attack | saldırı | attack |
| earthquake | deprem | earthquake |
| election | seçim | election |
| economy | ekonomi | economy |
| technology | teknoloji | technology |
| war | savaş | war |
| announced | açıkladı, duyurdu | announced |
| reported | bildirdi | reported |

---

## 8. 8-State News Lifecycle

### 8.1 State Tanımları ve Geçişler

```
STATE_LIFECYCLE = [
    "captured",           # Haber sisteme ilk giriş
    "fact_checking",      # Çapraz doğrulama devam ediyor
    "cross_verified",     # İddialar kaynaklarda doğrulandı
    "published",          # Memos'a yayınlandı
    "correction_needed",  # Hata tespit edildi (yayın sonrası)
    "corrected",          # Düzeltme yayınlandı
    "retracted",          # Haber geri çekildi
    "archived",           # Arşivlendi
]
```

### 8.2 Geçiş Kuralları

```
STATE_TRANSITIONS = {
    "captured":           ["fact_checking"],
    "fact_checking":      ["cross_verified", "captured"],
    "cross_verified":     ["captured", "published"],
    "published":          ["correction_needed", "archived"],
    "correction_needed":  ["corrected", "retracted"],
    "corrected":          ["archived"],
    "retracted":          ["archived"],
    "archived":           [],  # Terminal state
}
```

### 8.3 State Görüntüleme ve Değiştirme

```bash
# Tüm run'ların state'leri
hermes haber status

# State güncelleme (tool ile):
# haber_kurator_manager(action="update_state", slug="...", state="published")
```

State cache dosyası: `.state_cache/runs_state.json`

### 8.4 State-File Auto-Detection (sync_state)

`sync_state(slug)` dosya varlığına göre state'i otomatik algılar:

| Dosya | Tespit Edilen State |
|-------|---------------------|
| `correction.md` (Retraction içeriyorsa) | `retracted` |
| `correction.md` (Correction içeriyorsa) | `corrected` |
| `correction.md` (genel) | `correction_needed` |
| `fact-check-report.md` | `cross_verified` |
| Hiçbiri yoksa | `captured` |

---

## 9. Halüsinasyon Koruması

### 9.1 Tespit Edilen 4 Pattern

| # | Pattern | Regex | Severity | Ne kontrol eder? |
|---|---------|-------|----------|-----------------|
| 1 | Kaynaksız istatistik | `\$?\d+[\.\d,]*\s*(?:million\|billion\|...)` | 🔴 high | 200 karakter içinde kaynak adı var mı? |
| 2 | Spekülatif dil | `could (?:mean\|lead to\|result in)`, `might indicate`, `raises questions` | 🟡 medium | Gelecek hakkında tahmin mi? |
| 3 | Sahipsiz alıntı | `"([^"]{8,})"` | 🔴 high | `"..."` içinde konuşan adı var mı? |
| 4 | Muğlak atıf | `it is believed that`, `many think that`, `some argue that` | 🔴 high | Kim dedi? Spesifik kaynak var mı? |

### 9.2 URL Filtreleme (False Positive Koruması)

Sayı içeren satırda URL varsa (`https?://`), o satırdaki tüm sayılar atlanır.
Çünkü URL'lerdeki ID'ler (`g-s1-122453`), tarihler (`2026/05/16`) ve path segmentleri
anlamlı istatistik değil, sadece adres bileşenidir.

### 9.3 Skorlama

```
PASS: high severity bulgu = 0
FAIL: high severity bulgu ≥ 1
```

---

## 10. 120+ Slop Tespit Kalıbı

### 10.1 Kademeler

| Kademe | Pattern Sayısı | REVISE Eşiği | REJECT Eşiği |
|--------|---------------|-------------|-------------|
| 🔴 Tier 1 (Critical) | 45 | ≥1 pattern | ≥3 pattern |
| 🟡 Tier 2 (High) | 32 | ≥3 pattern | ≥5 pattern |
| 🟢 Tier 3 (Medium) | 31 | ≥8 pattern | ≥15 pattern |
| ⚪ Bonus (Tone) | 14 | Kontekst bazlı | — |

### 10.2 Tier 1 — Sıfır Tolerans (Haber)

Herhangi bir Tier 1 ihlali varsa otomatik **REVISE**:

```
1.  Promosyon/Clickbait: "groundbreaking", "game-changing"
2.  Önem abartısı: "pivotal", "testament"
3.  Belirsiz atıf: "experts believe", "studies show", "research suggests"
4.  Kaynaksız iddia: "allegedly", "unnamed sources say", "insiders reveal"
5.  Sahte aciliyet: "breaking:", "developing story", "this just in"
6.  Dolgu zarfları: "actually", "literally", "simply", "just", "basically"
7.  Staccato parçalama: kısa cümle dizileri
8.  Em Dash aşırı kullanımı
```

### 10.3 Tier 2 — Yüksek (3+ = REVISE)

```
1.  Copula Avoidance: "serves as", "stands as"
2.  -ing Padding: "leveraging", "implementing"
3.  Rule of Three Zorlama
4.  Filler Phrases: "due to the fact that", "in today's world"
5.  Generic Conclusions: "the future looks bright"
6.  Signposting: "let's dive in", "here's what you need"
7.  Hyperbolic Quantifiers: "every single", "never ever"
8.  Hedging: "it could potentially", "arguably"
```

### 10.4 Tier 3 — Orta (8+ = REVISE)

```
1.  Passive Voice (aşırı kullanım): "was noted", "were observed"
2.  Temporal Vagueness: "recently", "lately", "these days"
3.  False Balance: "some say... while others say"
4.  Rhetorical Questions: "have you ever wondered"
5.  Unnecessary Intensifiers: "very", "such"
6.  Clichéd Metaphors: "level up", "dive deep"
7.  False Precision: "exactly 45.67%"
```

### 10.5 Bonus Pattern'ler (Tone)

```
1.  Faux Authority: "you should", "you must"
2.  Vibes Over Data: "it feels like", "seems to me"
3.  Speculation as News: "could potentially mean", "raises questions about"
4.  Oversharing Backstory: "N years ago, I..."
5.  Under-Explaining Proof: "result: %word"
```

---

## 11. Writer Agent ve Otomatik Haber Üretimi

### 11.1 WriterAgent Sınıfı

```python
class WriterAgent:
    def __init__(self, core: HaberKuratorCore):
        self.core = core
        self._load_env()               # .env'den MEMOS_TOKEN oku
        self._llm = None               # Hermes LLM (opsiyonel)
    
    def set_llm(self, llm):           # Hermes auxiliary LLM bağla
    def _try_translate(self, text)    # İng→Tr çeviri (LLM ile)
    def generate_news(self, cluster)  # [Özet]-[Detaylar]-[Kaynak] üret
    def post_to_memos(self, content)  # Memos'a yayınla
    def auto_publish(self, ...)       # Tam otomatik pipeline
```

### 11.2 generate_news() Algoritması

```python
generate_news(cluster):
1. Başlık = cluster.story_title
2. Türkçeye çevir (LLM varsa)
3. Kategori tespiti (keywords):
   - siyaset: trump, china, russia, president, election...
   - sağlık: virus, health, hospital, covid, vaccine...
   - teknoloji: ai, apple, google, microsoft, nvidia, chip...
   - ekonomi: market, stock, economy, inflation, trade...
   - bilim: research, study, science, nature, space...
4. Kaynak sayısına göre Türkçe açıklama:
   - ≥10: "{N} farklı kaynak tarafından doğrulandı"
   - ≥5: "{N} bağımsız kaynak tarafından teyit edildi"
   - ≥3: "{N} ayrı kaynak tarafından doğrulandı"
   - else: "{N} kaynak tarafından doğrulandı"
5. [Özet] bölümü: Kategori etiketi + başlık
6. [Detaylar] bölümü:
   - Kaynak sayısı bilgisi
   - Başlıca kaynak isimleri (Tier 0 önce)
   - Doğrulama seviyesi açıklaması
   - Kategoriye özel detay
7. [Kaynak] bölümü: İlk 8 kaynağın ismi + URL
8. Tagler: #Haber #DoğrulanmışHaber #Gündem [+kategori]
```

### 11.3 Çıktı Formatı

```markdown
[Özet] Teknoloji: Apple yeni yapay zeka destekli iPhone'u tanıttı

[Detaylar]
- Bu haber, 5 farklı kaynak tarafından doğrulandı.
- Başlıca kaynaklar: Reuters, Associated Press (AP), BBC News.
- Haber, 2 haber ajansı tarafından teyit edildi (en yüksek seviye).

[Kaynak]
- Reuters: https://www.reuters.com/...
- Associated Press (AP): https://apnews.com/...
- BBC News: https://www.bbc.com/...

#Haber #DoğrulanmışHaber #Teknoloji #Gündem
```

### 11.4 Draft Package Formatı (WriterAgent çıktısı)

```
---
draft:
[Özet] ...
[Detaylar] ...
[Kaynak] ...

rubric_self_assessment:
- Tarafsızlık: 2/2
- Kaynak Gösterimi: 2/2
- Kısalık ve Netlik: 2/2
- Bilgi Yoğunluğu: 2/2
- Clickbait Uzaklığı: 2/2
- Format Yapısı: 2/2
- TOTAL: 12/12

avoid_slop_pass:
- (clean)

source_attribution_check:
- Every claim sourced: yes
- Sources approved: yes
---
```

---

## 12. Düzeltme ve Geri Çekme Mekanizması

### 12.1 Düzeltme (Correction)

```bash
# CLI ile
hermes haber correct {slug} "Hata açıklaması" --info "Doğru bilgi"

# Tool ile
# haber_kurator_manager(action="issue_correction", slug="...", 
#                       error_description="...", correct_information="...")
```

**Ne olur:**
1. `correction.md` oluşturulur (Correction Notice)
2. State `corrected` olarak güncellenir
3. Correction.md şablonu:

```markdown
# Correction Notice — slug
**Date:** 2026-05-16T...
**Type:** CORRECTION

## Error Description
...

## Correct Information
...

## Correction
The error has been corrected. We maintain our commitment to factual accuracy.
**Status:** CORRECTED
```

### 12.2 Geri Çekme (Retraction)

```bash
# CLI ile
hermes haber correct {slug} "Ciddi hata" --retract
```

**Ne zaman:**
- Haberin ana iddiası yanlış çıktıysa
- Kaynaklar haberi yalanladıysa
- Manipülasyon tespit edildiyse

**State geçişi:**
```
published → correction_needed → corrected/retracted → archived
```

### 12.3 State Geçişleri

```
published → correction_needed → corrected → archived
                                → retracted ↗
```

---

## 13. State Cache ve Persistence

### 13.1 Nasıl Çalışır?

Haber-Kuratör, state bilgilerini iki yerde tutar:
1. `runs/active/{slug}/haber-object.md` — Dosya sistemi (state: X)
2. `.state_cache/runs_state.json` — JSON cache (authoritative)

```json
{
  "2026-05-bir-haber-slugu": {
    "slug": "2026-05-bir-haber-slugu",
    "title": "Haber Başlığı",
    "state": "published",
    "route": "VERIFIED",
    "created": "2026-05-16T15:28:59.322940",
    "updated": "2026-05-16T15:37:16.092810",
    "source_type": "multi-source",
    "verification_level": "CONFIRMED"
  }
}
```

### 13.2 Avantajları

- **Plugin reload koruması:** Cache JSON dosyada saklanır, reload sonrası kaybolmaz
- **Hızlı erişim:** `get_state()` cache'ten okur, filesystem'e gitmez
- **Otomatik migrasyon:** `__init__`'te `_migrate_old_state()` eski run'ları otomatik tarar

---

## 14. Memos Yayınlama

### 14.1 API İsteği

```http
POST https://memos.googig.cloud/api/v1/memos
Authorization: Bearer {MEMOS_TOKEN}
Content-Type: application/json
User-Agent: Haber-Kuratör/3.1.0

{
  "content": "Haber metni...",
  "visibility": "PUBLIC"
}
```

### 14.2 Çevre Değişkenleri

| Değişken | Varsayılan | Açıklama |
|----------|-----------|----------|
| `MEMOS_TOKEN` | — | Zorunlu. Memos API token'ı |
| `MEMOS_API_URL` | `https://memos.googig.cloud/api/v1/memos` | Memos API base URL |

### 14.3 .env Dosya Konumu

Plugin `.env` dosyasını şu sırayla arar:
1. `plugins/haber-kurator/.env` (plugin dizini)
2. `~/.hermes/.env` (Hermes ana dizini)

---

## 15. Tam Komut Referansı

### 15.1 CLI Komutları (`hermes haber ...`)

**Haber Toplama & Doğrulama:**

| Komut | Açıklama | Örnek |
|-------|----------|-------|
| `sources` | Kaynakları kademelere göre listeler | `hermes haber sources` |
| `fetch [--category] [--limit]` | Haber çeker + kümeler + tablo gösterir | `hermes haber fetch --category technology --limit 10` |
| `verify [--category] [--limit]` | Çeker + kümeler + çapraz doğrular | `hermes haber verify --category news --limit 5` |
| `publish [--category] [--limit] [--auto]` | Doğrulanmış haberleri run'a ekler | `hermes haber publish --auto --limit 3` |
| `correct <slug> <hata> [--retract] [--info]` | Düzeltme/retraction yayınla | `hermes haber correct slug "hata" --info "doğru"` |
| `hallucination <slug>` | Halüsinasyon taraması | `hermes haber hallucination slug` |

**Writer Agent:**

| Komut | Açıklama | Örnek |
|-------|----------|-------|
| `auto-publish [--limit] [--category]` | Tam otomatik: fetch→verify→generate→publish | `hermes haber auto-publish --limit 5` |

**Sistem:**

| Komut | Açıklama |
|-------|----------|
| `setup` | Dizin yapısını başlat |
| `status` | Aktif run'ların state'leri |
| `audit` | Tam sistem denetimi |
| `runs [--no-archive]` | Tüm run'ları listele |
| `search <query>` | Run'larda ara |
| `archive <slug> [--force]` | Arşivle (`--force` ile state atla) |

### 15.2 Slash Komutlar (`/haber ...`)

| Komut | Açıklama |
|-------|----------|
| `fetch [kategori]` | 📡 Haber çek |
| `verify [kategori] [N]` | 🔍 Çapraz doğrula |
| `publish [kategori] [N] [--auto]` | 📰 Haberleri sisteme al |
| `auto-publish [N]` | 🤖 Writer Agent ile otomatik yayınla |
| `correct <slug>` | ✏️ Düzeltme |
| `hallucination <slug>` | 🔬 Halüsinasyon kontrolü |
| `sources` | 🌍 Kaynak listesi |
| `status` | 📋 Run durumu |
| `audit` | 🔍 Sistem sağlığı |
| `runs` | 📂 Tüm runlar |
| `ara/search <sorgu>` | 🔎 Haber ara |
| `setup` | 🚀 İlk kurulum |
| `archive <slug>` | 📦 Arşivle |

### 15.3 Tool Actions (`haber_kurator_manager`)

| Action | Parametreler | Açıklama |
|--------|-------------|----------|
| `setup` | — | Dizin yapısını başlat |
| `audit` | — | Sistem denetimi |
| `list` | `include_archived` | Run'ları listele |
| `sources` | — | Kaynakları listele |
| `fetch_news` | `category` | Haber çek + kümele |
| `search_news` | `search_query`, `max_results`, `language`, `country` | Haber ara |
| `verify_news` | `category`, `limit` | Çek + doğrula |
| `publish_verified` | `category`, `limit`, `human_review` | Yayınla |
| `cross_verify_story` | `cluster_data` | Spesifik kümeyi doğrula |
| `hallucination_check` | `slug` | Halüsinasyon tara |
| `scan_slop` | `text` | Slop tara |
| `check_correction` | `slug` | Düzeltme gerekli mi? |
| `issue_correction` | `slug`, `error_description`, `correct_information`, `retract` | Düzeltme yayınla |
| `update_state` | `slug`, `state` | State güncelle |
| `get_state` | `slug` | State oku |
| `sync_state` | `slug` | Filesystem'den state senkronize et |
| `get_next_actions` | `slug` | Sonraki adımları öner |
| `auto_publish` | `limit`, `category` | Writer Agent ile otomatik yayın |
| `search_runs` | `query` | Run'larda ara |
| `get_all_runs` | `include_archived` | Tüm run'lar |
| `archive_run` | `slug` | Arşivle |

### 15.4 Tool Actions (`haber_kurator_retriever`)

| Action | Parametreler | Açıklama |
|--------|-------------|----------|
| `sources` | — | Tüm kaynak metadata |
| `source_summary` | — | Kaynak özeti (tier bazlı) |
| `strategy` | — | Strateji dosyaları (positioning, audience, pillars, watchlist) |
| `voice` | — | Üslup profili + slop patterns |
| `run` | `slug` | Run dosyalarının tümü |
| `stores` | — | Store dosyaları |
| `learnings` | `topic` | Öğrenilen dersler |

### 15.5 Tool Action (`memos_publisher`)

| Parametre | Zorunlu | Açıklama |
|-----------|---------|----------|
| `content` | ✅ | Yayınlanacak haber metni |
| `visibility` | — | PUBLIC (varsayılan), PRIVATE, PROTECTED |
| `tags` | — | Virgülle ayrılmış etiketler |

---

## 16. Adım Adım Örnek Senaryo

### Senaryo: Teknoloji Haberi Doğrulama ve Yayınlama

```bash
# ── 1. Haberleri çek ──────────────────────────────────
hermes haber fetch --category technology --limit 10

# ── 2. En çok kaynaklı haberi detaylı doğrula ────────
hermes haber verify --category technology --limit 3

# ── 3. Güvenli haberleri run'a ekle ───────────────────
hermes haber publish --category technology --limit 3

# ── 4. Run'ları kontrol et ────────────────────────────
hermes haber status

# ── 5. Writer Agent ile otomatik yayınla ──────────────
hermes haber auto-publish --limit 3

# ── 6. Halüsinasyon kontrolü ──────────────────────────
hermes haber hallucination 2026-05-technology-slug

# ── 7. Arşivle (state published değilse --force ile) ──
hermes haber archive 2026-05-technology-slug --force
```

### Otomatik Pipeline (Tek Komut)

```bash
hermes haber auto-publish --limit 5 --category news
```

Bu komut: **fetch → cluster → verify → sort → dedup → create run → brief → draft → publish** adımlarının tamamını otomatik yapar.

### Haber Arama (Google News Üzerinden)

```bash
# CLI
hermes haber search "yapay zeka regülasyonu"

# Slash
/haber ara istanbulda kapkaça uğrayan kadın

# Tool
# haber_kurator_manager(action="search_news", search_query="...", 
#                       language="tr", country="TR")
```

---

## 17. Sık Sorulan Sorular ve Hata Çözümleri

### ❓ "Plugin 'haber_kurator' is not installed" hatası

Plugin adı tire ile: `haber-kurator`, alt çizgi ile değil:
```bash
hermes plugins enable haber-kurator
```

### ❓ "invalid choice: 'haber'" hatası

Plugin CLI komutları kayıtlı değil. İki olası neden:
1. **Absolute import hatası:** `__init__.py`'deki import'lar relative olmalı (`from .haber_kurator_core import...`)
2. **Handler bağlantısı eksik:** `cli.py`'de `haber_parser.set_defaults(func=handler)` çağrılmalı

### ❓ RSS beslemesi çalışmazsa?

- Hata alan beslemeler atlanır (log'a yazılır)
- 5 saniye timeout (CONFIG["rss_timeout"])
- Tüm kaynaklar hata verirse boş liste döner
- Kaynakları kontrol et: `hermes haber sources`

### ❓ "Number/statistic without clear source attribution" false positive

URL'lerdeki sayılar (`g-s1-122453`) kaynaksız istatistik sanılabilir. Sistem URL içeren satırlardaki tüm sayısal değerleri atlar.

### ❓ Hallüsinasyon testi sürekli FAIL veriyor?

Template-based draft kullanıyorsanız normaldir. LLM destekli oluşturmayı deneyin (Hermes içinde).

### ❓ Memos'a yayın başarısız?

1. `MEMOS_TOKEN` ayarlı mı?
2. API URL doğru mu? `https://memos.googig.cloud/api/v1/memos`
3. Token'da yetki var mı? (`visibility: PUBLIC`)
4. `.env` dosyası doğru yerde mi? (plugin dizini veya `~/.hermes/`)

### ❓ "Cannot archive" hatası

Run'ı arşivlemek için state `published` olabilir ancak `--force` her state'te arşivler:
```bash
hermes haber archive SLUG --force
```

### ❓ State cache ile filesystem uyuşmazlığı

Cache authoritative'dir. Sync için:
```bash
grep "state:" runs/active/*/haber-object.md
cat .state_cache/runs_state.json | python3 -m json.tool
```

### ❓ Writer Agent hangi LLM'i kullanır?

Hermes auxiliary LLM (`agent.auxiliary_client.async_call_llm`). LLM yoksa template-based üretime düşer (orijinal başlık korunur, çeviri yapılmaz).

### ❓ Run sayısı çok arttı, performans düşer mi?

- Run'lar dosya sistemi üzerinde tutulur
- State cache JSON ile yönetilir
- 1000+ run için optimize
- Eski run'ları arşivleyin: `hermes haber archive SLUG`

### ❓ `--auto` güvenli mi?

Sadece CONFIRMED (Level 3) veya HIGH CONFIDENCE (Level 2) haberleri otomatik onaylar.
MEDIUM/LOW haberler her zaman insan onayı gerektirir.

### ❓ Kaynak nasıl eklenir?

`haber_kurator_core.py` → `NEWS_SOURCES` sözlüğüne yeni bir `NewsSource` eklenir:

```python
"kaynak_adi": NewsSource(
    name="Kaynak Adı",
    base_url="https://...",
    category="news",
    tier=SourceTier.MAJOR,
    rss_feeds=["https://...rss"],
    language="tr",
    country="turkey",
    notes="Açıklama",
),
```

---

> **Haber-Kuratör v3.1.0** — Memos Küratörü
> 40+ kaynak, 4 güven kademesi, 8-state news lifecycle, 120+ slop kalıbı
>
> **Dosya:** `plugins/haber-kurator/USER_GUIDE.md`
> **Skill:** Haber-Kuratör skill'ini yükleyip `hermes haber ...` komutlarını kullanın
