# Haber-Kuratör — Hermes Agent Plugin

## Proje Tanımı

**Haber-Kuratör**, Hermes Agent için geliştirilmiş bir **AI-Augmented Haber Üretimi System** plugin'idir.

- **Kaynak:** Memos Küratörü — Tarafsız Haber ve Bilgi Akışı
- **Lisans:** MIT
- **Versiyon:** v2.4.0
- **Tür:** General Plugin (standalone)

---

## Herme-Agent Entegrasyonu

### Plugin Mimarisi

Haber-Kuratör, Hermes'in **General Plugin** sistemi üzerine inşa edilmiştir:

```
~/.hermes/plugins/haber-kurator/
├── __init__.py              # register(ctx) - plugin kayıt
├── cli.py                   # CLI komutları (hermes haber ...)
├── haber_kurator_core.py       # Ana mantık (HaberKuratorCore sınıfı)
├── plugin.yaml              # Plugin manifesti
├── SKILL.md                 # Hermes Skill tanımı
├── strategy/                # İnsan tarafından düzenlenen (positioning, audience, pillars)
├── voice/                   # Üslup kuralları + slop kontrolü
├── stores/                  # Ham malzeme deposu (inbox, workboard, ideas, hooks, proof)
├── runs/                    # Her içerik objesi = bir run folder
├── modules/                 # Writer agent yapılandırması
├── workflows/              # Playbook'lar
└── references/             # Referans dokümanlar
```

### ctx API Kullanımı

Haber-Kuratör şu Hermes API'lerini kullanır:

| API | Kullanım |
|-----|----------|
| `ctx.register_tool()` | `haber_kurator_manager`, `haber_kurator_retriever` |
| `ctx.register_hook()` | `on_session_start`, `post_tool_call` |
| `ctx.register_command()` | `/haber` slash command |
| `ctx.register_cli_command()` | `hermes haber ...` CLI |
| `ctx.register_skill()` | SKILL.md bundle |

### Plugin Discovery

```
# User plugin (önerilen)
/usr/local/lib/hermes-agent/plugins/haber-kurator/

# Project plugin
.hermes/plugins/haber-kurator/  (HERMES_ENABLE_PROJECT_PLUGINS=true gerekli)
```

---

## Test Süreci

### Test Öncesi Hazırlık

Her test öncesi şu kod çalıştırılmalıdır:

```bash
hermes_home = /usr/local/lib/hermes-agent
cp haber-kurator $hermes_home/plugins/haber-kurator
.\stress_test.ps1
```

### Stress Test Script

`stress_test.ps1` — Tüm kombinasyonları test eder:

| Adım | Test |
|------|------|
| 1 | Environment Cleanup |
| 2 | Weird Characters (Türkçe şİğÜç) |
| 3 | State: captured |
| 4 | State: briefed |
| 5 | State: drafted (priority) |
| 6 | State Recovery |
| 7 | Slop Detection (High) |
| 8 | Zero Slop |
| 9 | Audit |
| 10 | Signal RSS |
| 12 | Scale Test (50 runs < 90s) |
| 17 | Directory Corruption |
| 18 | Zero-Byte Handling |
| 19 | Bulk Cleanup |

---

## Keşfedilen Test Senaryoları

### Tüm Geçen Testler

| # | Senaryo | Sonuç |
|---|---------|-------|
| 1 | Tools via Hermes (Manager + Retriever) | ✅ |
| 2 | Retrieve Strategy | ✅ |
| 3 | Very Long Idea (500+ chars) | ✅ |
| 4 | Duplicate Slug | ✅ (düzeltildi) |
| 5 | State Priority (brief+draft) | ✅ |
| 6 | Hook (post_tool_call) | ✅ |
| 7a | Tier 2 Slop Detection | ✅ |
| 7b | Mixed Tier (T1+T2) | ✅ |
| 7c | Clean Content → PASS | ✅ |
| 8a | Empty Idea Handling | ✅ |
| 8b | Spaces Only | ✅ |
| 9 | Invalid Slug Characters | ✅ (düzeltildi) |
| 10 | UTF-8 (Japanese/Chinese/Arabic/Emoji) | ✅ (düzeltildi) |

---

## Düzeltilen Bug'lar

### 1. UTF-8 Encoding Issue
**Sorun:** Japanese/Chinese/Arabic gibi UTF-8 karakterler `UnicodeEncodeError` veriyordu.

**Düzeltme:** `haber_kurator_core.py`'deki tüm `write_text()` ve `read_text()` çağrılarına `encoding="utf-8"` eklendi.

```python
# Önce (hatalı):
(run_path / "idea.md").write_text(idea)

# Sonra (düzeltilmiş):
(run_path / "idea.md").write_text(idea, encoding="utf-8")
```

### 2. Duplicate Slug Overwrite
**Sorun:** Aynı slug kullanıldığında mevcut run overwrite ediliyordu.

**Düzeltme:** `create_run()` artık mevcut run'u kontrol ediyor ve uyarı veriyor:

```python
if run_path.exists():
    return {"slug": slug, "path": str(run_path), "status": "exists", "message": "Run already exists"}
```

### 3. Invalid Karakterler Slug'da Crash
**Sorun:** `@#$%^&*()` gibi invalid karakterler slug'da OSError veriyordu.

**Düzeltme:** Slug sanitize eklendi:

```python
slug = re.sub(r'[^a-z0-9\-_]', '-', slug.lower())[:50]
slug = re.sub(r'-+', '-', slug).strip('-')
```

---

## Mevcut Durum

### Test Sonuçları
- ✅ **Toplam Test:** 20+ senaryo
- ✅ **Geçen:** 19
- ✅ **Düzeltilen Bug:** 3
- ⚠️ **Kalan Issue:** 0

### Performans
- **50 run oluşturma:** ~60s (hedef: <90s)
- **State sync:** Anlık
- **Slop tarama:** <100ms

---

## CLI Komutları

```bash
# Yeni run oluştur
hermes haber new "fikir" --slug optional-slug

# Status kontrolü
hermes haber status

# Slop tarama
hermes haber scan <slug>

# Audit
hermes haber audit

# Sinyal taraması
hermes haber signal [x|rss]

# Setup
hermes haber setup
```

---

## Sonraki Session'lar İçin Notlar

1. **Test öncesi:** Her zaman plugin dosyalarını Hermes home'a kopyala
2. **Yeni senaryo ekleme:** `stress_test.ps1`'e yeni testler ekle veya manuel test yap
3. **Bug bulma:** `haber_kurator_core.py`'deki mantığı kontrol et
4. **Düzeltme sonrası:** Mutlaka Hermes'e kopyala ve test et
5. **UTF-8:** Herhangi bir encoding issue'da `encoding="utf-8"` kontrol et

---

## Kaynaklar

- https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins
- https://hermes-agent.nousresearch.com/docs/developer-guide/memory-provider-plugin

---

## TAMAMLANDI - 9/9 Testler Başarılı

### Yeni Özellik Testleri:
- ✅ `hermes haber new` - Yeni run oluşturma
- ✅ `hermes haber runs` - Tüm run'ları listeleme (8 run)
- ✅ `hermes haber learnings` - Önceki run'lardan öğrenilenler
- ✅ `hermes haber patterns` - Run pattern analizi (8 run, 6.2 ortalama okunma)
- ✅ `hermes haber context [slug]` - Bağlam oluşturma
- ✅ `hermes haber voice-update` - Üslup profili görüntüleme

### Düzeltilen Bug'lar:
- PermissionError handling in `get_all_runs()` 
- PermissionError handling in `analyze_run_patterns()`
- PermissionError handling in `_analyze_single_run()`
- Locked folder'lar graceful olarak atlanıyor
