# Haber Kuratör v3.1.0 — News Verification Engine

> **Çok kaynaklı haber doğrulama sistemi.** Dünyanın önde gelen 40+ güvenilir kaynağından haber çeker, çapraz doğrular ve Memos platformunda yayınlar.
>
> Hermes Agent plugin'i olarak çalışır. Kaynak: Memos Küratörü.

---

## 🎯 Ne İşe Yarar?

- **📡 Haber Toplama** — 40+ kaynaktan RSS beslemesi çeker (Reuters, AP, AFP, BBC, Bloomberg, AA, T24, Webrazzi...)
- **🔍 Çapraz Doğrulama** — Aynı haberi 2+ bağımsız kaynakta karşılaştırır, doğruluk seviyesi belirler
- **🤖 Writer Agent** — Doğrulanmış haberleri Türkçe `[Özet]-[Detaylar]-[Kaynak]` formatında otomatik üretir
- **📤 Otomatik Yayın** — Memos API'sine bağlanır, haberleri otomatik yayınlar
- **🛡️ Halüsinasyon Koruması** — Kaynaksız iddiaları, uydurma alıntıları, spekülasyonu tespit eder
- **✏️ Düzeltme & Geri Çekme** — Yayın sonrası hata durumunda correction veya retraction
- **🔬 120+ Slop Pattern** — 4 kademede AI kokusu tespiti (Tier 1-3 + Bonus)
- **🧩 Çapraz Dil** — Türkçe/İngilizce haberleri otomatik eşleştirir

---

## 🚀 Hızlı Başlangıç

```bash
# 1. Haberleri çek ve doğrula
hermes haber fetch                    # 40+ kaynaktan haber topla
hermes haber verify                   # Kümele + çapraz doğrula

# 2. Writer Agent ile otomatik yayınla
hermes haber auto-publish --limit 3   # En iyi 3 haberi Memos'a bas

# 3. veya manuel pipeline
hermes haber publish                  # Doğrulanan haberleri sisteme al

# 4. Sistem durumu
hermes haber sources                  # Kaynak listesini gör
hermes haber audit                    # Sistem sağlık kontrolü
hermes haber runs                     # Tüm run'ları listele
```

---

## 📡 Kaynak Güvenilirlik Kademeleri

| Kademe | Ağırlık | Tanım | Örnekler |
|--------|---------|-------|----------|
| **PRIMARY** (Tier 0) | 3 | Wire servisler — en yüksek | Reuters, AP, AFP, BBC |
| **MAJOR** (Tier 1) | 2 | Büyük yayıncılar | Bloomberg, WSJ, FT, NYT, Guardian, WaPo, NPR, Al Jazeera, Economist, CNBC, AA, BBC Türkçe, Euronews TR, DW, Bloomberg HT |
| **SPECIALIZED** (Tier 2) | 1 | Uzman / niş yayıncılar | Nature, MIT Tech Review, The Verge, Wired, HBR, ScienceDaily, T24, Medyascope, Duvar, Diken, BirGün, Sözcü, Cumhuriyet, Hürriyet, Webrazzi |

**Kural:** Tek kaynaktan haber → **LOW_CONFIDENCE**, insan onayı olmadan yayınlanamaz.

---

## 🔄 Çalışma Prensibi

```
📡 RSS ÇEKME                     📝 HABER ÜRETİMİ
─────────────────────           ─────────────────────
Reuters     ─┐                  Writer Agent
AP          ─┤  ┌───────────┐   ┌──────────────┐
AFP         ─┤  │fetch_all  │   │  generate_   │  ┌────────┐
BBC         ─┤  │_news()    │──▶│  news()      │──▶│ MEMOS  │
Bloomberg   ─┤  └───────────┘   │  (Türkçe)    │  │ YAYIN  │
AA          ─┤                  └──────────────┘  └────────┘
T24         ─┤                     ▲
...         ─┘  ┌───────────┐      │
                │  cross_   │──────┘
                │ verify_   │  ✅ CONFIRMED / 🟡 HIGH CONFIDENCE
                │ story()   │  🟠 MEDIUM CONFIDENCE / 🔴 LOW CONFIDENCE
                └───────────┘
```

---

## 📋 Komutlar

### CLI (`hermes haber ...`)

| Komut | Açıklama |
|-------|----------|
| `sources` | 📡 Kaynakları kademelere göre listeler |
| `fetch [--category] [--limit]` | 📡 Haber çeker + kümeler + tablo |
| `verify [--category] [--limit]` | 🔍 Çeker + kümeler + çapraz doğrular |
| `publish [--category] [--limit] [--auto]` | 📰 Doğrulanmış haberleri run'a ekler |
| `correct <slug> <hata> [--retract] [--info]` | ✏️ Düzeltme/retraction yayınla |
| `hallucination <slug>` | 🔬 Halüsinasyon taraması |
| `auto-publish [--limit] [--category]` | 🤖 Writer Agent: tam otomatik haber üret + Memos'a yayınla |
| `setup` | 🚀 Dizin yapısını oluştur |
| `status` | 📋 Aktif run'ların state'leri |
| `audit` | 🔍 Tam sistem denetimi |
| `runs [--no-archive]` | 📂 Tüm run'ları listele |
| `search <query>` | 🔎 Run'lar içinde ara |
| `archive <slug> [--force]` | 📦 Run'ı arşivle |

### Slash (`/haber ...`)

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

---

## 🔬 Doğrulama Seviyeleri

| Seviye | Değer | Anlamı | Otomatik Yayın? |
|--------|-------|--------|----------------|
| ✅ **CONFIRMED** | 3 | 2+ farklı Tier 0 kaynak | ✅ Evet |
| 🟡 **HIGH CONFIDENCE** | 2 | 1 Tier 0 + 1 Tier 1 | ✅ Evet |
| 🟠 **MEDIUM CONFIDENCE** | 1 | 2+ Tier 1 kaynak | ⚠️ İnsan önerilir |
| 🔴 **LOW CONFIDENCE** | 0 | Tek kaynak / Tier 2+ | ❌ İnsan onayı gerekli |
| ⛔ **UNVERIFIED** | -1 | Doğrulanamaz | ❌ Bloke |

---

## 🔄 8-State News Lifecycle

```
captured → fact_checking → cross_verified → published
                                               │
                          ┌────────────────────┘
                          ▼
              correction_needed → corrected → archived
                               ↘ retracted ↗
```

Her state geçişi `STATE_TRANSITIONS` sözlüğünde tanımlıdır ve `update_state()` ile doğrulanır.

---

## 🛡️ Kalite Kontrolleri

- **120+ slop pattern** (Tier 1: 45, Tier 2: 32, Tier 3: 31, Bonus: 14) — AI kokusu tespiti
- **Halüsinasyon taraması** — Kaynaksız istatistik, uydurma alıntı, spekülasyon tespiti (URL'lerdeki sayılar false positive olarak algılanmaz)
- **Türkçe/İngilizce çapraz dil kümeleme** — 50+ eşleştirme kuralı
- **8-state lifecycle** — Her haberin durumu JSON cache'te takip edilir
- **State cache persistence** — Plugin reload sonrası state kaybı yaşanmaz

---

## 🔧 Yapılandırma

```bash
# Memos API Token (.env dosyasına yaz)
MEMOS_TOKEN="memos_pat_xxx..."
MEMOS_API_URL="https://memos.googig.cloud/api/v1/memos"
```

### Cron Job ile Otomatik Yayın

```bash
hermes cron create --schedule "0 */2 * * *" \
  --name "haber-otomatik" \
  --prompt "Run the haber-kurator Writer Agent to auto-publish news to Memos"
```

---

## 📁 Proje Yapısı

```
haber-kurator/
├── __init__.py               🔌 Plugin kayıt (tools, hooks, CLI, slash)
├── haber_kurator_core.py     ⭐ Ana motor (40+ kaynak, doğrulama, 8-state)
├── writer_agent.py           🤖 Writer Agent (otomatik haber üretimi + yayın)
├── memos_cli.py              📤 Memos API istemcisi
├── cli.py                    📋 CLI komut ağacı
├── SKILL.md                  🧠 Hermes Agent skill tanımı
├── plugin.yaml               📄 Plugin manifest
├── strategy/                 📡 Kaynak ve strateji dosyaları
├── voice/                    🎯 Üslup kuralları ve slop pattern'leri
├── runs/active/              📂 Aktif haber run'ları
├── runs/archive/             📦 Arşivlenmiş run'lar
├── stores/                   📥 Fikir, kanıt, hook depoları
├── workflows/                📖 Playbook'lar
├── references/               📚 Referans dokümanlar
├── tests/                    🧪 Pytest birim testleri
└── .state_cache/             💾 JSON state cache
```

---

## Gereksinimler

- Hermes Agent
- Python 3.11+
- İnternet bağlantısı (RSS çekimi için)
- Memos hesabı + API token (yayın için)

---

## Lisans

MIT — özgürce kullan, değiştir, dağıt.

---

*Haber Küratörü v3.1.0 — Tarafsız Haber ve Bilgi Akışı. [Memos Küratörü](https://x.com/memos) metodolojisinden uyarlanmıştır.*
