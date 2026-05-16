# Haber-Kuratör v3.0.0 — Kapsamlı Kullanım Kılavuzu

> **Çok kaynaklı haber doğrulama ve yayın motoru.**
> 35+ küresel güvenilir kaynaktan RSS beslemeleriyle haber toplar, aynı haberleri
> otomatik kümeler, 2+ bağımsız kaynakta çapraz doğrular ve kaynak atıflarıyla
> Memos platformuna yayınlar.

**Yazar:** Memos Küratörü
**Lisans:** MIT
**Teknolojiler:** Python 3.9+, Hermes Agent Plugin Sistemi, RSS/Atom XML, Memos REST API

---

## İçindekiler

1. [Sistem Mimarisi](#1-sistem-mimarisi)
2. [Veri Modeli ve Sınıf Yapısı](#2-veri-modeli-ve-sınıf-yapısı)
3. [Kurulum ve Yapılandırma](#3-kurulum-ve-yapılandırma)
4. [Uçtan Uca Çalışma Döngüsü](#4-uçtan-uca-çalışma-döngüsü)
5. [Kaynak Güvenilirlik Sistemi](#5-kaynak-güvenilirlik-sistemi)
6. [Çapraz Doğrulama Algoritması](#6-çapraz-doğrulama-algoritması)
7. [Kümeleme ve Çapraz Dil Desteği](#7-kümeleme-ve-çapraz-dil-desteği)
8. [Halüsinasyon Koruması](#8-halüsinasyon-koruması)
9. [54+ Slop Tespit Kalıbı](#9-54-slop-tespit-kalıbı)
10. [Writer Agent ve Otomatik Haber Üretimi](#10-writer-agent-ve-otomatik-haber-üretimi)
11. [18 Aşamalı State Makinesi](#11-18-aşamalı-state-makinesi)
12. [12 Puanlık Rubrik Değerlendirme](#12-12-puanlık-rubrik-değerlendirme)
13. [Düzeltme ve Geri Çekme Mekanizması](#13-düzeltme-ve-geri-çekme-mekanizması)
14. [Memos Yayınlama](#14-memos-yayınlama)
15. [Tam Komut Referansı](#15-tam-komut-referansı)
16. [Adım Adım Örnek Senaryo](#16-adım-adım-örnek-senaryo)
17. [Sık Sorulan Sorular ve Hata Çözümleri](#17-sık-sorulan-sorular-ve-hata-çözümleri)

---

## 1. Sistem Mimarisi

### 1.1 Genel Akış Diyagramı

```
                         KAYNAK KATMANI (Source Layer)
                         ┌─────────────────────────────────────┐
                         │  Tier 0: Reuters, AP, AFP, BBC      │
                         │  Tier 1: Bloomberg, WSJ, FT, NYT... │  ← 35+ kaynak
                         │  Tier 2: Nature, Verge, Wired...    │    4 güven kademesi
                         │  Tier 3: (genişletilebilir)         │
                         └──────────┬──────────────────────────┘
                                    │ RSS/Atom HTTP GET
                                    ▼
                          TOPLAMA (fetch_all_news)
                         ┌─────────────────────────────────────┐
                         │  • Her kaynağın RSS URL'lerine istek │
                         │  • XML çözümleme (RSS 2.0 + Atom)   │
                         │  • Başlık/URL/tarih/özet çıkarma    │
                         │  • URL bazında deduplikasyon        │
                         │  • Promosyon içerik filtreleme      │
                         │  • Hatalı kaynakları atla + log     │
                         └──────────┬──────────────────────────┘
                                    ▼
                          KÜMELEME (cluster_stories)
                         ┌─────────────────────────────────────┐
                         │  • Cross-lingual normalizasyon      │
                         │  • Kelime örtüşmesi ≥ %30           │
                         │  • Türkçe↔İngilizce eşleştirme      │
                         │    (savaş→war, ekonomi→economy)     │
                         │  • En yüksek tier'dan başlık seçimi │
                         │  • Kaynak sayısına göre sıralama    │
                         └──────────┬──────────────────────────┘
                                    ▼
                       ÇAPRAZ DOĞRULAMA (cross_verify_story)
                      ┌─────────────────────────────────────────┐
                      │  • İddia çıkarma (NER + sayısal + fiil) │
                      │  • Çok kaynaklı teyit (weighted score)  │
                      │  • Sayısal tutarsızlık tespiti          │
                      │  • VerificationLevel ataması            │
                      │  • Detaylı rapor (fact-check-report.md) │
                      └──────────┬──────────────────────────────┘
                                 │
              ┌──────────────────┴──────────────────┐
              │                                     │
      verification_level ≥ 1                 verification_level < 1
      (CONFIRMED/HIGH/MEDIUM)                (LOW/UNVERIFIED)
              │                                     │
              ▼                                     ▼
     ┌──────────────────┐                 ┌──────────────────┐
     │  create_news_run │                 │  İnsan onayı     │
     │  → cross_verified│                 │  gerekli         │
     └────────┬─────────┘                 └──────────────────┘
              │
              ▼
     ┌──────────────────────────────────────────────────────────┐
     │               PRODUKSİYON PIPELINE                       │
     │                                                          │
     │  brief_ready ─► drafting ─► verification ─► draft_review│
     │     │              │              │              │      │
     │     │              │     ┌────────┴────────┐     │      │
     │     │              │     │ hallucination   │     │      │
     │     │              │     │ check + slop    │     │      │
     │     │              │     │ scan            │     │      │
     │     │              │     └─────────────────┘     │      │
     │     ▼              ▼                             ▼      │
     │  brief.md    draft-package.md           verifier-report │
     └──────────────────────────────────────────────────────────┘
              │
              ▼
     ┌──────────────────┐
     │  published       │──► Memos REST API POST
     └────────┬─────────┘
              │
              ▼
     ┌──────────────────────────────────────────────────────────┐
     │         YAYIN SONRASI (Post-Publication)                 │
     │                                                          │
     │  feedback_24h → feedback_72h → learned → archived       │
     │       │              │             │                     │
     │       └──────┬───────┘             │                     │
     │              │                     │                     │
     │        correction_needed           │                     │
     │              │                     │                     │
     │         corrected/retracted        │                     │
     └──────────────────────────────────────────────────────────┘
```

### 1.2 Python Katman Mimarisi

```
hermes_plugins.haber_kurator (namespace package)
│
├── __init__.py                  ← Plugin giriş noktası
│   • register(ctx)             ← Hermes plugin API'sine kayıt
│   • ctx.register_tool()       ← haber_kurator_manager, retriever, memos_publisher
│   • ctx.register_command()    ← /haber slash command
│   • ctx.register_cli_command() ← hermes haber CLI ağacı
│   • ctx.register_hook()       ← on_session_start, post_tool_call
│   • ctx.register_skill()      ← SKILL.md
│
├── haber_kurator_core.py       ← Ana motor (~3900 satır)
│   • HaberKuratorCore sınıfı   ← Tüm iş mantığı
│   • Veri modelleri            ← NewsSource, FactClaim, FetchedNewsItem
│   • Enum'lar                  ← SourceTier, VerificationLevel
│   • Sabitler                  ← NEWS_SOURCES, STATE_LIFECYCLE, FULL_SLOP_TIER1/2/3
│
├── cli.py                      ← CLI handler (~1070 satır)
│   • register_cli()            ← Argparse ağacı kurulumu
│   • handler(args)             ← 28 alt komut dağıtıcısı
│
├── writer_agent.py             ← Otomatik haber yazma ajanı
│   • WriterAgent sınıfı        ← generate_news(), auto_publish(), post_to_memos()
│
├── memos_cli.py                ← Memos REST API istemcisi
│   • post_memo()               ← POST /api/v1/memos
│   • load_env()                ← .env dosyasından MEMOS_TOKEN okuma
│
├── SKILL.md                    ← Hermes Agent skill tanımı
├── plugin.yaml                 ← Plugin manifest
│
├── strategy/                   ← Stratejik dokümanlar
│   ├── source-watchlist.md     ← 35+ kaynak listesi (tier, RSS, notlar)
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
│   ├── workboard.md            ← Çalışma panosu
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
│   ├── KULLANIM_KILAVUZU.md
│   ├── rubric-template.md
│   ├── production-prompts.md
│   ├── avoid-slop-patterns.md
│   ├── setup-workflow.md
│   ├── audit-technique.md
│   └── skill-audit-checklist.md
│
└── .state_cache/               ← Otomatik oluşturulan state cache
    └── runs_state.json         ← JSON formatında state veritabanı
```

### 1.3 HaberKuratorCore Sınıfı Detayı

```python
class HaberKuratorCore:
    """
    Ana iş motoru. Tüm haber toplama, doğrulama, state yönetimi
    ve dosya işlemlerini yürütür.
    """
    
    # ── Constructor ──
    def __init__(self, root: Path):
        # Dizin yapısı
        self.root = root                    # Plugin kök dizini
        self.strategy = root / "strategy"
        self.voice = root / "voice"
        self.active_runs = root / "runs" / "active"
        self.archive = root / "runs" / "archive"
        self.stores = root / "stores"
        self.workflows = root / "workflows"
        self.references = root / "references"
        
        # Slop pattern listeleri (FULL_SLOP_TIER1/2/3 + BONUS)
        self.slop_tier1 = FULL_SLOP_TIER1   # 30+ kritik pattern
        self.slop_tier2 = FULL_SLOP_TIER2   # 30+ yüksek pattern
        self.slop_tier3 = FULL_SLOP_TIER3   # 30+ orta pattern
        self.slop_bonus = FULL_SLOP_BONUS   # 9 ton pattern'i
        
        # 35+ haber kaynağı (NEWS_SOURCES dict)
        self.sources = NEWS_SOURCES.copy()
        
        # State cache (JSON dosyası)
        self._state_cache: Dict[str, RunState] = {}
        self._load_state_cache()
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
    rss_feeds: List[str]        # RSS/Atom besleme URL'leri
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
    published: str               # Yayın tarihi (ham metin)
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
    verified_by: List[str]     # Teyit eden diğer kaynaklar
    discrepancies: List[str]   # Çelişen raporlar
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
        """Yayın eşiği kontrolü."""
        return self.verification_level.value >= CONFIG["min_verification_level"]  # ≥ 1
```

### 2.2 Enum'lar

```python
class SourceTier(Enum):
    """Kaynak güvenilirlik kademeleri."""
    PRIMARY = 0           # Reuters, AP, AFP, BBC
    MAJOR = 1             # Bloomberg, WSJ, FT, Guardian, NYT...
    SPECIALIZED = 2       # Nature, MIT Tech Review, The Verge...
    SUPPLEMENTARY = 3     # (henüz eklenmemiş)

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
    state: str = "captured"         # 18-state lifecycle
    route: str = "VERIFIED"
    format: str = "Haber Bülteni"
    pillar: str = "Genel Haber"
    created: str = ""
    updated: str = ""
    source_type: str = "multi-source"
    verification_level: str = "unverified"
```

---

## 3. Kurulum ve Yapılandırma

### 3.1 Ön Koşullar

| Bileşen | Gereksinim |
|---------|------------|
| Hermes Agent | v2.x+ (plugin sistemi ile) |
| Python | 3.9+ (3.11 önerilen) |
| Memos hesabı | API token ile |
| Paketler | rich (CLI çıktıları için) |
| İnternet | RSS beslemelerine erişim (TCP 80/443) |

### 3.2 Kurulum Adımları

```bash
# 1. Plugin'in etkin olduğunu kontrol et
hermes plugins list
# → haber-kurator enabled olarak görünmeli

# 2. Memos kimlik bilgilerini ayarla
# İki yöntemden biri:
echo 'MEMOS_TOKEN=your_memos_token' >> ~/.hermes/.env
echo 'MEMOS_API_URL=https://memos.googig.cloud/api/v1/memos' >> ~/.hermes/.env

# Veya plugin dizinine .env dosyası:
# plugins/haber-kurator/.env

# 3. Dizin yapısını oluştur
hermes haber setup

# 4. Sistem sağlık kontrolü
hermes haber audit
# Beklenen: "✅ Haber Kuratör v3.0.0 Audit: 0 active, 0 archived."
```

### 3.3 .env Dosya Yapısı

```bash
# ~/.hermes/.env veya plugins/haber-kurator/.env
MEMOS_TOKEN=hkp_xxxxxxxxxxxxxxxxxxxxxx
MEMOS_API_URL=https://memos.googig.cloud/api/v1/memos
```

**Önemli:** Memos API'si `User-Agent` header'ı gerektirir. `memos_cli.py` otomatik olarak `"Haber-Kuratör/3.0.0"` ekler.

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

`hermes haber audit` komutu şunları kontrol eder:

| Kontrol | Ne Denetlenir |
|---------|---------------|
| ✅ Kritik dizinler | strategy, voice, stores, runs, workflows var mı? |
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

#### İç Çalışma Algoritması

```
fetch_all_news(category=None):
1. Filtreleme:
   - Eğer category verilmişse: sadece o kategorideki kaynakları kullan
   - Verilmemişse: tüm kaynaklar
   
2. RSS Çekme (paralel olmayan sıralı):
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
   - (?:discount|promo|code|coupon|voucher|save\s+\d+%|...)
   - Başlıkta bu pattern'ler varsa atla
   
6. Dönüş: FetchedNewsItem listesi
```

#### RSS Zaman Aşımı ve Hata Yönetimi

- Her besleme için `timeout=5` saniye (`CONFIG["rss_timeout"]`)
- XML Parse Hatası (`ET.ParseError`): atlanır, loglanır
- Ağ Hatası (`urllib.error.URLError`, `HTTPError`): atlanır, loglanır
- **Tüm kaynaklar hata verirse:** boş liste döner, hata yükseltilmez
- Hata sayısı `logger.info` ile raporlanır

### ══════════════════════════════════════════════════════════
### AŞAMA 2: Kümeleme (cluster_stories)
### ══════════════════════════════════════════════════════════

**Python metodu:** `HaberKuratorCore.cluster_stories(items) → List[Dict]`

Bu adım detayları için [Bölüm 7 — Kümeleme ve Çapraz Dil Desteği]'ne bakın.

### ══════════════════════════════════════════════════════════
### AŞAMA 3: Çapraz Doğrulama (cross_verify_story)
### ══════════════════════════════════════════════════════════

**Python metodu:** `HaberKuratorCore.cross_verify_story(cluster) → CrossVerificationResult`

**CLI:** `hermes haber verify [--category ...] [--limit N]`

Bu adım detayları için [Bölüm 6 — Çapraz Doğrulama Algoritması]'na bakın.

### ══════════════════════════════════════════════════════════
### AŞAMA 4: News Run Oluşturma (publish_verified_news)
### ══════════════════════════════════════════════════════════

**Python metodu:** `HaberKuratorCore.publish_verified_news(cluster, human_review=True) → Dict`

**CLI:** `hermes haber publish [--category ...] [--limit N] [--auto]`

#### Adım Adım

```
publish_verified_news(cluster, human_review=True):
1. create_news_run(cluster):
   a. cross_verify_story(cluster) → verification sonucu
   b. runs/active/{slug}/ klasörünü oluştur
   c. haber-object.md yaz:
      - ID, Created, Status=cross_verified/captured
      - Route=VERIFIED (güvenli) veya REWRITE (düşük güven)
      - Title, Verification Level, Verified Sources
   d. idea.md yaz:
      - Story, Best Source URL
      - Tüm kaynaklar: [tier] source_name — URL
   e. fact-check-report.md yaz:
      - Verification seviyesi, source sayıları
      - İddia bazında doğrulama durumu
      - Varsa tutarsızlıklar
   f. context.md yaz:
      - Writer için kaynak özeti + verification özeti
      - Voice profile summary
   g. State cache'e ekle
   
2. Eğer zaten varsa: {"status": "exists"} dön

3. Eğer verification_level ≥ 2 ve human_review=False:
   - State otomatik: captured → idea_review → brief_ready
   - auto_advanced = True
```

#### haber-object.md Formatı

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

#### fact-check-report.md Formatı

```markdown
# Cross-Verification Report: Israel Says It Killed Hamas's Top Leader in Gaza

**Verification Level:** ✅ CONFIRMED — Multiple primary sources
**Total Sources:** 3
**Primary Sources:** 2
**Major Sources:** 1
**Weighted Score:** 8
**Claims Extracted:** 28
**Claims Verified (2+ sources):** 5

### Sources Reporting
  • [PRIMARY — Wire Service] Associated Press (AP) — https://...
  • [PRIMARY — Wire Service] BBC News — https://...
  • [MAJOR — Major Outlet] NPR — https://...

### Tier Breakdown
  • Tier 0 (Primary): 2
  • Tier 1 (Major): 1

### Claim Verification
  ✅ gaza — confirmed by 3 sources
  ✅ hamas — confirmed by 3 sources
  ⚠️ israel says — only from Associated Press (AP)

### Verdict
⚠️ Sources use different headlines — may indicate different angles.
✅ PASS — Meets minimum verification threshold (level 1).
```

### ══════════════════════════════════════════════════════════
### AŞAMA 5: Brief Hazırlığı
### ══════════════════════════════════════════════════════════

**CLI:** `hermes haber brief {slug}` veya `hermes haber brief {slug} --llm`

Brief (Writer Context Packet), Writer Agent'ın kullanacağı TEK bilgi kaynağıdır.
İçinde thesis, key facts, source list, constraints ve rubric hedefleri bulunur.

```
Brief oluşturma algoritması:
1. haber-object.md'den oku: Title, Verification Level, Source Count
2. idea.md'den oku: Kaynak listesi (name → URL)
3. fact-check-report.md'den oku: Doğrulama detayları
4. context.md'den oku: Writer context
5. brief.md oluştur:
   # Writer Context Packet — {slug}
   ## Meta
   ## Thesis
   ## Key Facts
   ## Source List
   ## Constraints
   ## Rubric Targets
6. State: brief_ready
```

`--llm` ile: Hermes auxiliary LLM kullanarak kaynaklardan otomatik brief oluşturulur.
LLM yoksa veya hata alınırsa template-based brief'e düşer.

### ══════════════════════════════════════════════════════════
### AŞAMA 6: Taslak Yazımı (Drafting)
### ══════════════════════════════════════════════════════════

**CLI:** `hermes haber draft {slug}` veya `hermes haber draft {slug} --llm`

```
Draft oluşturma algoritması:
1. brief.md'yi oku
2. draft-package.md oluştur:
   ---
   draft:
   [Özet] Tek cümle haber özeti
   
   [Detaylar]
   - Doğrulanmış bilgi maddeleri
   - Her madde kaynak atıflı
   
   [Kaynak]
   - Kaynak Adı: URL
   
   rubric_self_assessment: (opsiyonel)
   avoid_slop_pass:
   voice_check:
   source_attribution_check:
3. State: drafting
```

`--llm` ile: brief'teki Thesis/Source List/Constraints'i kullanarak LLM'e haber metni yazdırılır.
**Halüsinasyon koruması:** LLM prompt'unda "CRITICAL: Only use facts from the brief. Do NOT add any information not in the brief." talimatı vardır.

### ══════════════════════════════════════════════════════════
### AŞAMA 7: Taslak Doğrulama
### ══════════════════════════════════════════════════════════

**CLI:** `hermes haber verify-draft {slug}`

İki aşamalı denetim:

1. **Halüsinasyon Taraması** (`hallucination_check()`):
   - 4 pattern: kaynaksız istatistik, spekülatif dil, sahipsiz alıntı, muğlak atıf
   - URL'lerdeki sayılar false positive olarak algılanmaz (özel filtre)

2. **Slop Taraması** (`scan_slop()`):
   - 54+ kalıp, 4 kademe
   - Detaylar için [Bölüm 9]'a bakın

Sonuç: `verifier-report.md` yazılır, state `verification`

### ══════════════════════════════════════════════════════════
### AŞAMA 8: Yayın (Publishing)
### ══════════════════════════════════════════════════════════

**CLI:** `hermes haber post {slug}`

```
post_memo() algoritması:
1. draft-package.md'yi oku
2. draft: bölümünü ayıkla (rubric_self_assessment öncesi)
3. Memos API'sine POST:
   POST https://memos.googig.cloud/api/v1/memos
   Authorization: Bearer {MEMOS_TOKEN}
   Content-Type: application/json
   User-Agent: Haber-Kuratör/3.0.0
   {
     "content": "[Özet] ... [Detaylar] ... [Kaynak] ...",
     "visibility": "PUBLIC"
   }
4. State: published
```

### ══════════════════════════════════════════════════════════
### AŞAMA 9: Writer Agent ile Otomatik Yayın
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
   b. Template brief yaz
   c. generate_news(cluster) → Türkçe [Özet]-[Detaylar]-[Kaynak] metni
   d. Draft package yaz
   e. State: drafting
   f. post_to_memos() → Memos'a yayınla
   g. 1 saniye bekle (rate limit)
7. Rapor dön: {published, skipped, failed, articles[]}
```

### ══════════════════════════════════════════════════════════
### AŞAMA 10: Post-mortem ve Arşivleme
### ══════════════════════════════════════════════════════════

**Postmortem:** `hermes haber postmortem {slug} [--impressions N] [--okunma N] [--likes N]`

haber-object.md + feedback.md + correction.md okuyarak metrik tablosu gösterir.
State'e göre bir sonraki adımı önerir.

**Arşivleme:** `hermes haber archive {slug}` veya `hermes haber archive {slug} --force`
- Normal: state `learned` olmalı
- `--force`: her state'te arşivler

---

## 5. Kaynak Güvenilirlik Sistemi

### 5.1 Kademe Tanımları

| Kademe | Değer | Ağırlık | Tanım | Ölçüt |
|--------|-------|---------|-------|-------|
| **PRIMARY** | 0 | 3 | Wire servis / haber ajansı | Reuters, AP, AFP, BBC |
| **MAJOR** | 1 | 2 | Büyük yayıncı / gazete | Bloomberg, WSJ, FT, Guardian, NYT, WaPo, NPR, Al Jazeera, Economist, CNBC |
| **SPECIALIZED** | 2 | 1 | Uzman / niş yayıncı | Nature, MIT Tech Review, The Verge, Wired, HBR, ScienceDaily |
| **SUPPLEMENTARY** | 3 | 1 | Yerel / bölgesel | (genişletilebilir) |

### 5.2 Türkçe Kaynaklar ve Kademeleri

**Tier 1 (MAJOR):**
| Kaynak | Kategori | RSS |
|--------|----------|-----|
| Anadolu Ajansı (AA) | news | aa.com.tr/rss/ajansguncel.xml |
| BBC Türkçe | news | feeds.bbci.co.uk/turkce/rss.xml |
| Euronews Türkçe | news | tr.euronews.com/rss |
| Deutsche Welle Türkçe | news | rss.dw.com/rdf/Turkish |
| Bloomberg HT | business | bloomberght.com/rss |

**Tier 2 (SPECIALIZED):**
| Kaynak | Kategori | RSS |
|--------|----------|-----|
| T24 | news | t24.com.tr/rss |
| Medyascope | news | medyascope.tv/feed/ |
| Gazete Duvar | news | gazeteduvar.com.tr/rss |
| Diken | news | diken.com.tr/feed/ |
| BirGün | news | birgun.net/rss |
| Sözcü | news | sozcu.com.tr/feeds-haberler |
| Cumhuriyet | news | cumhuriyet.com.tr/rss/son_dakika.xml |
| Hürriyet | news | rss.hurriyet.com.tr/ |
| Webrazzi | technology | webrazzi.com/feed/ |

### 5.3 Çapraz Doğrulama Kuralları (Türkiye Haberleri)

| Senaryo | Minimum Doğrulama |
|----------|------------------|
| Uluslararası haber (Türkçe) | BBC Türkçe + Euronews TR veya 1 Tier 0 + 1 Türk kaynağı |
| Türkiye iç politika | AA + T24/Medyascope/Diken (2 bağımsız) |
| Ekonomi | Bloomberg HT + AA veya uluslararası Tier 1 |
| Teknoloji | Webrazzi + uluslararası Tier 2 veya 2 Türk kaynağı |
| Yerel haber | AA + en az 1 bağımsız Türk kaynağı |

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
   - Skip words: "The", "This", "That", "What"... filtrelenir

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

# Başlık farklılığı varsa (farklı angle): uyarı ekle
if has_title_discrepancy:
    report += "⚠️ Sources use different headlines"
```

### 6.4 Yayın Eşiği

| Seviye | Otomatik Yayın? |
|--------|-----------------|
| CONFIRMED (3) | ✅ Evet (`--auto` ile veya normal) |
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

İki haber başlığı aynı kümede birleştirilir:
- **Normal (İngilizce-İngilizce):** kelime örtüşmesi ≥ %40
- **Çapraz dil (Türkçe-İngilizce):** kelime örtüşmesi ≥ %30

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

## 8. Halüsinasyon Koruması

### 8.1 Tespit Edilen 4 Pattern

| # | Pattern | Regex | Severity | Ne kontrol eder? |
|---|---------|-------|----------|-----------------|
| 1 | Kaynaksız istatistik | `\$?\d+[\.\d,]*\s*(?:million\|billion\|...)` | 🔴 high | 200 karakter içinde kaynak adı var mı? |
| 2 | Spekülatif dil | `could (?:mean\|lead to\|result in)`, `might indicate`, `raises questions` | 🟡 medium | Gelecek hakkında tahmin mi? |
| 3 | Sahipsiz alıntı | `"([^"]{8,})"` | 🔴 high | "..." içinde konuşan adı var mı? |
| 4 | Muğlak atıf | `it is believed that`, `many think that`, `some argue that` | 🔴 high | Kim dedi? Spesifik kaynak var mı? |

### 8.2 URL Filtreleme (False Positive Koruması)

Sayı içeren satırda URL varsa (`https?://`), o satırdaki tüm sayılar atlanır.
Çünkü URL'lerdeki ID'ler (`g-s1-122453`), tarihler (`2026/05/16`) ve path segmentleri
anlamlı istatistik değil, sadece adres bileşenidir.

### 8.3 Skorlama

```
PASS: high severity bulgu = 0
FAIL: high severity bulgu ≥ 1
```

---

## 9. 54+ Slop Tespit Kalıbı

### 9.1 Kademeler

| Kademe | Pattern Sayısı | REVISE Eşiği | REJECT Eşiği |
|--------|---------------|-------------|-------------|
| 🔴 Tier 1 (Critical) | 32 | ≥1 pattern | ≥3 pattern |
| 🟡 Tier 2 (High) | 32 | ≥3 pattern | ≥5 pattern |
| 🟢 Tier 3 (Medium) | 33 | ≥8 pattern | ≥15 pattern |
| ⚪ Bonus (Tone) | 9 | Kontekst bazlı | — |

### 9.2 Tier 1 — Sıfır Tolerans (Haber)

Herhangi bir Tier 1 ihlali varsa otomatik **REVISE**:

```
1.  Promosyon/Clickbait: "groundbreaking", "game-changing"
2.  Önem abartısı: "pivotal", "testament"
3.  Belirsiz atıf: "experts believe", "studies show"
4.  Kaynaksız iddia: "allegedly", "unnamed sources say"
5.  Sahte aciliyet: "breaking:", "developing story"
6.  Dolgu zarfları: "actually", "literally", "simply", "just"
7.  Staccato parçalama: kısa cümle dizileri
8.  "şok edici", "inanılmaz", "devrim niteliğinde" (Türkçe clickbait)
9.  "bence", "bana göre", "görünen o ki" (öznel ifade)
10. "son dakika", "gelişen haber" (yalancı aciliyet)
... 22 pattern daha
```

### 9.3 Tier 2 — Yüksek (3+ = REVISE)

```
1.  Copula Avoidance: "serves as", "stands as"
2.  -ing Padding: "leveraging", "implementing"
3.  Rule of Three Zorlama
4.  Filler Phrases: "due to the fact that"
5.  Generic Conclusions: "the future looks bright"
6.  Signposting: "let's dive in", "here's what you need"
7.  Hyperbolic Quantifiers: "every single", "never ever"
8.  Hedging: "it could potentially", "arguably"
... 24 pattern daha
```

### 9.4 Tier 3 — Orta (8+ = REVISE)

```
1.  Passive Voice (aşırı kullanım)
2.  Temporal Vagueness: "recently", "lately"
3.  False Balance: "some say... while others say"
4.  Speculation: "could potentially mean", "raises questions"
... 29 pattern daha
```

---

## 10. Writer Agent ve Otomatik Haber Üretimi

### 10.1 WriterAgent Sınıfı

```python
class WriterAgent:
    def __init__(self, core: HaberKuratorCore):
        self.core = core
        self._load_env()               # .env'den MEMOS_TOKEN oku
        self._llm = None               # Hermes LLM (opsiyonel)
    
    def set_llm(self, llm):           # Hermes auxiliary LLM bağla
    def _try_translate(self, text)    # İng→Tr çeviri
    def generate_news(self, cluster)  # [Özet]-[Detaylar]-[Kaynak] üret
    def post_to_memos(self, content)  # Memos'a yayınla
    def auto_publish(self, ...)       # Tam otomatik pipeline
```

### 10.2 generate_news() Algoritması

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

### 10.3 Çıktı Formatı

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

---

## 11. 18 Aşamalı State Makinesi

### 11.1 State Tanımları ve Geçişler

```
STATE_LIFECYCLE = [
    "captured",           # Haber sisteme ilk giriş
    "fact_checking",      # Çapraz doğrulama devam ediyor
    "cross_verified",     # İddialar kaynaklarda doğrulandı
    "idea_review",        # Rota kararı
    "brief_ready",        # Writer Context Packet hazır
    "drafting",           # Taslak yazılıyor
    "verification",       # Denetim (halüsinasyon + slop)
    "draft_review",       # İnsan/LLM incelemesi
    "approved",           # Onaylandı
    "scheduler_ready",    # Zamanlayıcıya hazır
    "scheduled",          # Zamanlandı
    "published",          # Memos'a yayınlandı
    "feedback_24h",       # 24 saat metrik toplama
    "feedback_72h",       # 72 saat derin analiz
    "learned",            # Öğrenilen dersler çıkarıldı
    "correction_needed",  # Hata tespit edildi
    "corrected",          # Düzeltme yayınlandı
    "retracted",          # Haber geri çekildi
    "archived",           # Arşivlendi
]
```

### 11.2 Geçiş Kuralları

| Mevcut State | Geçebileceği State'ler | Açıklama |
|--------------|------------------------|----------|
| `captured` | `fact_checking` | Haber doğrulamaya alınır |
| `fact_checking` | `cross_verified`, `captured` | Doğrulama tamam veya başa dön |
| `cross_verified` | `idea_review`, `captured` | Rota kararı veya yeniden değerlendir |
| `idea_review` | `brief_ready`, `captured` | Brief hazırlığı veya geri dönüş |
| `brief_ready` | `drafting` | Taslak yazımı başlar |
| `drafting` | `verification` | Taslak denetime gider |
| `verification` | `draft_review` | Denetim raporu hazır |
| `draft_review` | `approved`, `brief_ready`, `captured` | Onay, revizyon veya iptal |
| `approved` | `scheduler_ready` | Zamanlamaya hazır |
| `scheduler_ready` | `scheduled` | Zamanlandı |
| `scheduled` | `published` | Yayınlandı |
| `published` | `feedback_24h`, `correction_needed` | Feedback veya düzeltme |
| `feedback_24h` | `feedback_72h`, `correction_needed` | 72h feedback veya düzeltme |
| `feedback_72h` | `learned`, `correction_needed` | Öğren veya düzelt |
| `learned` | `archived`, `correction_needed` | Arşivle veya düzelt |
| `correction_needed` | `corrected`, `retracted` | Düzelt veya geri çek |
| `corrected` | `learned` | Düzeltme sonrası öğren |
| `retracted` | `archived` | Geri çekme sonrası arşivle |
| `archived` | — | Terminal state |

### 11.3 State Görüntüleme ve Değiştirme

```bash
# Tek run state'i
hermes haber state haber-slug

# Tüm run'ların state'leri
hermes haber state

# State değiştirme
hermes haber state haber-slug --set draft_review
```

### 11.4 State-File Auto-Detection (sync_state)

```python
STATE_FILE_MAP = {
    "fact_checking":     "fact-check-report.md",
    "cross_verified":    "fact-check-report.md",
    "correction_needed": "correction.md",
    "corrected":         "correction.md",
    "retracted":         "correction.md",
    "published":         "published",
    "verification":      "verifier-report.md",
    "feedback_72h":      "feedback.md",
    "feedback_24h":      "feedback.md",
    "learned":           "feedback.md",
    "drafting":          "draft-package.md",
    "brief_ready":       "brief.md",
}
```

`sync_state(slug)` dosya varlığına göre state'i otomatik algılar.

---

## 12. 12 Puanlık Rubrik Değerlendirme

### 12.1 Kriterler

| # | Kriter | 0 puan | 1 puan | 2 puan |
|---|--------|--------|--------|--------|
| 1 | **Tarafsızlık** | Yazar fikrini katmış ("Maalesef", "Bence") | Kısmen yönlendirme var | Tamamen objektif |
| 2 | **Kaynak Gösterimi** | Kaynak yok veya "Uzmanlar" gibi belirsiz | İsim var ama link/net kurum eksik | Kaynak net: isim + URL |
| 3 | **Kısalık ve Netlik** | Uzun paragraflar, laf salatası | Biraz uzun ama okunabilir | Hap bilgi, hızlı okunur |
| 4 | **Bilgi Yoğunluğu** | Soyut kelimeler, somut veri yok | Birkaç detay var ama eksik | Sayı, tarih, kişi, kurum dolu |
| 5 | **Clickbait Uzaklığı** | "Şok", "İnanılmaz", gizemli başlık | Hafif abartı | İçeriği dürüstçe yansıtan |
| 6 | **Format Yapısı** | Karman çorman düz metin | Format var ama standart değil | [Özet]-[Detaylar]-[Kaynak] |

### 12.2 CLI Puanlama

```bash
hermes haber score haber-slug
```

Çıktı: 5 kriter × 2 = 10 puan (format, slop, uzunluk, yoğunluk, kaynak) + self-assessment
- ≥ 10/12: ✅ İyi, yayına hazır
- ≥ 7/12: 🟡 Revizyon gerekli
- < 7/12: ❌ Yeniden yazılmalı

---

## 13. Düzeltme ve Geri Çekme Mekanizması

### 13.1 Düzeltme (Correction)

```bash
hermes haber correct {slug} "Hata açıklaması" --info "Doğru bilgi"
```

**Ne olur:**
1. `correction.md` oluşturulur (Correction Notice)
2. State `corrected` olarak güncellenir
3. Orijinal haber güncellenir veya uyarı eklenir

### 13.2 Geri Çekme (Retraction)

```bash
hermes haber correct {slug} "Ciddi hata" --retract
```

**Ne zaman:**
- Haberin ana iddiası yanlış çıktıysa
- Kaynaklar haberi yalanladıysa
- Manipülasyon tespit edildiyse

**Ne olur:**
1. `correction.md` → `## Retraction Statement` yazılır
2. State `retracted`
3. Haber platformdan kaldırılır veya "RETRACTED" etiketi eklenir

### 13.3 State Geçişleri

```
published → correction_needed → corrected/retracted → learned → archived
```

---

## 14. Memos Yayınlama

### 14.1 API İsteği

```http
POST https://memos.googig.cloud/api/v1/memos
Authorization: Bearer {MEMOS_TOKEN}
Content-Type: application/json
User-Agent: Haber-Kuratör/3.0.0

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

### 15.1 Haber Toplama & Doğrulama

| Komut | Açıklama | Örnek |
|-------|----------|-------|
| `hermes haber sources` | Kaynakları kademelere göre listeler | `hermes haber sources` |
| `hermes haber fetch [--category] [--limit]` | Haber çeker + kümeler + tablo | `hermes haber fetch --category technology --limit 10` |
| `hermes haber verify [--category] [--limit]` | Çeker + kümeler + çapraz doğrular | `hermes haber verify --category news --limit 5` |
| `hermes haber publish [--category] [--limit] [--auto]` | Doğrulanmış haberleri run'a ekler | `hermes haber publish --auto --limit 3` |
| `hermes haber correct <slug> <hata> [--retract] [--info]` | Düzeltme/retraction | `hermes haber correct slug "hata" --info "doğru"` |
| `hermes haber hallucination <slug>` | Halüsinasyon taraması | `hermes haber hallucination slug` |

### 15.2 Writer Agent

| Komut | Açıklama | Örnek |
|-------|----------|-------|
| `hermes haber brief <slug> [--llm]` | Brief hazırla | `hermes haber brief slug --llm` |
| `hermes haber draft <slug> [--llm]` | Taslak yaz | `hermes haber draft slug --llm` |
| `hermes haber verify-draft <slug>` | Taslak denetimi | `hermes haber verify-draft slug` |
| `hermes haber post <slug>` | Memos'a yayınla | `hermes haber post slug` |
| `hermes haber auto-publish [--limit] [--category]` | Tam otomatik yayın | `hermes haber auto-publish --limit 5` |

### 15.3 Kalite Kontrol

| Komut | Açıklama |
|-------|----------|
| `hermes haber scan <slug>` | 54+ slop taraması |
| `hermes haber score <slug>` | 12 puanlık rubric değerlendirmesi |
| `hermes haber hallucination <slug>` | Halüsinasyon taraması |

### 15.4 Sistem & Bilgi

| Komut | Açıklama |
|-------|----------|
| `hermes haber setup` | Dizin yapısını başlat |
| `hermes haber status` | Aktif run'ların state'leri |
| `hermes haber audit` | Tam sistem denetimi |
| `hermes haber state [slug] [--set]` | State görüntüle/değiştir |
| `hermes haber runs [--no-archive]` | Tüm run'ları listele |
| `hermes haber search <query>` | Run'larda ara |
| `hermes haber context <slug>` | Run bağlamını göster |
| `hermes haber learnings [--topic]` | Önceki run'lardan öğrenilenler |
| `hermes haber patterns` | Run pattern analizi |
| `hermes haber voice-update` | Ses profilini göster |

### 15.5 Run Yönetimi

| Komut | Açıklama | Örnek |
|-------|----------|-------|
| `hermes haber new <idea> [--slug] [--source]` | Yeni run (haber dışı) | `hermes haber new "fikir"` |
| `hermes haber route <idea> [--source]` | Rota belirle | `hermes haber route "fikir" --source verified` |
| `hermes haber postmortem <slug> [--impressions]` | Yayın sonrası analiz | `hermes haber postmortem slug --okunma 1200` |
| `hermes haber archive <slug> [--force]` | Arşivle | `hermes haber archive slug --force` |
| `hermes haber signal [x\|rss]` | Sinyal taraması | `hermes haber signal rss` |

### 15.6 Slash Komutlar (Hermes içinde)

Tüm CLI komutlarının `/haber` karşılığı vardır:
- `/haber fetch` — fetch
- `/haber verify` — verify
- `/haber publish` — publish
- `/haber status` — status
- `/haber sources` — sources

### 15.7 Doğal Dil Desteği (NLP)

Hermes içinde `/haber` komutuna **Türkçe doğal dil cümleleri** yazabilirsiniz.
Sistem kelimelerden niyeti ve kategoriyi otomatik algılar:

| Dediğiniz | Ne Yapar |
|-----------|----------|
| `/haber teknoloji haberlerini getir` | `fetch --category technology` |
| `/haber ekonomi haberlerini doğrula` | `verify --category business` |
| `/haber son dakika haberlerini yayınla` | `publish --category news` |
| `/haber bilim haberlerini otomatik yayınla` | `auto-publish --category science` |
| `/haber kaynakları listele` | `sources` |
| `/haber haber doğrula` | `verify` (tüm kategoriler) |
| `/haber haber yayınla` | `publish` (tüm kategoriler) |
| `/haber getir` | `fetch` (tüm kategoriler) |

**Desteklenen kategoriler:** teknoloji, ekonomi/finans, bilim/araştırma, gündem, son dakika
**Desteklenen fiiller:** getir/çek/ara (fetch), doğrula/kontrol et/teyit et (verify), yayınla/paylaş/gönder (publish), otomatik yayınla (auto-publish)

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

# ── 5. Bir haber için brief oluştur (LLM ile) ────────
hermes haber brief 2026-05-technology-slug --llm

# ── 6. Taslak oluştur (LLM ile) ───────────────────────
hermes haber draft 2026-05-technology-slug --llm

# ── 7. Taslağı denetle ────────────────────────────────
hermes haber verify-draft 2026-05-technology-slug

# ── 8. Puanla ─────────────────────────────────────────
hermes haber score 2026-05-technology-slug

# ── 9. Onayla ve yayınla ──────────────────────────────
hermes haber state 2026-05-technology-slug --set approved
hermes haber post 2026-05-technology-slug

# ── 10. Postmortem ────────────────────────────────────
hermes haber state 2026-05-technology-slug --set feedback_24h
hermes haber state 2026-05-technology-slug --set feedback_72h
hermes haber state 2026-05-technology-slug --set learned

# ── 11. Arşivle (state learned değilse --force ile) ──
hermes haber archive 2026-05-technology-slug --force
```

### Otomatik Pipeline (Tek Komut)

```bash
hermes haber auto-publish --limit 5 --category news
```

Bu komut: **fetch → cluster → verify → sort → dedup → create run → brief → draft → publish** adımlarının tamamını otomatik yapar.

---

## 17. Sık Sorulan Sorular ve Hata Çözümleri

### ❓ "Plugin 'haber_kurator' is not installed" hatası

Plugin adı tire ile: `haber-kurator`, alt çizgi ile değil:
```bash
hermes plugins enable haber-kurator
hermes plugins disable haber-kurator
```

### ❓ "invalid choice: 'haber'" hatası

Plugin CLI komutları kayıtlı değil. İki olası neden:

1. **Absolute import hatası:** `__init__.py`'deki `from haber_kurator_core import...` gibi import'lar Hermes namespace paketinde çalışmaz. Çözüm: `from .haber_kurator_core import...` (relative import).

2. **Handler bağlantısı eksik:** `cli.py`'deki `register_cli()` fonksiyonu argparse ağacını kurar ama `haber_parser.set_defaults(func=handler)` çağrılmazsa komut işlenemez. Çözüm: `register_cli()` sonunda `haber_parser.set_defaults(func=handler)` eklenir.

Emin değilseniz: `hermes plugins list` ile plugin'in etkin olduğunu kontrol edin, sonra `hermes haber sources` ile test edin.

### ❓ RSS beslemesi çalışmazsa?

- Hata alan beslemeler atlanır (log'a yazılır)
- 5 saniye timeout (CONFIG["rss_timeout"])
- Tüm kaynaklar hata verirse boş liste döner
- Kaynakları kontrol et: `hermes haber sources`

### ❓ "Number/statistic without clear source attribution" false positive

URL'lerdeki sayılar (`g-s1-122453`) kaynaksız istatistik sanılabilir. Sistem:
1. Sayının bulunduğu satırda URL (`https://`) var mı kontrol eder
2. Varsa o satırdaki tüm sayısal değerleri atlar

### ❓ Hallüsinasyon testi sürekli FAIL veriyor?

Template-based draft kullanıyorsanız normaldir. `--llm` ile oluşturun:
```bash
hermes haber brief SLUG --llm
hermes haber draft SLUG --llm
```

### ❓ Memos'a yayın başarısız?

1. `MEMOS_TOKEN` ayarlı mı?
2. API URL doğru mu? `https://memos.googig.cloud/api/v1/memos`
3. Token'da yetki var mı? (`visibility: PUBLIC`)
4. `.env` dosyası doğru yerde mi? (plugin dizini veya `~/.hermes/`)

### ❓ "Cannot archive" hatası

Run'ı arşivlemek için state `learned` olmalıdır. Zorla arşivle:
```bash
hermes haber archive SLUG --force
```

### ❓ State cache ile filesystem uyuşmazlığı

`haber-object.md`'deki state ile `.state_cache/runs_state.json` farklı olabilir.
Cache authoritative'dir. Sync için:
```bash
# Her iki kaynağı kontrol et
grep -A1 "state:" runs/active/*/haber-object.md
cat .state_cache/runs_state.json | python3 -m json.tool
```

### ❓ Writer Agent hangi LLM'i kullanır?

Hermes auxiliary LLM (`agent.auxiliary_client.async_call_llm`).
LLM yoksa template-based üretime düşer (orijinal başlık korunur).

### ❓ Run sayısı çok arttı, performans düşer mi?

- Run'lar dosya sistemi üzerinde tutulur
- State cache SQLite JSON ile yönetilir
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

> **Haber-Kuratör v3.0.0** — Memos Küratörü
> 35+ kaynak, 4 güven kademesi, 18 state, 54+ slop kalıbı, 12 puanlık rubric
> 
> **Dosya:** `plugins/haber-kurator/references/KULLANIM_KILAVUZU.md`
> **Skill:** `hermes-agent` skill'ini yükleyip `hermes haber ...` komutlarını kullanın
