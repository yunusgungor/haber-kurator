# Workflow: Idea → Published Post (News Edition — v3.1.0)

> **Haber üretimi için 15 aşamalı ana playbook.** 
> Artık kişisel içerik sistemi DEĞİL, çok kaynaklı haber doğrulama sistemidir.
> Her haber en az 2 bağımsız güvenilir kaynakta doğrulanmadan yayınlanmaz.

---

## Genel Bakış — Yeni Süreç

```
KAYNAK KATMANI (Source Layer)
  │  Reuters, AP, AFP, BBC, Bloomberg, WSJ, FT...
  │  Her kaynak Tier 0-3 arası güvenilirlik puanına sahip
  ▼
TOPLAMA (Fetch)
  │  Tüm kaynaklardan RSS beslemeleri otomatik çekilir
  │  URL ve başlık bazında tekilleştirme yapılır
  ▼
KÜMELEME (Clustering)
  │  Aynı haber farklı kaynaklardan gelirse kümelenir
  │  Örtüşme skoru ≥%40 → aynı haber
  ▼
ÇAPRAZ DOĞRULAMA (Cross-Verification) ⭐ YENİ
  │  Her küme için: kaç kaynak bildiriyor? Hangi kademede?
  │  CONFIRMED: 2+ Tier 0 → otomatik onay
  │  HIGH_CONFIDENCE: 1 Tier 0 + 1 Tier 1 → insan onayı gerekmez
  │  MEDIUM_CONFIDENCE: 2+ Tier 1 → insan kontrolü önerilir
  │  LOW_CONFIDENCE: tek kaynak → İNSAN ONAYI ZORUNLU
  ▼
FACT-CHECK RAPORU (fact-check-report.md) ⭐ YENİ
  │  Hangi kaynaklar aynı fikirde? Varsa tutarsızlıklar neler?
  │  Kaynak zinciri ve güven seviyesi belgelenir
  ▼
WRITER AGENT (draft-package.md)
  │  SADECE brief'teki kaynaklardaki bilgileri kullanır
  │  Her iddia bir kaynağa bağlanmalıdır
  │  Halüsinasyon = sistem hatası
  ▼
VERIFIER AGENT (verifier-report.md) ⭐ GÜNCELLENDİ
  │  KONTROL 1: Kaynak atıfları doğru mu? (source_attribution_audit)
  │  KONTROL 2: Halüsinasyon var mı? (uydurma iddia tespiti)
  │  KONTROL 3: Rubric skoru (0-12)
  │  KONTROL 4: Slop kalıpları
  ▼
İNSAN ONAYI (draft_review)
  │  Her haber insan tarafından okunur
  │  Kaynak zinciri doğrulanır
  ▼
YAYIN (published)
  │  Kaynak atıflarıyla birlikte Memos'a gönderilir
  ▼
FEEDBACK DÖNGÜSÜ
  │  24s: metrik toplama, hata kontrolü
  │  72s: derin analiz, correction check
  ▼
DÜZELTME WORKFLOW'U (correction.md) ⭐ YENİ
  │  Hatalı haber → correction notice → düzeltilmiş sürüm
  │  Veya: retraction (tamamen geri çekme)
```

---

## Aşama Detayları

### AŞAMA 0: NEWS FETCH (Yeni)
**Sistem dış kaynaklardan haberleri çeker.**

```
Kaynak listesi: source-watchlist.md (26+ kaynak)
Yöntem: RSS/Atom beslemeleri
Çıktı: FetchedNewsItem listesi (title, url, source, tier)
```

**Eylem:** `hermes haber fetch` veya `/haber fetch`

---

### AŞAMA 0.5: CLUSTERING & VERIFICATION (Yeni)
**Aynı haber kümelenir ve çapraz doğrulanır.**

```
Giriş: FetchedNewsItem listesi
İşlem:
  1. Başlık normalizasyonu (temizlik, lowercase)
  2. Kelime örtüşmesi ≥%40 → aynı küme
  3. Her küme için: kaynak sayısı, tier dağılımı
  4. VerificationLevel ataması
Çıktı: CrossVerificationResult (fact-check-report.md)
```

**Eylem:** `hermes haber verify` veya `/haber verify`

**Threshold:**
- CONFIRMED (Level 3): 2+ Tier 0 kaynaktan haber → otomatik yayına hazır
- HIGH_CONFIDENCE (Level 2): 1 Tier 0 + 1 Tier 1 → insan onayı opsiyonel
- MEDIUM_CONFIDENCE (Level 1): 2+ Tier 1 → insan kontrolü önerilir
- LOW_CONFIDENCE (Level 0): Tek kaynak → İNSAN ONAYI ZORUNLU
- UNVERIFIED: Yayınlanamaz → neden belirtilir

---

### AŞAMA 1: captured
**Haber sisteme ilk kez girer.**

- **Giriş:** Fetch sonucu veya manuel fikir
- **Route:** VERIFIED (çok kaynaklı haber) veya ORIGINAL/REWRITE/REPURPOSE
- **Çıkış:** `haber-object.md` oluşturulur
- **State:** `captured` (veya otomatik `fact_checking`)

---

### AŞAMA 1.5: fact_checking (Yeni — News Pipeline)
**Çapraz doğrulama devam ediyor.**

- Bekleme durumu. RSS taraması veya kaynak karşılaştırması sürüyor.
- Süreç tamamlanınca state `cross_verified` olur.

---

### AŞAMA 2: cross_verified (Yeni — News Pipeline)
**Haber doğrulandı. Artık brief yazılabilir.**

- `fact-check-report.md` okunur
- Route `VERIFIED` ise: Writer Agent'a kaynak listesi ve güven seviyesi verilir
- İnsan `idea_review`'e geçmeli

---

### AŞAMA 3-15: (Öncekiyle aynı — idea_review → learned)

> **ÖNEMLİ FARKLAR:**
> - Writer Agent: Her iddia için kaynak atfı ZORUNLU
> - Verifier Agent: source_attribution_audit bölümü EKLENDİ
> - Hallucination check: brief'te olmayan iddia = SİSTEM HATASI
> - `published` state'inden sonra `correction_needed` state'ine geçilebilir

---

### YENİ AŞAMA: correction_needed (v3.0)
**Yayın sonrası hata tespit edildi. Düzeltme yapılmalı.**

**Tetikleyiciler:**
- Geri bildirimde hata bildirimi
- Otomatik taramada tutarsızlık
- İnsan tarafından fark edilen hata

**Eylem:**
1. `correction.md` yaz: hata tanımı + doğru bilgi
2. Corrections API ile düzeltme yayınla
3. State: `corrected` veya `retracted`

---

### YENİ AŞAMA: corrected (v3.0)
**Düzeltme yayınlandı. Orijinal haber güncellendi veya uyarı eklendi.**

---

### YENİ AŞAMA: retracted (v3.0)
**Haber tamamen geri çekildi. Güvenilirlik için zorunlu.**

**Ne zaman yapılır:**
- Haberin ana iddiası yanlış çıktıysa
- Kaynaklar haberi yalanladıysa
- Manipülasyon veya yanlış yönlendirme tespit edildiyse

**Etki:** `correction.md` → `## Retraction Statement` bölümü yazılır
