# Haber Kuratör v3.0.0 — Kapsamlı Kullanıcı Kılavuzu

> **News Verification Engine** — Çok kaynaklı haber doğrulama sistemi.
> Dünyanın önde gelen 35 güvenilir kaynağından haber çeker, çapraz doğrular
> ve Memos platformunda yayınlar.
>
> **Plugin:** `~/.hermes/plugins/haber-kurator/`
> **Kaynak:** Memos Küratörü — Tarafsız Haber ve Bilgi Akışı

---

## 📋 İçindekiler

1. [Giriş — Haber Kuratör Nedir?](#1-giriş--haber-kuratör-nedir)
2. [Mimariye Genel Bakış](#2-mimariye-genel-bakış)
3. [Kaynak Güvenilirlik Sistemi](#3-kaynak-güvenilirlik-sistemi)
4. [Çapraz Doğrulama Motoru](#4-çapraz-doğrulama-motoru)
5. [Writer Agent — Otomatik Haber Üretimi](#5-writer-agent--otomatik-haber-üretimi)
6. [19-State Lifecycle](#6-19-state-lifecycle)
7. [Kalite Kontrolleri](#7-kalite-kontrolleri)
8. [Düzeltme Workflow'u](#8-düzeltme-workflowu)
9. [Kurulum ve Yapılandırma](#9-kurulum-ve-yapılandırma)
10. [Komut Referansı](#10-komut-referansı)
11. [Proje Yapısı](#11-proje-yapısı)
12. [Sorun Giderme](#12-sorun-giderme)

---

## 1. Giriş — Haber Kuratör Nedir?

**Haber Kuratör**, haber üretimini uçtan uca otomatize eden bir doğrulama sistemidir:

1. **📡 Kaynaklardan haber çeker** — Reuters, AP, AFP, BBC, Bloomberg gibi 35 küresel kaynaktan RSS beslemeleri
2. **🔍 Çapraz doğrular** — Aynı haberi 2+ kaynakta karşılaştırır, doğruluk seviyesi belirler
3. **🤖 Türkçe haber üretir** — Writer Agent ile [Özet] - [Detaylar] - [Kaynak] formatında yazar
4. **📤 Memos'ta yayınlar** — API üzerinden otomatik paylaşım

### 1.1 Felsefe

```
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   Bu bir HABER SİSTEMİDİR.                                      ║
║                                                                  ║
║   ▌ Sonuçlar GERÇEK olmalı                                      ║
║   ▌ Sahte haber infiale yol açar                                ║
║   ▌ Her iddia bir kaynağa dayanmalı                             ║
║   ▌ 2+ bağımsız kaynakta doğrulanmayan haber yayınlanmaz        ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
```

### 1.2 Ne İşe Yarar?

| Yetenek | Açıklama |
|---------|----------|
| **📡 Haber Toplama** | 35 kaynaktan RSS/Atom beslemesi çeker, tekilleştirir |
| **🔍 Kümeleme** | Aynı haberi farklı kaynaklardan gruplar (EN/TR çapraz dil) |
| **✅ Çapraz Doğrulama** | Her haberin kaç kaynakta, hangi kademede bildirildiğini analiz eder |
| **🤖 Writer Agent** | Doğrulanmış haberleri Türkçe otomatik yazar |
| **📤 Memos Yayını** | API üzerinden otomatik paylaşım |
| **🛡️ Halüsinasyon Koruması** | Kaynaksız iddia, uydurma alıntı, spekülasyon tespiti |
| **🔬 Slop Taraması** | 122 pattern ile AI kokusu tespiti |
| **📊 State Yönetimi** | 19-state lifecycle ile her haberin durumunu takip |
| **✏️ Düzeltme** | Yayın sonrası hata durumunda correction/retraction |

---

## 2. Mimariye Genel Bakış

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                      HABER KURATÖR v3.0.0 — MİMARİ                      ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                           ║
║  📡 KAYNAK KATMANI                                                        ║
║  ┌─────────────────────────────────────────────────────────────────┐     ║
║  │ Tier 0: Reuters, AP, AFP, BBC                                  │     ║
║  │ Tier 1: Bloomberg, WSJ, FT, NYT, Guardian, WaPo, Al Jazeera... │     ║
║  │ Tier 2: Nature, MIT Tech Review, Wired...                      │     ║
║  │ Tier TR: AA, BBC Türkçe, Euronews TR, T24, Diken, Sözcü...    │     ║
║  └─────────────────────────────────────────────────────────────────┘     ║
║                                    │                                     ║
║                                    ▼                                     ║
║  🔍 DOĞRULAMA KATMANI                                                    ║
║  ┌─────────────────────────────────────────────────────────────────┐     ║
║  │ 1. fetch_all_news() → RSS/Atom beslemeleri çekilir              │     ║
║  │ 2. _deduplicate_news() → URL + başlık bazında tekilleştirme    │     ║
║  │ 3. cluster_stories() → Aynı haber kümelenir (EN/TR destekli)    │     ║
║  │ 4. cross_verify_story() → Doğrulama seviyesi belirlenir        │     ║
║  └─────────────────────────────────────────────────────────────────┘     ║
║                                    │                                     ║
║                                    ▼                                     ║
║  🤖 ÜRETİM KATMANI (Writer Agent)                                       ║
║  ┌─────────────────────────────────────────────────────────────────┐     ║
║  │ 5. publish_verified_news() → Run klasörü oluşturulur            │     ║
║  │ 6. generate_news() → Türkçe haber metni yazılır                │     ║
║  │    [Özet] - [Detaylar] - [Kaynak] formatında                   │     ║
║  │ 7. hallucination_check() → Halüsinasyon taranır                │     ║
║  │ 8. scan_slop() → Slop pattern kontrolü                         │     ║
║  └─────────────────────────────────────────────────────────────────┘     ║
║                                    │                                     ║
║                                    ▼                                     ║
║  📤 YAYIN KATMANI                                                         ║
║  ┌─────────────────────────────────────────────────────────────────┐     ║
║  │ 9. post_to_memos() → Memos API'sine POST                       │     ║
║  │ 10. correction workflow → Hata varsa düzeltme                  │     ║
║  └─────────────────────────────────────────────────────────────────┘     ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

---

## 3. Kaynak Güvenilirlik Sistemi

### 3.1 Güvenilirlik Kademeleri

Sistem, her haber kaynağını 4 kademede sınıflandırır:

| Kademe | Ağırlık | Açıklama | Örnekler |
|--------|---------|----------|---------|
| **Tier 0 (PRIMARY)** | 3 | Wire servisler — en yüksek güvenilirlik | Reuters, AP, AFP, BBC |
| **Tier 1 (MAJOR)** | 2 | Büyük yayıncılar — yüksek güvenilirlik | Bloomberg, WSJ, FT, NYT, Guardian |
| **Tier 2 (SPECIALIZED)** | 1 | Uzman yayıncılar — orta-yüksek | Nature, MIT Tech Review, Wired |
| **Tier TR** | 1-2 | Türkçe kaynaklar | AA (1), BBC Türkçe (2), Euronews TR (2), T24 (1) |

### 3.2 35 Kaynak Listesi

Toplam 35 kaynak tanımlıdır:

**Tier 0 (5):** Reuters, AP, AFP, BBC, Reuters Investigates

**Tier 1 (15):** Bloomberg, WSJ, FT, Guardian, NYT, Washington Post, Al Jazeera, NPR, Economist, CNBC, NYT Tech, WaPo Tech + **Türkçe:** AA, BBC Türkçe, Euronews TR, Deutsche Welle TR, Bloomberg HT

**Tier 2 (15+):** Nature, MIT Tech Review, The Verge, Wired, HBR, ScienceDaily + **Türkçe:** T24, Medyascope, Gazete Duvar, Diken, BirGün, Sözcü, Cumhuriyet, Hürriyet, Webrazzi

### 3.3 Çapraz Dil Desteği (EN/TR)

Sistem, İngilizce ve Türkçe haberleri ortak anahtar kelimelerle kümeler:

```
"interest rate" = "faiz" → "interest-rate"
"earthquake" = "deprem" → "earthquake"
"election" = "seçim" → "election"
"inflation" = "enflasyon" → "inflation"
"announced" = "açıkladı" → "announced"
```

30+ ortak terim ile İngilizce Reuters haberi ile Türkçe BBC haberi aynı kümeye düşer.

---

## 4. Çapraz Doğrulama Motoru

### 4.1 Doğrulama Seviyeleri

| Seviye | Değer | Koşul | Otomatik Yayın? |
|--------|-------|-------|----------------|
| ✅ **CONFIRMED** | 3 | 2+ farklı Tier 0 kaynak | ✅ Evet |
| 🟡 **HIGH CONFIDENCE** | 2 | 1 Tier 0 + 1 Tier 1 | ✅ Evet |
| 🟠 **MEDIUM CONFIDENCE** | 1 | 2+ Tier 1 | ⚠️ İnsan önerilir |
| 🔴 **LOW CONFIDENCE** | 0 | Tek kaynak / sadece Tier 2+ | ❌ Hayır |
| ⛔ **UNVERIFIED** | -1 | Doğrulanamaz | ❌ Bloke |

### 4.2 İddia Çıkarımı

Cross-verification, RSS özetlerinden otomatik olarak iddiaları çıkarır:

- **Proper noun çıkarımı:** Büyük harfli isimler (Trump, Beijing, Taiwan, Ebola)
- **Sayısal veri:** Yüzdeler, miktarlar, yıllar
- **Aksiyon fiilleri:** announced, launched, reported, confirmed, killed

Aynı iddia 2+ kaynakta geçiyorsa **"verified"** olarak işaretlenir.

### 4.3 Sayısal Tutarsızlık Tespiti

Farklı kaynaklar aynı konuda farklı rakam veriyorsa (örn: "65 ölü" vs "80 ölü"), sistem bunu tespit eder ve doğrulama seviyesini bir kademe düşürür.

---

## 5. Writer Agent — Otomatik Haber Üretimi

### 5.1 Nasıl Çalışır?

Writer Agent (`writer_agent.py`) doğrulanmış haber kümelerini alır ve Türkçe haber metni üretir:

1. **Haber başlığını alır** — En yüksek kademeli kaynaktan
2. **Kaynak listesini oluşturur** — Tüm bildiren kaynaklar
3. **Doğrulama seviyesini ekler** — Kaç kaynak, hangi kademeler
4. **Türkçe haber metni yazar** — [Özet] - [Detaylar] - [Kaynak] formatında
5. **Memos'a gönderir** — API üzerinden yayınlar

### 5.2 Çıktı Formatı

```markdown
[Özet] Trump, Tayvan'a yönelik silah satışlarını Çin ile yürüttüğü
müzakerelerde "çok iyi bir pazarlık kozu" olarak kullandığını
belirterek, ABD'nin bölgedeki geleneksel politikasında stratejik
bir değişime gitti.

[Detaylar]
- Bu haber, 5 bağımsız kaynak tarafından teyit edildi.
- Başlıca kaynaklar: Associated Press (AP), BBC News, CNBC.
- Haber, 2 farklı haber ajansı (Tier 0) tarafından doğrulandı.
- ...

[Kaynak]
- AP: nytimes.com/world/asia
- BBC News: bbc.com/news/articles
- CNBC: cnbc.com/2026/05/15/trump-china-xi-taiwan

#Haber #DoğrulanmışHaber #Gündem
```

### 5.3 Kullanım

```bash
# Writer Agent ile otomatik yayın
python3 writer_agent.py --limit 5

# Sadece belirli kategoriler
python3 writer_agent.py --limit 3 --category technology
python3 writer_agent.py --limit 3 --category business

# Hermes CLI üzerinden
hermes haber auto-publish --limit 5
hermes haber auto-publish --limit 3 --category science

# Slash komut
/haber auto-publish 5
```

---

## 6. 19-State Lifecycle

Her haber içerik objesi 19 state'ten geçer:

```
captured → fact_checking → cross_verified → idea_review → brief_ready
→ drafting → verification → draft_review → approved → scheduler_ready
→ scheduled → published → feedback_24h → feedback_72h → learned
→ [correction_needed → corrected / retracted] → archived
```

### State Detayları

| State | Ne Anlama Gelir | Ne Yapılır |
|-------|----------------|-----------|
| **captured** | Haber sisteme ilk kez girdi | fetch veya manuel |
| **fact_checking** | 🔄 Çapraz doğrulama devam ediyor | Bekle |
| **cross_verified** | ✅ Haber doğrulandı | Brief yazılabilir |
| **idea_review** | Rota kararı verildi | brief.md hazırlanır |
| **brief_ready** | Writer Context Packet yazıldı | Draft'a geç |
| **drafting** | Haber metni yazıldı | Verifier çalıştır |
| **verification** | Doğrulama kontrolü yapıldı | İncele |
| **draft_review** | İnsan onayı bekleniyor | APPROVE/REVISE/REJECT |
| **approved** | Yayın onayı verildi | Scheduler'a hazırla |
| **scheduler_ready** | Yayına hazır | Memos'a gönder |
| **scheduled** | Zamanlandı | Yayınlanmasını bekle |
| **published** | 🎉 Yayında! | 24s metrik bekle |
| **feedback_24h** | İlk metrikler toplandı | 72s bekle |
| **feedback_72h** | Derin analiz yapıldı | Öğrenim çıkar |
| **learned** | Öğrenimler kaydedildi | Arşivle |
| **correction_needed** | 🔄 Hata tespit edildi | Düzeltme yaz |
| **corrected** | Düzeltme yayınlandı | Learned'e geç |
| **retracted** | Haber geri çekildi | Arşivle |
| **archived** | 📦 Arşivlendi | — |

---

## 7. Kalite Kontrolleri

### 7.1 Slop Taraması

**122 regex pattern** ile AI içerik kokusu tespiti:

| Tier | Adet | Eşik (REVISE) | Eşik (REJECT) | Örnekler |
|------|------|--------------|--------------|----------|
| 🔴 **Tier 1** | 45 | ≥1 | ≥3 | "groundbreaking", "game-changing", "experts believe", "actually" |
| 🟡 **Tier 2** | 32 | ≥3 | ≥5 | "serves as", "leveraging", "let's dive in" |
| 🟢 **Tier 3** | 31 | ≥8 | ≥15 | passive voice, "very", "recently" |
| ⚪ **Bonus** | 14 | kontekst bazlı | — | "you should", "it feels like" |

### 7.2 Halüsinasyon Koruması

Otomatik olarak taranan unsurlar:

- **Sayısal iddialar:** Kaynağı belirtilmemiş istatistikler flag'lenir
- **Uydurma alıntılar:** Konuşmacısı belirtilmemiş alıntılar tespit edilir
- **Spekülasyon:** "could mean", "might indicate", "raises questions" yakalanır
- **Kaynaksız iddialar:** "experts believe", "critics say" gibi belirsiz atıflar

**Türkçe destek:** "bildirdi", "açıkladı", "belirtti", "sözleriyle", "tanımladı" gibi Türkçe atıf kelimeleri tanınır.

---

## 8. Düzeltme Workflow'u

Yayın sonrası hata tespit edilirse:

```bash
# Düzeltme yayınla
hermes haber correct <slug> "hata açıklaması" --info "doğru bilgi"

# Haberi tamamen geri çek (ciddi hatalar için)
hermes haber correct <slug> --retract

# Otomatik hata tespiti (feedback'te anahtar kelime ara)
haber_kurator_manager(action='check_correction', slug='...')
```

Düzeltme süreci:
1. `correction.md` dosyası run klasörüne yazılır
2. State `correction_needed` → `corrected` veya `retracted` olur
3. Düzeltme notu ilgili Memos gönderisine eklenir

---

## 9. Kurulum ve Yapılandırma

### 9.1 Plugin Yükleme

```bash
# Plugin dosyalarını Hermes home'a kopyala
cp -r haber-kurator /usr/local/lib/hermes-agent/plugins/haber-kurator/
```

### 9.2 Memos API Token

```bash
# .env dosyasını düzenle
cat > ~/.hermes/plugins/haber-kurator/.env << 'EOF'
MEMOS_TOKEN="memos_pat_xxx..."
MEMOS_API_URL="https://memos.googig.cloud/api/v1/memos"
EOF
```

### 9.3 İlk Kurulum

```bash
# Dizin yapısını oluştur
hermes haber setup

# Sistem sağlık kontrolü
hermes haber audit

# Kaynakları doğrula
hermes haber sources
```

### 9.4 Writer Agent Cronjob

```bash
# Her 2 saatte bir Writer Agent çalıştır
cronjob create \
  --schedule "0 */2 * * *" \
  --name "news-auto-publisher" \
  --prompt "Run the haber-kurator Writer Agent: auto-publish up to 5 verified news articles to Memos. Use action='auto_publish' with limit=5." \
  --workdir "/home/asus/.hermes/plugins/haber-kurator"
```

---

## 10. Komut Referansı

### 10.1 CLI (`hermes haber ...`)

| Komut | Açıklama |
|-------|----------|
| `fetch [--category]` | 📡 Tüm 35 kaynaktan haber çek |
| `verify [--category] [--limit]` | 🔍 Kümele + çapraz doğrula |
| `publish [--category] [--limit] [--auto]` | 📰 Doğrulanan haberleri sisteme al |
| `auto-publish [--limit] [--category]` | 🤖 Writer Agent: otomatik haber üret + Memos'a yayınla |
| `post <slug>` | 📤 Draft'ı Memos'ta yayınla |
| `correct <slug> <hata> [--info] [--retract]` | ✏️ Düzeltme veya geri çekme yayınla |
| `hallucination <slug>` | 🔬 Halüsinasyon kontrolü |
| `scan <slug>` | 🔎 Slop pattern taraması |
| `score <slug>` | 📊 Rubric puanlama (0-12) |
| `sources` | 🌍 Kaynak listesini göster |
| `status` | 📋 Run durumlarını göster |
| `audit` | 🔍 Sistem sağlık kontrolü |
| `runs [--no-archive]` | 📂 Tüm run'ları listele |
| `search <query>` | 🔎 Run içeriklerinde ara |
| `new <idea> [--source]` | 🆕 Yeni run oluştur |
| `route <idea> [--source]` | 🗺️ Rota belirle |
| `state [slug] [--set]` | 🔁 State görüntüle/güncelle |
| `brief <slug>` | 📝 Brief hazırla |
| `draft <slug>` | ✍️ Draft hazırla |
| `verify-draft <slug>` | 🔍 Draft'ı doğrula |
| `signal [x\|rss]` | 📶 Sinyal tara |
| `postmortem <slug>` | 📊 Yayın analizi |
| `learnings [--topic]` | 📝 Öğrenimleri göster |
| `patterns` | 📊 Pattern analizi |
| `archive <slug>` | 📦 Run'ı arşivle |
| `context <slug>` | 📄 Run bağlamını göster |
| `voice-update` | 🗣️ Üslup profilini göster |
| `setup` | 🚀 İlk kurulum |

### 10.2 Slash Komutları (`/haber ...`)

| Komut | Açıklama |
|-------|----------|
| `fetch` | 📡 Haber çek |
| `verify` | 🔍 Çapraz doğrula |
| `publish [N] [kategori] [--auto]` | 📰 Haberleri sisteme al |
| `auto-publish [N]` | 🤖 Writer Agent ile otomatik yayınla |
| `post <slug>` | 📤 Memos'ta yayınla |
| `correct <slug>` | ✏️ Düzeltme |
| `hallucination <slug>` | 🔬 Halüsinasyon kontrolü |
| `scan <slug>` | 🔎 Slop tara |
| `score <slug>` | 📊 Rubric puanla |
| `sources` | 🌍 Kaynak listesi |
| `status` | 📋 Run durumu |
| `audit` | 🔍 Sistem sağlığı |
| `runs` | 📂 Tüm runlar |
| `search <query>` | 🔎 Run ara |
| `new <idea>` | 🆕 Yeni run |
| `route <idea>` | 🗺️ Rota belirle |
| `state [slug]` | 🔁 State gör |
| `brief <slug>` | 📝 Brief hazırla |
| `draft <slug>` | ✍️ Draft hazırla |
| `verify-draft <slug>` | 🔍 Draft'ı doğrula |
| `signal [x\|rss]` | 📶 Sinyal tara |
| `postmortem <slug>` | 📊 Yayın analizi |
| `context <slug>` | 📄 Run bağlamı |
| `setup` | 🚀 İlk kurulum |
| `archive <slug>` | 📦 Arşivle |
| `learnings` | 📝 Öğrenimler |
| `patterns` | 📊 Pattern analizi |
| `voice-update` | 🗣️ Ses profilini görüntüle |

### 10.3 Tool Actions (`haber_kurator_manager`)

| Action | Parametreler | Açıklama |
|--------|-------------|----------|
| `fetch_news` | `category` | 📡 35 kaynaktan haber çek |
| `verify_news` | `category`, `limit` | 🔍 Kümele + çapraz doğrula |
| `publish_verified` | `category`, `limit`, `human_review` | 📰 Doğrulanan haberleri sisteme al |
| `auto_publish` | `limit`, `category` | 🤖 Writer Agent ile otomatik yayınla |
| `cross_verify_story` | `cluster_data` | ✅ Tek küme çapraz doğrula |
| `hallucination_check` | `slug` | 🔬 Halüsinasyon tara |
| `issue_correction` | `slug`, `error_description`, `correct_information`, `retract` | ✏️ Düzeltme yayınla |
| `check_correction` | `slug` | 🔍 Hata kontrolü |
| `scan_slop` | `text` | 🔎 Slop tara |
| `score` | `slug` | 📊 Rubric puanla |
| `sources` | — | 🌍 Kaynak listesi |
| `list` | `include_archived` | 📂 Run'ları listele |
| `new_run` | `idea`, `slug`, `source_hint` | 🆕 Yeni run oluştur |
| `update_state` | `slug`, `state` | 🔁 State güncelle |
| `get_state` | `slug` | 🔍 State görüntüle |
| `decide_route` | `idea`, `source_hint` | 🗺️ Rota belirle |
| `search_runs` | `query` | 🔎 Run ara |
| `archive_run` | `slug` | 📦 Arşivle |
| `postmortem` | `slug`, `metrics` | 📊 Yayın analizi |
| `generate_brief` | `slug`, `extra_context` | 📝 Brief oluştur |
| `generate_draft` | `slug` | ✍️ Draft oluştur |
| `run_verifier` | `slug` | 🔍 Verifier çalıştır |
| `signal` | `source` | 📶 Sinyal tara |
| `update_voice` | `updates` | 🗣️ Ses profili güncelle |
| `get_learnings` | `topic` | 📝 Öğrenimleri getir |
| `analyze_patterns` | — | 📊 Pattern analizi |
| `setup` | — | 🚀 İlk kurulum |
| `audit` | — | 🔍 Sistem sağlığı |

### Retriever Actions (`haber_kurator_retriever`)

| Action | Parametreler | Açıklama |
|--------|-------------|----------|
| `sources` | — | Tüm kaynakların listesi |
| `source_summary` | — | Kaynak özeti (kademeler) |
| `strategy` | — | Strateji dosyaları |
| `voice` | — | Ses profili + slop pattern |
| `run` | `slug` | Run dosyaları |
| `stores` | — | Depo dosyaları |
| `learnings` | `topic` | Öğrenimler |

---

## 11. Proje Yapısı

```
haber-kurator/
│
├── haber_kurator_core.py         ⭐ Ana motor (3649+ satır)
│   ├── SourceTier (Enum)         Kaynak güvenilirlik kademeleri
│   ├── VerificationLevel (Enum)  Doğrulama seviyeleri
│   ├── FactClaim                 İddia doğrulama sınıfı
│   ├── CrossVerificationResult   Çapraz doğrulama sonucu
│   ├── HaberKuratorCore          Ana sınıf (tüm iş mantığı)
│   │   ├── fetch_all_news()      Haber çekme
│   │   ├── cluster_stories()     Kümeleme (EN/TR)
│   │   ├── cross_verify_story()  Çapraz doğrulama
│   │   ├── create_news_run()     Run oluşturma
│   │   ├── publish_verified_news() Otomatik yayın
│   │   ├── hallucination_check() Halüsinasyon tespiti
│   │   ├── issue_correction()    Düzeltme
│   │   ├── scan_slop()           Slop taraması
│   │   └── ... (40+ metod)
│   └── NEWS_SOURCES              35 kaynak tanımı
│
├── writer_agent.py               🤖 Writer Agent
│   ├── WriterAgent               Otomatik haber üretimi + yayın
│   │   ├── generate_news()       Türkçe haber metni yaz
│   │   ├── post_to_memos()       Memos API çağrısı
│   │   └── auto_publish()        Uçtan uca pipeline
│   └── main()                    CLI entry point
│
├── memos_cli.py                  📤 Memos API istemcisi
│   └── post_memo()               POST /api/v1/memos
│
├── __init__.py                   🔌 Plugin kayıt
│   ├── register()                Tool/Slash/CLI/Hook kaydı
│   ├── haber_kurator_manager     Tool (30+ action)
│   ├── haber_kurator_retriever   Bilgi alma tool'u
│   └── memos_publisher           Yayın tool'u
│
├── cli.py                        📋 CLI komut ağacı
│   └── register_cli()            25+ komut
│
├── plugin.yaml                   Plugin manifest
├── SKILL.md                      Skill tanımı
├── README.md                     Bu dosya
│
├── strategy/
│   ├── source-watchlist.md       📡 35 kaynak (Tier 0-3)
│   ├── positioning.md            🎯 Konumlandırma
│   ├── audience.md               👥 Hedef kitle
│   └── pillars.md                📚 İçerik konuları
│
├── voice/
│   ├── voice-profile.md          🗣️ Üslup kuralları
│   └── master-avoid-slop.md      🚫 122 slop pattern
│
├── runs/
│   ├── active/{slug}/            📂 Aktif haberler
│   │   ├── haber-object.md       ID, state, route, verification
│   │   ├── idea.md               Kaynak listesi + rota
│   │   ├── fact-check-report.md  Çapraz doğrulama raporu
│   │   ├── context.md            Yazar bağlamı
│   │   ├── brief.md              Writer Context Packet
│   │   ├── draft-package.md      Haber metni
│   │   └── correction.md         Düzeltme (varsa)
│   └── archive/                  📦 Arşiv
│
├── stores/
│   ├── inbox.md                  Ham fikirler
│   ├── ideas/                    Olgunlaşmış fikirler
│   ├── hooks/                    Hook pattern'leri
│   ├── proof/                    Kanıtlar
│   └── feedback/                 Geri bildirimler
│
├── workflows/
│   ├── idea-to-published-post.md Ana workflow
│   ├── verifier-checklist.md     Verifier kontrol listesi
│   └── ...
│
├── references/                   Referans dokümanlar
└── .env                          🔑 Memos API token
```

---

## 12. Sorun Giderme

### 12.1 RSS Beslemesi Çalışmıyor

```bash
# Kaynakların durumunu kontrol et
hermes haber sources

# Tek kaynak testi
python3 -c "
from haber_kurator_core import HaberKuratorCore, NEWS_SOURCES
from pathlib import Path
core = HaberKuratorCore(Path('.'))
items = core.fetch_all_news()
print(f'{len(items)} haber çekildi')
"
```

### 12.2 Memos API Hatası

```bash
# Token ve URL kontrolü
cat .env

# API testi
curl -s "https://memos.googig.cloud/api/v1/memos" \
  -H "Authorization: Bearer $(grep MEMOS_TOKEN .env | cut -d= -f2 | tr -d '\"')" \
  -H "Content-Type: application/json"
```

**Sık hatalar:**
- **403 error code 1010:** Token süresi dolmuş → Memos'tan yeni token al
- **404 Not Found:** API URL yanlış → `.env`'deki URL'yi kontrol et (/api/v1/memos olmalı)
- **DNS çözümleme hatası:** İnternet bağlantısını kontrol et, tekrar dene

### 12.3 Halüsinasyon Yanlış Alarmı

Halüsinasyon kontrolü rubric skorlarını da tarıyorsa:

```bash
# Sadece haber metnini kontrol et
python3 -c "
from haber_kurator_core import HaberKuratorCore
from pathlib import Path
core = HaberKuratorCore(Path('.'))
result = core.hallucination_check('slug')
print(f'Bulgu: {result[\"total_findings\"]}')
for f in result.get('findings', []):
    print(f'  [{f[\"type\"]}] {f[\"message\"]}')
"
```

### 12.4 Doğrulama Seviyesi Beklenenden Düşük

Eğer aynı kaynaktan gelen birden fazla haber tek kaynak sayılıyorsa:
- 5 BBC haberi ≠ 5 farklı kaynak
- Sadece benzersiz kaynak isimleri sayılır
- 2 farklı Tier 0 kaynak gerekli (Reuters + AP gibi)

---

*Haber Küratörü — Tarafsız Haber ve Bilgi Akışı. v3.0.0*
