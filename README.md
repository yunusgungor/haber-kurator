# Haber Kuratör v3.0.0 — News Verification Engine

> **Çok kaynaklı haber doğrulama sistemi.** Dünyanın önde gelen 35 güvenilir kaynağından haber çeker, çapraz doğrular ve Memos platformunda yayınlar.
>
> Hermes Agent plugin'i olarak çalışır. Kaynak: Memos Küratörü.

---

## 🎯 Ne İşe Yarar?

| Yapabilir | Açıklama |
|-----------|----------|
| **📡 Haber Toplama** | 35 kaynaktan RSS beslemesi çeker (Reuters, AP, AFP, BBC, Bloomberg, AA, T24, Webrazzi...) |
| **🔍 Çapraz Doğrulama** | Aynı haberi 2+ kaynakta karşılaştırır, doğruluk seviyesi belirler |
| **🤖 Writer Agent** | Doğrulanmış haberleri Türkçe [Özet]-[Detaylar]-[Kaynak] formatında yazar |
| **📤 Otomatik Yayın** | Memos API'sine bağlanır, haberleri otomatik yayınlar |
| **🛡️ Halüsinasyon Koruması** | Kaynaksız iddiaları, uydurma alıntıları, spekülasyonu tespit eder |
| **✏️ Düzeltme Workflow'u** | Yayın sonrası hata durumunda düzeltme veya geri çekme |

---

## 🚀 Hızlı Başlangıç

```bash
# 1. Haberleri çek ve doğrula
hermes haber fetch                    # 35 kaynaktan haber topla
hermes haber verify                   # Kümele + çapraz doğrula

# 2. Writer Agent ile otomatik yayınla
hermes haber auto-publish --limit 3   # En iyi 3 haberi Memos'a bas

# 3. veya manuel pipeline
hermes haber publish                  # Doğrulanan haberleri sisteme al
hermes haber post <slug>              # Memos'ta yayınla

# 4. Sistem durumu
hermes haber sources                  # Kaynak listesini gör
hermes haber audit                    # Sistem sağlık kontrolü
hermes haber runs                     # Tüm run'ları listele
```

---

## 📡 Kaynak Güvenilirlik Kademeleri

| Kademe | Açıklama | Örnekler | Doğrulama |
|--------|----------|---------|-----------|
| **Tier 0 (PRIMARY)** | Wire servisler — en yüksek | Reuters, AP, AFP, BBC | 2+ farklı kaynak → ✅ **CONFIRMED** |
| **Tier 1 (MAJOR)** | Büyük yayıncılar | Bloomberg, WSJ, FT, NYT, Guardian | 1 T0 + 1 T1 → 🟡 **HIGH CONFIDENCE** |
| **Tier 2 (SPECIALIZED)** | Uzman yayıncılar | Nature, MIT Tech Review, Wired | 2+ T1 → 🟠 **MEDIUM CONFIDENCE** |
| **Tier 3 (TÜRKÇE)** | Türkiye kaynakları | AA, BBC Türkçe, Euronews TR, T24, Diken, Sözcü... | 🔴 **LOW CONFIDENCE** (insan onayı gerek) |

**Kural:** Tek kaynaktan haber LOW_CONFIDENCE olarak işaretlenir, insan onayı olmadan yayınlanamaz.

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
T24         ─┤  ┌───────────┐                     ▲
Sözcü       ─┤  │  cross_   │                     │
...         ─┘  │ verify_   │─────────────────────┘
                 │ story()   │  ✅ CONFIRMED
                 └───────────┘  🟡 HIGH CONFIDENCE
```

---

## 📋 Komutlar

### CLI (`hermes haber ...`)

| Komut | Açıklama |
|-------|----------|
| `fetch [--category]` | 📡 Tüm 35 kaynaktan haber çek |
| `verify [--category] [--limit]` | 🔍 Kümele + çapraz doğrula |
| `publish [--category] [--limit] [--auto]` | 📰 Doğrulanan haberleri sisteme al |
| `auto-publish [--limit] [--category]` | 🤖 Writer Agent: otomatik haber üret + Memos'a yayınla |
| `post <slug>` | 📤 Mevcut draft'ı Memos'ta yayınla |
| `correct <slug> <hata> --info <doğru>` | ✏️ Düzeltme yayınla |
| `correct <slug> --retract` | 🚫 Haberi tamamen geri çek |
| `hallucination <slug>` | 🔬 Halüsinasyon kontrolü |
| `scan <slug>` | 🔎 Slop tara |
| `score <slug>` | 📊 Rubric puanla (0-12) |
| `sources` | 🌍 Kaynak listesini göster |
| `status` | 📋 Run durumlarını göster |
| `audit` | 🔍 Sistem sağlık kontrolü |
| `runs [--no-archive]` | 📂 Tüm run'ları listele |
| `search <query>` | 🔎 Run'lar içinde ara |
| `new <idea> [--source]` | 🆕 Yeni run oluştur |
| `route <idea> [--source]` | 🗺️ Rota belirle |
| `state [slug] [--set]` | 🔁 State gör/güncelle |
| `brief <slug> [--llm]` | 📝 Brief hazırla (--llm ile otomatik) |
| `draft <slug> [--llm]` | ✍️ Draft hazırla (--llm ile otomatik) |
| `verify-draft <slug>` | 🔍 Draft'ı doğrula (slop + halüsinasyon) |
| `signal [x|rss]` | 📶 Sinyal tara |
| `postmortem <slug>` | 📊 Yayın analizi |
| `learnings [--topic]` | 📝 Öğrenimler |
| `patterns` | 📊 Pattern analizi |
| `archive <slug> [--force]` | 📦 Run'ı arşivle (--force ile state atla) |
| `context <slug>` | 📄 Run bağlamını göster |
| `voice-update` | 🗣️ Üslup profilini göster |
| `setup` | 🚀 Dizin yapısını oluştur |

### Slash (`/haber ...`)

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
| `archive <slug> [--force]` | 📦 Arşivle (--force ile state atla) |
| `learnings` | 📝 Öğrenimler |
| `patterns` | 📊 Pattern analizi |
| `voice-update` | 🗣️ Ses profilini görüntüle |

### Doğal Dil Desteği

Hermes içinde `/haber` komutuna **Türkçe cümle** yazabilirsiniz. Sistem otomatik anlar:

| Dediğiniz | Ne Yapar |
|-----------|----------|
| `/haber teknoloji haberlerini getir` | `fetch --category technology` |
| `/haber ekonomi haberlerini doğrula` | `verify --category business` |
| `/haber son dakika haberlerini yayınla` | `publish --category news` |
| `/haber bilim haberlerini otomatik yayınla` | `auto-publish --category science` |
| `/haber kaynakları listele` | `sources` |
| `/haber haber doğrula` | `verify` |

Kategori: teknoloji, ekonomi/finans, bilim/araştırma, gündem, son dakika, haber
Fiil: getir/ara (fetch), doğrula/kontrol et (verify), yayınla/paylaş (publish)

---

## 📁 Proje Yapısı

```
haber-kurator/
├── haber_kurator_core.py    ⭐ Ana motor (35 kaynak, doğrulama, 19 state)
├── writer_agent.py          🤖 Writer Agent (otomatik haber üretimi + yayın)
├── memos_cli.py             📤 Memos API istemcisi
├── __init__.py              🔌 Plugin kayıt (tools, hooks, CLI, slash)
├── cli.py                   📋 CLI komut ağacı
├── strategy/
│   ├── source-watchlist.md  📡 35 güvenilir kaynak (Tier 0-3)
│   ├── positioning.md       🎯 Konumlandırma (sen doldur)
│   ├── audience.md          👥 Hedef kitle (sen doldur)
│   └── pillars.md           📚 İçerik konuları (sen doldur)
├── voice/
│   ├── voice-profile.md     🗣️ Üslup kuralları
│   └── master-avoid-slop.md 🚫 111 slop pattern
├── runs/active/             📂 Aktif haber run'ları
├── runs/archive/            📦 Arşivlenmiş run'lar
├── stores/                  📥 Fikir, kanıt, hook depoları
├── workflows/               📖 Playbook'lar
└── .env                     🔑 Memos API token
```

---

## 🔧 Yapılandırma

### Memos API Token

```bash
# .env dosyasına yaz
MEMOS_TOKEN="memos_pat_xxx..."
MEMOS_API_URL="https://memos.googig.cloud/api/v1/memos"
```

### Otomatik Yayın Cronjob

```bash
# Her 2 saatte bir Writer Agent çalıştır
hermes cron create --schedule "0 */2 * * *" \
  --name "haber-otomatik" \
  --prompt "Run the haber-kurator Writer Agent to auto-publish news to Memos"
```

---

## 📊 Doğrulama Seviyeleri

| Seviye | Değer | Anlamı | Otomatik Yayın? |
|--------|-------|--------|----------------|
| ✅ **CONFIRMED** | 3 | 2+ farklı Tier 0 kaynak | ✅ Evet |
| 🟡 **HIGH CONFIDENCE** | 2 | 1 Tier 0 + 1 Tier 1 | ✅ Evet |
| 🟠 **MEDIUM CONFIDENCE** | 1 | 2+ Tier 1 | ⚠️ İnsan önerilir |
| 🔴 **LOW CONFIDENCE** | 0 | Tek kaynak | ❌ Hayır |
| ⛔ **UNVERIFIED** | -1 | Doğrulanamaz | ❌ Bloke |

---

## 🛡️ Kalite Kontrolleri

- **111 slop pattern** (T1:45, T2:33, T3:19, Bonus:14) — AI kokusu tespiti
- **Halüsinasyon taraması** — Kaynaksız istatistik, uydurma alıntı, spekülasyon (URL'lerdeki sayılar false positive olarak algılanmaz)
- **Türkçe/İngilizce çapraz dil** — 50+ eşleştirme kuralı ile kümeleme
- **19 state'li lifecycle** — Her haberin durumu takip edilir
- **Düzeltme workflow'u** — Hatalı haber için correction/retraction

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

*Haber Küratörü — Tarafsız Haber ve Bilgi Akışı. [Memos Küratörü](https://x.com/memos) metodolojisinden uyarlanmıştır.*
