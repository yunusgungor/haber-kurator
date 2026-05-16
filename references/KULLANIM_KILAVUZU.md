# Haber-Kuratör v3.0.0 — Kullanım Kılavuzu

> **Türkçe haber doğrulama ve yayın motoru.**
> Dünyanın önde gelen 35+ güvenilir kaynağından haber çeker, çapraz doğrular
> ve kaynak atıflarıyla Memos'a yayınlar.

---

## İçindekiler

1. [Sistem Nedir?](#1-sistem-nedir)
2. [Mimari Genel Bakış](#2-mimari-genel-bakış)
3. [Gereksinimler & Kurulum](#3-gereksinimler--kurulum)
4. [Uçtan Uca Çalışma Döngüsü](#4-uçtan-uca-çalışma-döngüsü)
5. [18 Aşamalı State Makinesi](#5-18-aşamalı-state-makinesi)
6. [Kaynak Güvenilirlik Sistemi](#6-kaynak-güvenilirlik-sistemi)
7. [Komut Referansı](#7-komut-referansı)
8. [Adım Adım Örnek Senaryo](#8-adım-adım-örnek-senaryo)
9. [Sık Sorulan Sorular](#9-sık-sorulan-sorular)

---

## 1. Sistem Nedir?

Haber-Kuratör, Hermes Agent üzerinde çalışan bir **haber doğrulama ve yayın motorudur**.
Temel prensip: **hiçbir haber tek kaynaktan yayınlanmaz.** Her haber en az 2 bağımsız,
güvenilir kaynakta doğrulanmadan sisteme girmez.

### Temel İlkeler

| İlke | Açıklama |
|------|----------|
| **Çok Kaynaklı Doğrulama** | Her iddia en az 2 bağımsız kaynakta teyit edilir |
| **Kademeli Güven** | Kaynaklar 4 güvenilirlik kademesinde sınıflandırılır |
| **Halüsinasyon Koruması** | Yapay zeka yazıcı, yalnızca kaynaklardaki bilgileri kullanır |
| **Şeffaflık** | Her haberin altında kullanılan tüm kaynaklar listelenir |
| **Düzeltme Mekanizması** | Yayın sonrası hata durumunda düzeltme/geri çekme yapılabilir |

### Ne Yapabilir?

- 35+ küresel haber kaynağından otomatik haber toplama (Reuters, AP, AFP, BBC, Bloomberg, WSJ, FT, Guardian, NYT, WaPo, Nature, MIT Tech Review + Türkçe: AA, BBC Türkçe, Euronews TR, DW Türkçe, T24, Medyascope, Duvar, Diken, BirGün, Sözcü, Cumhuriyet, Hürriyet, Bloomberg HT, Webrazzi)
- Aynı haberi farklı kaynaklardan algılama ve kümeleme (İngilizce + Türkçe çapraz dil desteği)
- Çapraz doğrulama: her iddiayı 2+ kaynakta karşılaştırma
- Otomatik haber üretimi: Writer Agent ile Türkçe [Özet]-[Detaylar]-[Kaynak] formatında yazma
- Memos platformuna doğrudan yayın
- Yayın sonrası düzeltme ve geri çekme

---

## 2. Mimari Genel Bakış

```
                        ┌──────────────────────────────┐
                        │     35+ HABER KAYNAĞI        │
                        │  (Tier 0-3, RSS/Atom)        │
                        └──────────┬───────────────────┘
                                   │
                                   ▼
                        ┌──────────────────────────────┐
                        │    TOPLAMA (fetch_all_news)   │
                        │  • RSS çekme                 │
                        │  • URL/başlık tekilleştirme  │
                        │  • Promosyon içerik filtreleme│
                        └──────────┬───────────────────┘
                                   │
                                   ▼
                        ┌──────────────────────────────┐
                        │   KÜMELEME (cluster_stories)  │
                        │  • Kelime örtüşmesi ≥%30     │
                        │  • Çapraz dil desteği         │
                        │  • En yüksek kaynaktan başlık │
                        └──────────┬───────────────────┘
                                   │
                                   ▼
                        ┌──────────────────────────────┐
                        │ ÇAPRAZ DOĞRULAMA             │
                        │ (cross_verify_story)         │
                        │  • İddia çıkarma             │
                        │  • Çok kaynaklı teyit        │
                        │  • Sayısal tutarsızlık tespiti│
                        │  • Seviye belirleme          │
                        │    (CONFIRMED → UNVERIFIED)  │
                        └──────────┬───────────────────┘
                                   │
                                   ▼
                     ┌────────────┴────────────┐
                     │                         │
               GÜVENLİ SEVİYE           DÜŞÜK SEVİYE
           (CONFIRMED/HIGH)          (MEDIUM/LOW/UNVER)
                     │                         │
                     ▼                         ▼
            ┌─────────────────┐       ┌────────────────┐
            │  YAYIN RUN'ı    │       │ İnsan Onayına  │
            │  Oluşturma      │──────▶│ Gönder         │
            └────────┬────────┘       └────────────────┘
                     │
                     ▼
            ┌──────────────────────────────────┐
            │  WRITER AGENT / MANUEL YAZIM     │
            │  • Brief hazırlığı               │
            │  • Kaynak atıflı taslak          │
            │  • Halüsinasyon taraması         │
            │  • Slop taraması (54+ kalıp)     │
            └──────────┬───────────────────────┘
                       │
                       ▼
            ┌──────────────────────────────────┐
            │    YAYIN (Memos API)             │
            │    • Memos'a gönderme            │
            │    • State: published            │
            └──────────┬───────────────────────┘
                       │
                       ▼
            ┌──────────────────────────────────┐
            │    GERİ BİLDİRİM & DÜZELTME      │
            │    • feedback_24h / feedback_72h │
            │    • Hata → düzeltme/geri çekme  │
            │    • Arşiv                        │
            └──────────────────────────────────┘
```

### Klasör Yapısı

```
haber-kurator/
├── strategy/                     ← Stratejik dokümanlar
│   ├── source-watchlist.md       ← Tüm kaynakların listesi
│   ├── positioning.md            ← Konumlandırma
│   ├── audience.md               ← Hedef kitle
│   └── pillars.md                ← İçerik sütunları
├── voice/                        ← Üslup kuralları
│   ├── voice-profile.md          ← Ses profili
│   └── master-avoid-slop.md      ← 54+ slop kalıbı
├── runs/active/{slug}/           ← Aktif haber run'ları
│   ├── haber-object.md           ← State, route, verification level
│   ├── idea.md                   ← Kaynak listesi
│   ├── fact-check-report.md      ← Çapraz doğrulama raporu
│   ├── context.md                ← Writer için kaynak özeti
│   ├── brief.md                  ← Writer Context Packet
│   ├── draft-package.md          ← Taslak + rubric + self-assessment
│   ├── verifier-report.md        ← Denetçi raporu
│   ├── feedback.md               ← Yayın sonrası geri bildirim
│   └── correction.md             ← Düzeltme/retraction kaydı
├── references/                   ← Yardımcı dokümanlar
├── modules/                      ← Writer konfigürasyonu
└── workflows/                    ← Playbook'lar
```

---

## 3. Gereksinimler & Kurulum

### Gereksinimler

- **Hermes Agent** (plugin sistemi ile çalışır)
- **Python 3.9+**
- **Memos hesabı** (yayın için)
- **MEMOS_TOKEN** çevre değişkeni

### Kurulum

Plugin zaten yüklü ve etkin:

```bash
# Etkin olduğunu kontrol et
hermes plugins list
# → haber-kurator enabled olarak görünmeli

# Memos kimlik bilgilerini ayarla
# ~/.hermes/.env dosyasına veya plugin'in .env dosyasına:
echo 'MEMOS_TOKEN=your_token_here' >> ~/.hermes/.env

# İsteğe bağlı: Memos API URL'si (varsayılan: https://memos.googig.cloud/api/v1/memos)
echo 'MEMOS_API_URL=https://memos.googig.cloud/api/v1/memos' >> ~/.hermes/.env

# İlk kurulum
hermes haber setup

# Sistem durumunu kontrol et
hermes haber audit
```

### .env Dosyası Konumu

Plugin, `.env` dosyasını iki yerde arar:
1. `~/.hermes/.env` (Hermes ana dizini)
2. `plugins/haber-kurator/.env` (plugin dizini)

---

## 4. Uçtan Uca Çalışma Döngüsü

Aşağıdaki akış, bir haberin kaynaktan yayına kadar olan tam yolculuğudur.

### ═══════════════════════════════════════════════
### AŞAMA 1: Haber Toplama (Fetch)
### ═══════════════════════════════════════════════

**Komut:** `hermes haber fetch` veya `/haber fetch`

Sistem, tüm kaynakların RSS/Atom beslemelerini paralel olarak çeker:

```bash
hermes haber fetch --category news --limit 10
```

**Ne olur:**
1. Her kaynağın RSS/Atom URL'lerine HTTP isteği gönderilir (5sn timeout)
2. RSS 2.0 ve Atom formatları otomatik algılanır
3. XML çözümlemesi yapılır, başlık/URL/tarih/özet çıkarılır
4. Aynı URL ve benzer başlıktaki haberler tekilleştirilir
5. Promosyon içerik (kupon, indirim vb.) filtrelenir
6. Hata alan kaynaklar atlanır (log'a yazılır)

**Çıktı:** Benzersiz haber öğeleri listesi (FetchedNewsItem)

### ═══════════════════════════════════════════════
### AŞAMA 2: Kümeleme (Clustering)
### ═══════════════════════════════════════════════

Bu adım `fetch` veya `verify` komutunun içinde otomatik çalışır.

**Ne olur:**
1. Her haberin başlığı normalize edilir (noktalama, küçük harf)
2. Türkçe/İngilizce ortak kelimeler eşleştirilir (`savaş` ↔ `war`, `ekonomi` ↔ `economy`)
3. Normalize başlıklar arasında kelime örtüşmesi hesaplanır
4. ≥%30 örtüşme varsa → aynı haber kabul edilir, aynı kümeye eklenir
5. Her küme için:
   - Kaç kaynak bildiriyor?
   - Hangi güvenilirlik kademesindeler?
   - En yüksek kademeli kaynağın başlığı kullanılır
   - En çok kaynaklı haber önce listelenir

### ═══════════════════════════════════════════════
### AŞAMA 3: Çapraz Doğrulama (Cross-Verification)
### ═══════════════════════════════════════════════

**Komut:** `hermes haber verify` veya `/haber verify`

```bash
hermes haber verify --category technology --limit 10
```

**Ne olur — detaylı:**

1. **İddia Çıkarma:** Her haberin başlık ve özetinden:
   - Büyük harfli özel isimler (kişi, kurum, yer)
   - Sayısal değerler (yüzde, para miktarı, yıl)
   - Eylem fiilleri (duyurdu, açıkladı, başlattı)
   
2. **Çapraz Referans:** Her iddia diğer kaynaklardaki aynı haberle karşılaştırılır:
   - 2+ kaynak aynı iddiayı bildiriyorsa → `verified`
   - Tek kaynak bildiriyorsa → `single_source`
   
3. **Sayısal Tutarsızlık Tespiti:** Aynı metrik için farklı kaynaklar farklı sayı bildiriyorsa tespit edilir.

4. **Seviye Belirleme:**

| Koşul | Seviye | Yayın? |
|-------|--------|--------|
| 2+ Tier 0 kaynak (Reuters, AP, AFP, BBC) | ✅ CONFIRMED | Otomatik |
| 1 Tier 0 + 1+ Tier 1 | 🟡 HIGH CONFIDENCE | Otomatik |
| 2+ Tier 1 kaynak | 🟠 MEDIUM CONFIDENCE | İnsan onayı önerilir |
| Tek kaynak / Tier 2+ | 🔴 LOW CONFIDENCE | İnsan onayı ZORUNLU |
| Hiçbir güvenilir kaynak yok | ⛔ UNVERIFIED | YAYINLANAMAZ |

5. Sayısal tutarsızlık varsa seviye bir kademe düşürülür.

6. **Rapor oluşturulur:** Hangi kaynaklar, hangi iddialar, hangi seviye.

### ═══════════════════════════════════════════════
### AŞAMA 4: Yayın Run'ı Oluşturma (Publish)
### ═══════════════════════════════════════════════

**Komut:** `hermes haber publish` veya `/haber publish`

```bash
hermes haber publish --category news --limit 5
# veya insan onayı olmadan:
hermes haber publish --auto
```

**Ne olur:**
1. `fetch` + `cluster` + `cross_verify` adımları otomatik çalışır
2. Doğrulanan her haber için `runs/active/{slug}/` klasörü oluşturulur
3. Klasöre yazılan dosyalar:
   - `haber-object.md` — ID, state, route, verification level
   - `idea.md` — Hangi kaynaklar, hangi URL'ler
   - `fact-check-report.md` — Çapraz doğrulama raporu (detaylı)
   - `context.md` — Writer Agent için kaynak özeti
4. State `cross_verified` (güvenli) veya `captured` (düşük güven) olarak ayarlanır
5. `--auto` flag'i ile CONFIRMED/HIGH seviyeli haberler otomatik `brief_ready`'e atlanır

### ═══════════════════════════════════════════════
### AŞAMA 5: Brief Hazırlığı
### ═══════════════════════════════════════════════

**Komut:** `/haber brief {slug}`

```yaml
hermes haber brief 2025-05-technology-company-new-chip
```

Bu aşamada `brief.md` dosyası oluşturulur. İki yöntem:

**Manuel (önerilen):**
İnsan yazar, kaynakları okuyarak brief'i yazar. `haber-object.md` ve `fact-check-report.md`'deki bilgiler kullanılır.

**LLM ile (deneysel):**
```bash
hermes haber brief 2025-05-technology-company-new-chip --llm
```

Brief şunları içermelidir:
- **Thesis:** Haberin özü (tek cümle)
- **Key Facts:** Kaynaklardan çıkarılan doğrulanmış bilgiler
- **Source List:** Kullanılan her kaynağın adı ve URL'si
- **Constraints:** Format, ton, uzunluk kuralları

**Önemli:** brief, Writer Agent'ın kullanacağı TEK bilgi kaynağıdır.
Brief'te olmayan hiçbir bilgi taslakta kullanılamaz.

### ═══════════════════════════════════════════════
### AŞAMA 6: Taslak Yazımı (Drafting)
### ═══════════════════════════════════════════════

**Komut:** `/haber draft {slug}`

```bash
hermes haber draft 2025-05-technology-company-new-chip
```

`draft-package.md` dosyası oluşturulur. Format:

```markdown
---
draft:
[Özet] Teknoloji şirketi yeni çipini duyurdu.

[Detaylar]
- Bu haber, 5 farklı kaynak tarafından doğrulandı.
- Başlıca kaynaklar: Reuters, Bloomberg, The Verge, Wired.
- Haber, 2 haber ajansı tarafından teyit edildi (en yüksek seviye).

[Kaynak]
- Reuters: https://...
- Bloomberg: https://...
- The Verge: https://...

#Haber #DoğrulanmışHaber #Teknoloji #Gündem

rubric_self_assessment:
- Tarafsızlık: 2/2
- Kaynak Gösterimi: 2/2
- Kısalık ve Netlik: 2/2
- Bilgi Yoğunluğu: 2/2
- Clickbait Uzaklığı: 2/2
- Format Yapısı: 2/2
TOTAL: 12/12

avoid_slop_pass:
- (clean)

voice_check:
- All rules followed: yes

source_attribution_check:
- Every claim sourced: yes
```

**Yazım Kuralları:**
- Her iddia bir kaynağa bağlı olmalı
- Spekülatif dil kullanılmaz ("could mean", "might suggest" yasak)
- Kaynak isimleri ve URL'ler orijinal dilinde kalır
- Tüm açıklayıcı metinler Türkçe olur
- Öznel ifadeler kesinlikle yasak

### ═══════════════════════════════════════════════
### AŞAMA 7: Taslak Doğrulama
### ═══════════════════════════════════════════════

İki ayrı denetimden geçer:

#### a) Halüsinasyon Taraması

**Komut:** `hermes haber hallucination {slug}`

```bash
hermes haber hallucination 2025-05-technology-company-new-chip
```

4 pattern taranır:

| Pattern | Tespit | Severity |
|---------|--------|----------|
| Kaynaksız istatistik | 200 karakter içinde kaynak adı yoksa | 🔴 high |
| Spekülatif dil | "could mean, might suggest, raises questions" | 🟡 medium |
| Sahipsiz alıntı | "..." içinde konuşan belli değilse | 🔴 high |
| Muğlak atıf | "it is believed that, critics say" | 🔴 high |

**Sonuç:** high severity bulgu yoksa → ✅ PASS

#### b) Slop Taraması

**Komut:** `hermes haber scan {slug}`

```bash
hermes haber scan 2025-05-technology-company-new-chip
```

54+ slop kalıbı 4 kademede taranır:
- **Tier 1 (Critical):** Promosyon dili, abartı, manipülatif ifadeler
- **Tier 2 (High):** Klişe, gereksiz sıfatlar, belirsizlik
- **Tier 3 (Medium):** Dolgu ifadeler, zayıf geçişler
- **Bonus (Tone):** Resmiyet dışı ton, uygunsuz samimiyet

### ═══════════════════════════════════════════════
### AŞAMA 8: Yayın (Publishing)
### ═══════════════════════════════════════════════

**Komut:** `/haber post {slug}`

```bash
hermes haber post 2025-05-technology-company-new-chip
```

Ne olur:
1. `draft-package.md` okunur
2. `draft:` bölümünden içerik çıkarılır
3. Memos API'sine POST isteği gönderilir
4. State `published` olarak güncellenir

**Writer Agent ile Otomatik Yayın:**

```bash
hermes haber auto-publish --limit 5 --category news
```

Writer Agent tüm pipeline'ı otomatik çalıştırır:
1. `fetch_all_news()` → haberleri çek
2. `cluster_stories()` → kümele
3. `cross_verify_story()` → doğrula
4. Puanla → en yüksek güvenilirlikten başlayarak sırala
5. Zaten var olanları atla
6. Yeni haberler için:
   - News run oluştur
   - Brief yaz
   - `generate_news()` ile Türkçe haber metni oluştur
   - Draft package yaz
   - Memos'a yayınla
7. 1sn bekle (rate limit)

### ═══════════════════════════════════════════════
### AŞAMA 9: Yayın Sonrası (Post-Publication)
### ═══════════════════════════════════════════════

Otomatik state geçişleri:
- `published` → `feedback_24h` (24 saat sonra)
- `feedback_24h` → `feedback_72h` (72 saat sonra)
- `feedback_72h` → `learned` (öğrenilen dersler çıkarılır)
- `learned` → `archived` (arşivlenir)

**Düzeltme mekanizması** her aşamada devreye girebilir:

```bash
# Hata düzeltme
hermes haber correct haber-slug "Yanlış tarih kullanıldı" --info "Doğru tarih: 15 Mayıs 2025"

# Tamamen geri çekme (ciddi hatalarda)
hermes haber correct haber-slug "Bilgi teyit edilemedi" --retract
```

**Postmortem analizi:**
```bash
hermes haber postmortem haber-slug --impressions 1500 --okunma 1200 --likes 45
```

### ═══════════════════════════════════════════════
### AŞAMA 10: Arşivleme
### ═══════════════════════════════════════════════

Öğrenilen dersler çıkarıldıktan sonra run arşivlenir:

```bash
hermes haber archive haber-slug
```

Arşivlenen run `runs/archive/{slug}/` altına taşınır.
`hermes haber runs` komutu arşivdekileri de gösterir (varsayılan).
Sadece aktifleri görmek için: `hermes haber runs --no-archive`

---

## 5. 18 Aşamalı State Makinesi

Her haber run'ı aşağıdaki 18 aşamadan geçer:

```
                  ┌─────────────────┐
                  │   captured      │ ← Haber sisteme ilk giriş
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
           ┌──────│  fact_checking  │ ← Çapraz doğrulama devam ediyor
           │      └────────┬────────┘
           │               │
           │               ▼
           │      ┌─────────────────┐
           │      │ cross_verified  │ ← İddialar kaynaklarda doğrulandı
           │      └────────┬────────┘
           │               │
           │               ▼
           │      ┌─────────────────┐
           │      │  idea_review    │ ← Rota kararı (route decision)
           │      └────────┬────────┘
           │               │
           │               ▼
           │      ┌─────────────────┐
           │      │  brief_ready    │ ← Writer Context Packet hazır
           │      └────────┬────────┘
           │               │
           │               ▼
           │      ┌─────────────────┐
           │      │   drafting      │ ← Taslak yazılıyor
           │      └────────┬────────┘
           │               │
           │               ▼
           │      ┌─────────────────┐
           │      │  verification   │ ← Denetim (halüsinasyon + slop)
           │      └────────┬────────┘
           │               │
           │               ▼
           │      ┌─────────────────┐
           │      │  draft_review   │ ← İnsan/LLM incelemesi
           │      └──┬─────────┬────┘
           │         │         │
           │         ▼         └────────┐
           │    ┌──────────┐           │
           │    │ approved  │    brief_ready'ye dön (revizyon)
           │    └─────┬─────┘
           │          │
           │          ▼
           │   ┌──────────────┐
           │   │scheduler_ready│
           │   └──────┬───────┘
           │          │
           │          ▼
           │   ┌──────────────┐
           │   │  scheduled   │
           │   └──────┬───────┘
           │          │
           │          ▼
           │   ┌──────────────┐
           │   │  published   │ ← Memos'a yayınlandı
           │   └──┬───────┬───┘
           │      │       │
           │      │       └──────────────────┐
           │      ▼                          ▼
           │  ┌─────────────┐      ┌──────────────────┐
           │  │feedback_24h │      │correction_needed  │ ← Hata tespit edildi
           │  └──────┬──────┘      └──────┬───────────┘
           │         │                    │
           │         ▼                    ├──────────┐
           │  ┌──────────────┐            │          │
           │  │ feedback_72h │            ▼          ▼
           │  └──────┬───────┘    ┌─────────┐  ┌──────────┐
           │         │           │corrected│  │retracted │
           │         ▼           └────┬─────┘  └────┬─────┘
           │    ┌─────────┐           │              │
           │    │ learned  │          │              │
           │    └────┬─────┘          │              │
           │         │                ▼              ▼
           │         ▼          ┌──────────────────────┐
           │   ┌─────────┐      │     (tekrar learned)  │
           │   │ archived │     └──────────────────────┘
           │   └─────────┘
           │
           └─── captured'a dönüş: doğrulama yetersizse
```

### Geçiş Tablosu

| Mevcut State | Geçebileceği State'ler |
|--------------|------------------------|
| `captured` | `fact_checking` |
| `fact_checking` | `cross_verified`, `captured` |
| `cross_verified` | `idea_review`, `captured` |
| `idea_review` | `brief_ready`, `captured` |
| `brief_ready` | `drafting` |
| `drafting` | `verification` |
| `verification` | `draft_review` |
| `draft_review` | `approved`, `brief_ready`, `captured` |
| `approved` | `scheduler_ready` |
| `scheduler_ready` | `scheduled` |
| `scheduled` | `published` |
| `published` | `feedback_24h`, `correction_needed` |
| `feedback_24h` | `feedback_72h`, `correction_needed` |
| `feedback_72h` | `learned`, `correction_needed` |
| `learned` | `archived`, `correction_needed` |
| `correction_needed` | `corrected`, `retracted` |
| `corrected` | `learned` |
| `retracted` | `archived` |
| `archived` | — (terminal) |

### State Değiştirme

```bash
# State görüntüle
hermes haber state haber-slug

# State güncelle
hermes haber state haber-slug --set brief_ready
```

---

## 6. Kaynak Güvenilirlik Sistemi

### Kademeler

| Kademe | Ağırlık | Tanım | Örnekler | Doğrulama Etkisi |
|--------|---------|-------|----------|------------------|
| **Tier 0 — PRIMARY** | 3 puan | Wire servisler | Reuters, AP, AFP, BBC | 2+ Tier 0 → CONFIRMED |
| **Tier 1 — MAJOR** | 2 puan | Büyük yayıncılar | Bloomberg, WSJ, FT, NYT, Guardian, WaPo, NPR, Al Jazeera, AA, BBC Türkçe, Euronews TR, DW Türkçe, Bloomberg HT | 1 Tier 0 + 1+ Tier 1 → HIGH CONFIDENCE |
| **Tier 2 — SPECIALIZED** | 1 puan | Uzman yayıncılar | Nature, MIT Tech Review, The Verge, Wired, HBR, ScienceDaily, T24, Medyascope, Diken, Duvar, BirGün, Sözcü, Cumhuriyet, Hürriyet, Webrazzi | 2+ Tier 1 → MEDIUM CONFIDENCE |
| **Tier 3 — SUPPLEMENTARY** | 1 puan | Yerel kaynaklar | (henüz eklenmemiş) | Tek kaynak → LOW CONFIDENCE |

### Doğrulama Skoru Hesaplama

```python
# weighted_score = sum(kaynakların ağırlıkları)
# primary_count = Tier 0 kaynak sayısı
# major_count = Tier 1 kaynak sayısı
# total_unique = toplam farklı kaynak sayısı

if primary_count >= 2 and total_unique >= 2:
    → CONFIRMED (Level 3)
elif primary_count >= 1 and major_count >= 1:
    → HIGH CONFIDENCE (Level 2)
elif major_count >= 2:
    → MEDIUM CONFIDENCE (Level 1)
elif total_unique >= 1:
    → LOW CONFIDENCE (Level 0)
else:
    → UNVERIFIED (Level -1)
```

### Yayın Eşiği

Varsayılan minimum yayın seviyesi: **Level 1 (MEDIUM CONFIDENCE)**
- **CONFIRMED / HIGH CONFIDENCE:** Otomatik yayın (insan onayı gerekmez)
- **MEDIUM CONFIDENCE:** İnsan onayı önerilir
- **LOW CONFIDENCE:** İnsan onayı ZORUNLU
- **UNVERIFIED:** Yayınlanamaz

### Tüm Kaynaklar

```bash
# Kaynak listesini görüntüle
hermes haber sources
```

Kaynak listesinde şu an 35+ kaynak bulunur:
- **Tier 0 (4):** Reuters, AP, AFP, BBC
- **Tier 1 (15):** Bloomberg, WSJ, FT, Guardian, NYT, Washington Post, Economist, CNBC, NPR, Al Jazeera, AA, BBC Türkçe, Euronews TR, DW Türkçe, Bloomberg HT
- **Tier 2 (15+):** Nature, MIT Tech Review, The Verge, Wired, HBR, ScienceDaily, T24, Medyascope, Gazete Duvar, Diken, BirGün, Sözcü, Cumhuriyet, Hürriyet, Webrazzi

---

## 7. Komut Referansı

### Haber Toplama & Doğrulama

| Komut | Açıklama |
|-------|----------|
| `hermes haber sources` | Tüm haber kaynaklarını kademelere göre listeler |
| `hermes haber fetch [--category] [--limit]` | Haberleri çeker ve kümeler |
| `hermes haber verify [--category] [--limit]` | Çeker, kümeler, çapraz doğrular |
| `hermes haber publish [--category] [--limit] [--auto]` | Doğrulanmış haberleri run'a ekler |
| `hermes haber correct <slug> <hata> [--retract] [--info]` | Düzeltme/retraction yayınlar |
| `hermes haber hallucination <slug>` | Halüsinasyon taraması yapar |

### Writer Agent

| Komut | Açıklama |
|-------|----------|
| `hermes haber auto-publish [--limit] [--category]` | Tam otomatik: çek → doğrula → yaz → yayınla |
| `hermes haber brief <slug> [--llm]` | Brief hazırlık aşamasına geçer |
| `hermes haber draft <slug> [--llm]` | Taslak aşamasına geçer |
| `hermes haber verify-draft <slug> [--llm]` | Taslak doğrulama aşamasına geçer |
| `hermes haber post <slug>` | Taslağı Memos'a yayınlar |

### Kalite Kontrol

| Komut | Açıklama |
|-------|----------|
| `hermes haber scan <slug>` | 54+ slop kalıbı taraması |
| `hermes haber score <slug>` | 12 maddelik rubric puanlaması |

### Sistem & Bilgi

| Komut | Açıklama |
|-------|----------|
| `hermes haber setup` | Dizin yapısını başlatır |
| `hermes haber status` | Tüm aktif run'ların state'lerini gösterir |
| `hermes haber audit` | Tam sistem denetimi |
| `hermes haber state [slug] [--set]` | State görüntüle/güncelle |
| `hermes haber runs [--no-archive]` | Tüm run'ları listeler |
| `hermes haber search <query>` | Run'larda arama |
| `hermes haber context <slug>` | Run bağlamını gösterir |
| `hermes haber learnings [--topic]` | Önceki run'lardan öğrenilenler |
| `hermes haber patterns` | Run pattern analizi |
| `hermes haber voice-update` | Ses profilini gösterir |

### Run Yönetimi

| Komut | Açıklama |
|-------|----------|
| `hermes haber new <idea> [--slug] [--source]` | Yeni run oluşturur (haber dışı içerik) |
| `hermes haber route <idea> [--source]` | Fikir için rota belirler |
| `hermes haber postmortem <slug> [--impressions]` | Yayın sonrası analiz |
| `hermes haber archive <slug>` | Run'ı arşivler |
| `hermes haber signal [x\|rss]` | Sinyal taraması |

---

## 8. Adım Adım Örnek Senaryo

### Senaryo: Teknoloji Haberini Doğrulama ve Yayınlama

**1. Haberleri çekelim:**

```bash
hermes haber fetch --category technology --limit 10
```

Çıktı:
```
📡 News Fetch Results
  47 items from sources → 12 story clusters

Top 10 Stories by Source Coverage
┌─────┬──────────────────────────────────────┬─────────┬───────────┬──────────┐
│ #   │ Title                                │ Sources │ Tiers     │ Verified?│
├─────┼──────────────────────────────────────┼─────────┼───────────┼──────────┤
│ 1   │ Apple unveils new AI-powered iPhone  │ 5       │ T0:2 T1:3 │ ✅       │
│ 2   │ Google launches Gemini 3.0 model     │ 4       │ T0:2 T1:2 │ ✅       │
│ ... │                                      │         │           │          │
```

**2. Bir haberi detaylı doğrulayalım:**

```bash
hermes haber verify --limit 5
```

En çok kaynaklı haberler sıralanır ve her biri için doğrulama seviyesi gösterilir.

**3. En güvenilir haberi yayına hazırlayalım:**

```bash
hermes haber publish --category technology --limit 3
```

Bu komut:
- En çok kaynaklı 3 haberi alır
- Çapraz doğrular
- Her biri için `runs/active/{slug}/` klasörü oluşturur
- `fact-check-report.md` yazar

Çıktı:
```
✅ Publish Results

  ✅ 2025-05-apple-unveils-new-ai
     Route: VERIFIED | State: cross_verified
     ✅ CONFIRMED — Multiple primary sources

  ✅ 2025-05-google-launches-gemini
     Route: VERIFIED | State: cross_verified
     🟡 HIGH CONFIDENCE — Primary + major sources
```

**4. Kısa metin yaz ve yayınla (Writer Agent ile otomatik):**

```bash
hermes haber auto-publish --limit 3 --category technology
```

Writer Agent:
1. Her haber için brief oluşturur
2. Türkçe haber metni üretir ([Özet]-[Detaylar]-[Kaynak] formatında)
3. Draft package yazar
4. Memos'a yayınlar

Çıktı:
```
🤖 Writer Agent — 3 haber yayınlandı

  ✅ Apple yeni yapay zeka destekli iPhone'u tanıttı — Level: CONFIRMED
  ✅ Google Gemini 3.0 modelini kullanıma sundu — Level: HIGH_CONFIDENCE
  ✅ Yeni nesil çip teknolojisi %40 daha hızlı — Level: CONFIRMED
```

**5. Yayın sonrası kontrol:**

```bash
hermes haber status
```

```bash
# Halüsinasyon taraması (yayın öncesinde de kullanılabilir)
hermes haber hallucination 2025-05-apple-unveils-new-ai
```

**6. Hata durumunda düzeltme:**

```bash
hermes haber correct 2025-05-apple-unveils-new-ai "Çip hızı %40 olarak belirtilmişti, doğrusu %35" --info "Doğru: %35 daha hızlı"
```

**7. Arşivleme:**

```bash
hermes haber archive 2025-05-apple-unveils-new-ai
```

---

## 9. Sık Sorulan Sorular

### ❓ Haber kaynağı ekleyebilir miyim?

Kaynak eklemek için `haber_kurator_core.py` dosyasındaki `NEWS_SOURCES` sözlüğüne yeni bir `NewsSource` eklenir. Planlanan özellik: `hermes haber source-add ...`

### ❓ RSS beslemesi çalışmazsa ne olur?

Hata alan beslemeler sessizce atlanır ve log'a yazılır. Diğer kaynaklardan çekme devam eder. Tüm kaynaklar hata verirse sonuç boş liste döner.

### ❓ Bir haber hem Türkçe hem İngilizce kaynaklarda varsa?

Çapraz dil desteği sayesinde `savaş/war`, `ekonomi/economy` gibi kelimeler normalize edilerek eşleştirilir. Örtüşme ≥%30 ise aynı haber kabul edilir.

### ❓ Yanlış haber yayınlanırsa ne olur?

`hermes haber correct {slug} "hata" --info "doğrusu"` ile düzeltme yayınlanır.
Ciddi hatalarda `--retract` ile haber tamamen geri çekilir.

### ❓ Writer Agent hangi LLM'i kullanır?

Writer Agent, haber metni üretimi için Hermes Agent'in yardımcı LLM'ini (auxiliary_client) kullanır. Başlıkları İngilizceden Türkçeye çevirir. LLM yoksa orijinal başlık korunur.

### ❓ `--auto` güvenli mi?

`--auto`, yalnızca **CONFIRMED** (Level 3) veya **HIGH CONFIDENCE** (Level 2) seviyesindeki haberleri otomatik onaylar. Düşük seviyeli haberler her zaman insan onayına bırakılır.

### ❓ Memos'a bağlantı sorunu?

1. `MEMOS_TOKEN`'ın doğru ayarlandığından emin olun
2. API URL'sini kontrol edin: `MEMOS_API_URL=https://memos.googig.cloud/api/v1/memos`
3. `.env` dosyasının plugin dizininde veya `~/.hermes/.env`'de olduğundan emin olun

### ❓ Run sayısı çok fazla, performans etkilenir mi?

Run'lar dosya sistemi üzerinde tutulur. Çok sayıda run varsa `hermes haber archive` ile öğrenilen run'lar arşivlenebilir. State cache'i SQLite ile yönetilir (1000+ run için optimize).

---

> **Haber-Kuratör v3.0.0** — Memos Küratörü
> Sorularınızı `/haber help` ile veya doğrudan Hermes Agent üzerinden iletebilirsiniz.
