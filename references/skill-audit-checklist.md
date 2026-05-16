# Skill Audit Checklist — Haber Kuratör

> Bu dosya, Haber Kuratör plugin'inin veya başka bir skill'in eksiksiz doğrulanması için kullanılır.
> Kullanıcı "eksiksiz kontrol et" veya "derinlemesine kontrol et" dediğinde bu kontrol listesi uygulanır.

---

## 🔍 Audit Metodolojisi

**Yaklaşım:** Systematic verification — yüzeysel check DEĞİL, tüm dosyaları oku, tüm anahtarları karşılaştır, sonuçları tablo ile sun.

**1. Dosya listesi çıkar** (Python ile):
```python
import os
base = "/home/hermeswebui/.hermes/skills/productivity/haber-kurator"
files = {}
for root, dirs, filenames in os.walk(base):
    for fn in filenames:
        path = os.path.join(root, fn)
        with open(path) as f:
            files[path.replace(base + '/', '')] = f.read()
```

**2. 5 katmanlı kontrol uygula:**

---

## Katman 1: Dosya Yolu Referans Kontrolü

Her dosyadaki `` `dosya.md` `` referanslarını bul → dosya gerçekten var mı?

```python
import re
for name, content in files.items():
    refs = re.findall(r'`([^`]+\.(?:md|sh))`', content)
    for r in sorted(set(refs)):
        if not r.startswith('..'):
            exists = os.path.exists(os.path.join(base, r))
            if not exists:
                print(f"❌ MISSING: {r} (referenced in {name})")
```

**Haber Kuratör specific dosyalar:**
- `references/avoid-slop-patterns.md` ✅
- `references/production-prompts.md` ✅
- `references/rubric-template.md` ✅
- `scripts/setup-haber-kurator.sh` ✅
- `workflows/*.md` (4 dosya) ✅

**Eksik dosya referansı örnekleri (bulunan hatalar):**
| Referenced | Status | Not |
|---|---|---|
| `brief.md` | ⚠️ Bare filename | Run folder içinde `{slug}/brief.md` olarak kullanılmalı — dokümante değil hata |
| `stores/inbox.md` | ✅ Full path | Production-prompts.md'den doğru referans |
| `voice/voice-profile.md` | ✅ Relative | Skill klasörüne göre değil, `$HABER_KURATOR_PATH`'e göre |
| `master-avoid-slop.md` | ⚠️ Bare filename | `voice/master-avoid-slop.md` olarak çözümlenmeli |

---

## Katman 2: İçerik Tutarlılık Kontrolü

| Kontrol | Beklenen | Dosyalar |
|---------|---------|---------|
| **9 haber değeri taşıyan format** | Format tablosunda 9 satır | SKILL.md |
| **4 production prompt** | Prompt envanter tablosunda 4 satır | SKILL.md |
| **13 workflow aşama** | AŞAMA 1-13 hepsi mevcut | workflows/idea-to-published-post.md |
| **4 rota** | ORIGINAL, REPURPOSE, REWRITE, RESEARCH+IDEATE | workflows/, SKILL.md, setup script |
| **2-model setup** | Writer Model + Orchestrator Model | SKILL.md |
| **8/12 rubric threshold** | 8/12 eşik değeri geçiyor | rubric-template.md, SKILL.md, workflows |
| **Feedback 24s + 72s** | Her iki süre de dokümante | workflows/feedback-loop.md |

**Kontrol kodu:**
```python
# 13 aşama
stages = re.findall(r'AŞAMA\s+(\d+)', wp)
aşama_set = set(int(x) for x in stages)
complete_13 = aşama_set == set(range(1, 14))  # True olmalı

# 9 format
fmt_rows = [r for r in skill.split('\n') 
            if '|' in r and re.search(r'\|\s*\d+\s*\|', r)]
fmt_count = len(fmt_rows)  # 9 olmalı

# 4 rota
routes_ok = all(r in wp for r in 
    ['ORIGINAL', 'REPURPOSE', 'RESEARCH+IDEATE', 'REWRITE'])
```

---

## Katman 3: Tier/Seviye Tamamlık Kontrolü

Avoid-Slop sistemi: **3 seviye** kontrol edilmeli.

| Dosya | Tier 1 (8 kalıp) | Tier 2 (8 kalıp) | Tier 3 (18+ kalıp) |
|-------|:---:|:---:|:---:|
| SKILL.md (özet) | ✅ Mention var | ✅ Mention var | ❌ Eksikti — **eklendi** |
| references/avoid-slop-patterns.md | ✅ Tablo var | ✅ Tablo var | ✅ Tablo var |
| workflows/verifier-checklist.md | ✅ Tablo var | ✅ Tablo var | ❌ Eksikti — **eklendi** |
| workflows/idea-to-published-post.md | ✅ Var | ✅ Var | ❌ Eksikti — **eklendi** |
| scripts/setup-haber-kurator.sh | ✅ Var | ✅ Var | ✅ Var |

**Eşik değerleri tutarlılığı:**
| Tier | Eşik | Doğrulama |
|------|------|-----------|
| Tier 1 | ≥3 ihlal = REJECT | `references/avoid-slop-patterns.md`'de kontrol et |
| Tier 2 | ≥5 toplam ihlal = REJECT, 3+ = REVISE | Aynı dosyada kontrol et |
| Tier 3 | Bağlamsal, çok fazla = REVISE | `Passive Voice`, `Elegant Variation` vb. kalıp isimleri mevcut |

---

## Katman 4: Hermes Komut Envanteri Kontrolü

**Tüm /haber komutları dokümante mi?** (SKILL.md'de arama yap)

```python
lines = skill.split('\n')
cmd_lines = [l for l in lines if '/haber ' in l and l.strip().startswith('/')]
unique_cmds = set()
for line in cmd_lines:
    m = re.match(r'(/haber\s+\w+)', line.strip())
    if m:
        unique_cmds.add(m.group(1))
# Beklenen: 19 komut
```

**Haber Kuratör /haber komutları:**
| Komut | Durum | Not |
|-------|-------|-----|
| `/haber new` | ✅ | |
| `/haber brief` | ✅ | |
| `/haber draft` | ✅ | |
| `/haber verify` | ✅ | |
| `/haber post` | ✅ | |
| `/haber postmortem` | ⚠️ Eksikti | **Eklendi** |
| `/haber feedback` | ✅ | |
| `/haber score` | ✅ | |
| `/haber audit` | ✅ | |
| `/haber setup` | ✅ | |
| `/haber scaffold` | ✅ | |
| `/haber seeds` | ✅ | |
| `/haber extract-brand` | ✅ | |
| `/haber signal` | ✅ | |
| `/haber ideas` | ✅ | |
| `/haber hooks` | ✅ | |
| `/haber proof` | ✅ | |
| `/haber backlog` | ✅ | |
| `/haber archive` | ✅ | |
| `/haber metrics` | ✅ | |

---

## Katman 5: Setup Script Dizin Kontrolü

```python
required_dirs = [
    'strategy',           # SKILL.md'de referans var ama oluşturulmuyor
    'voice',              # Aynı
    'stores/ideas',       # ✅
    'stores/hooks',       # ✅
    'stores/proof',       # ✅
    'stores/feedback',    # ✅
    'runs/active',        # ✅
    'runs/archive',       # ✅
    'modules/writer/references/example-briefs',
    'modules/writer/references/best-posts',
    'modules/writer/templates',
    'workflows'
]
for d in required_dirs:
    in_script = d in script_content
    print(f"{'✅' if in_script else '❌'} {d}")
```

**Bulunan hata:** Setup script'in `create_scaffold()` fonksiyonu 12 dizin oluşturuyordu. `strategy/` ve `voice/` dizinleri dokümante edilmişti ama `dirs=()` array'inde yoktu — **düzeltildi**.

---

## ⚠️ Bilinen Sorunlar (Düzeltildi)

| # | Sorun | Tarih | Durum |
|---|-------|-------|-------|
| 1 | SKILL.md'de Tier 3 özeti yoktu | 2026-05-11 | ✅ Düzeltildi |
| 2 | `/haber postmortem` dokümante değildi | 2026-05-11 | ✅ Düzeltildi |
| 3 | Kullanıcı Tercihleri section eksikti | 2026-05-05 | ✅ Eklendi |
| 4 | verifier-checklist.md'de Tier 3 kalıpları (17-34) yoktu | 2026-05-11 | ✅ Eklendi |
| 5 | idea-to-published-post.md'de Tier 2/3 eşik değerleri net değildi | 2026-05-11 | ✅ Düzeltildi |
| 6 | production-prompts.md'de dosya yolu referansları belirsizdi | 2026-05-11 | ✅ Düzeltildi |

---

## ✅ Audit Çalıştırma Şablonu

```
1. execute_code ile tüm dosyaları oku
2. 5 katmanlı kontrolü çalıştır
3. Sonuçları tablo ile sun (✅ PASS / ❌ FAIL)
4. Tespit edilen hataları patch ile düzelt
5. Düzeltmelerden sonra tüm kontrolleri tekrar çalıştır
6. 0 FAIL olana kadar tekrarla
```
