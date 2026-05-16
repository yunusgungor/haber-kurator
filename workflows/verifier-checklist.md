# Workflow: Verifier Checklist — News Edition (v3.1.0)

> **Adım adım haber doğrulama kontrol listesi.**
> Artık sadece slop ve rubrik değil — KAYNAK DOĞRULAMA da eklenmiştir.
> Verifier Agent veya insan reviewer için.

---

## Ön Hazırlık

**Çalıştırmadan önce:**
- [ ] `brief.md` mevcut ve dolu (kaynak listesi dahil)
- [ ] `draft-package.md` mevcut
- [ ] `voice-profile.md` mevcut
- [ ] `master-avoid-slop.md` mevcut
- [ ] `fact-check-report.md` mevcut (news run'ı için)
- [ ] `references/rubric-template.md` mevcut

**Okuma sırası:**
1. Önce `fact-check-report.md` — hangi kaynaklar ne doğruladı?
2. Sonra `brief.md` — ne üretilmesi gerekiyordu? Hangi kaynaklar listelenmiş?
3. Sonra `draft-package.md` — ne üretildi? Kaynaklar doğru atfedilmiş mi?
4. Sonra `master-avoid-slop.md` ve rubric

---

## 🔴 KONTROL 0: Kaynak Atıf Denetimi (CRITICAL — YENİ)

**Bu kontrol diğerlerinden ÖNCE gelir. Bir haberin kaynağı yanlışsa, gerisi anlamsızdır.**

### 0a: Her iddia bir kaynağa bağlı mı?
| Kontrol | Nasıl Yapılır |
|---------|---------------|
| Her istatistik/rakam için kaynak var mı? | `grep -c -E "(Reuters|AP|AFP|Bloomberg|BBC|WSJ|FT|The Guardian|NYT)" draft-package.md` |
| Kaynaksız iddia var mı? | "uzmanlara göre", "kaynaklara göre", "açıklamada" gibi belirsiz ifadeleri tara |
| Alıntı yapılan kişi/kurum belirtilmiş mi? | `"..." said X` pattern'ini kontrol et |

### 0b: Kaynaklar güvenilir mi?
| Kontrol | Nasıl Yapılır |
|---------|---------------|
| Kaynaklar source-watchlist.md'de var mı? | Kullanılan her kaynağı approved listte kontrol et |
| Tier 0-1 kaynak mı? | Değilse LOW_CONFIDENCE flag'ı |
| Kaynak linki çalışıyor mu? | (manuel kontrol) |

### 0c: Halüsinasyon var mı? (YENİ)
| Kontrol | Nasıl Yapılır |
|---------|---------------|
| brief'te olmayan iddia var mı? | Her iddiayı brief'teki source listesiyle karşılaştır |
| Uydurma alıntı var mı? | Alıntı yapılan kişinin brief'te geçtiğini doğrula |
| Uydurma sayı var mı? | brief'te geçmeyen her rakamı işaretle |

### 0d: Kaynak Zinciri Formatı
```
source_attribution_audit:
- Claims with proper source: [N]
- Claims without source: [N]
- Potentially hallucinated: [list]
- Sources approved: [yes/no]
```

---

## 🟡 KONTROL 1: Brief Uyumu

| Kontrol | Soru | Geçti? |
|---------|------|--------|
| Thesis | Haberin özü brief'teki thesis ile uyumlu mu? | [ ] |
| Source List | Draft'ta kullanılan kaynaklar brief'teki listeden mi? | [ ] |
| Format | [Özet] - [Detaylar] - [Kaynak] yapısı kullanılmış mı? | [ ] |
| Tone | Tarafsız ve objektif ton korunmuş mu? | [ ] |
| Length | Uzunluk sınırlarına uyulmuş mu? | [ ] |

---

## 🟢 KONTROL 2: Rubric Puanlaması (0-12)

| # | Kriter | Puan (0-2) | Kanıt |
|---|--------|-----------|-------|
| 1 | **Tarafsızlık (Objectivity)** — Kişisel yorum yok, sadece gerçekler | /2 | |
| 2 | **Kaynak Gösterimi (Sourcing)** — Her iddia kaynak atıflı | /2 | |
| 3 | **Kısalık ve Netlik (Brevity)** — Haber formatına uygun | /2 | |
| 4 | **Bilgi Yoğunluğu (Fact Density)** — Rakam, tarih, isim var | /2 | |
| 5 | **Clickbait Uzaklığı** — Abartı yok, spekülasyon yok | /2 | |
| 6 | **Format Yapısı** — [Özet]-[Detaylar]-[Kaynak] | /2 | |
| | **TOPLAM** | **/12** | |
| | **Eşik: 8/12** | **Geçti?** | |

---

## 🔵 KONTROL 3: Slop Taraması

### Tier 1 — Sıfır Tolerans (Haber Odaklı)
| # | Kalıp | İhlal? |
|---|-------|--------|
| 1 | Promosyon/Clickbait: "groundbreaking", "game-changing" | [ ] |
| 2 | Önem abartısı: "pivotal", "testament" | [ ] |
| 3 | Belirsiz atıf: "experts believe", "studies show", "uzmanlara göre" | [ ] |
| 4 | Kaynaksız iddia: "allegedly", "unnamed sources say" | [ ] |
| 5 | Sahte aciliyet: "breaking:", "developing story" | [ ] |
| 6 | Dolgu zarfları: "actually", "literally", "simply", "just" | [ ] |
| 7 | Staccato parçalama: kısa cümle dizileri | [ ] |

### Tier 2 — Yüksek (3+ = REVISE, 5+ = REJECT)
| # | Kalıp | İhlal? |
|---|-------|--------|
| 8 | Copula Avoidance: "serves as", "stands as" | [ ] |
| 9 | -ing Padding: "leveraging", "implementing" | [ ] |
| 10 | Rule of Three Zorlama | [ ] |
| 11 | Filler Phrases: "due to the fact that" | [ ] |
| 12 | Generic Conclusions: "the future looks bright" | [ ] |
| 13 | Signposting: "let's dive in", "here's what you need" | [ ] |
| 14 | Hyperbolic Quantifiers: "every single", "never ever" | [ ] |
| 15 | Hedging: "it could potentially", "arguably" | [ ] |

### Tier 3 — Orta (8+ = REVISE, 15+ = REJECT)
| # | Kalıp | İhlal? |
|---|-------|--------|
| 16 | Passive Voice (aşırı) | [ ] |
| 17 | Temporal Vagueness: "recently", "lately" | [ ] |
| 18 | False Balance: "some say... while others say" | [ ] |
| 19 | Speculation: "could potentially mean", "raises questions" | [ ] |
| 20+ | Diğer Tier 3 kalıpları için master-avoid-slop.md'ye bak | [ ] |

---

## ⚠️ KONTROL 4: Ses Kontrolü

```
voice_check:
- Rule 1 (Tarafsız): [uyuldu/ihlal]
- Rule 2 (Kaynak atfı): [uyuldu/ihlal]
- Rule 3 (Özet-Detay-Kaynak): [uyuldu/ihlal]
- Rule 4 (Veri kullanımı): [uyuldu/ihlal]
- Rule 5 (Şeffaflık): [uyuldu/ihlal]
- Yasaklı kalıp: [evet/hayır]
```

---

## VERDICT

```
┌─────────────────────────────────────────────────────┐
│  VERDICT — News Edition v3.1.0                      │
├─────────────────────────────────────────────────────┤
│                                                     │
│  SOURCE AUDIT:  [PASS / FAIL]                       │
│  Rubric Skor:   ___/12  (Eşik: 8/12)               │
│  Slop İhlalleri: [count]                           │
│  Halüsinasyon:  [NONE / DETECTED]                  │
│  Ses Uyumu:     [tam / kısmi / bozuk]              │
│                                                     │
│  [ ] APPROVE                                        │
│      → source audit PASS, skor ≥8, no hallucination │
│                                                     │
│  [ ] REVISE                                         │
│      → source audit minor issues, skor ≥6          │
│                                                     │
│  [ ] REJECT                                         │
│      → source audit FAIL veya halüsinasyon var      │
│        veya skor <6                                 │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Kesin Ret Nedenleri:**
- Halüsinasyon tespiti (brief'te olmayan iddia)
- Kaynaksız iddia ≥ 3 adet
- Kaynak güvenilir değil (whitelist'te yok)
- Skor < 6/12

---

## Final Rapor Formatı

```markdown
# Verifier Report — {SLUG} (News Edition)
Tarih: {YYYY-MM-DD}
Verifier: {agent veya insan}

## source_attribution_audit
- Claims with proper source: N
- Claims without source: N
- Hallucinated claims: [NONE / list]
- Source approval: [PASS / FAIL]

## brief_check
- Thesis delivered: [yes/partial/no]
- Source list followed: [yes/partial/no]
- Format correct: [yes/partial/no]

## rubric_scoring [X/12]
- Tarafsızlık: [0/1/2]
- Kaynak Gösterimi: [0/1/2]
- Kısalık ve Netlik: [0/1/2]
- Bilgi Yoğunluğu: [0/1/2]
- Clickbait Uzaklığı: [0/1/2]
- Format Yapısı: [0/1/2]

## avoid_slop_findings
- [Tier 1 findings]
- [Tier 2 findings]

## VERDICT: [APPROVE | REVISE | REJECT]

## required_fixes
1. [fix]
```
