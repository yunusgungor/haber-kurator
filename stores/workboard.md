# Workboard — Haber Akışı Sırası

> Bu dosya, işleme alınacak güncel haberlerin sırasını tutar.
> Haberler `strategy/pillars.md` dosyasındaki sütunlara (Pillar) göre işlenir.
> Güncellenir: Her yeni haber yakalandığında veya yayınlandığında.

---

## Öncelik Sırası (Canlı Bülten)

| # | Haber Slug / ID | State | Pillar | Not |
|---|-----------------|-------|--------|-----|
| 1 | 2026-05-ornek-haber-1 | idea_review | **Pillar 1 — Teknoloji, Yapay Zeka** | Reuters'tan alındı, memo yazımı için brief bekliyor. |
| 2 | *(inbox'tan çekilecek)* | captured | **Pillar 2 — Küresel Gelişmeler** | Sıradaki yeni haber. |
| 3 | *(inbox'tan çekilecek)* | captured | **Pillar 3 — İş Dünyası ve Ekonomi** | Sıradaki yeni haber. |

---

## Yapılacaklar (Günlük Kürasyon Görevleri)

- [ ] **Haber Taraması:** `strategy/source-watchlist.md` listesinden güncel 3 kritik haberi Inbox'a aktar.
- [ ] **Memos Üretimi:** Seçilen haberleri `hermes haber new` komutuyla (route: REWRITE/RESEARCH) Haber-Kuratör pipeline'ına sok.
- [ ] **Draft Onayı:** Verifier Agent tarafından taranan 3 haberi (Slop Scan ve Rubric) kontrol et ve yayınla.

---

## Açıklama (Haber State'leri)

- **captured:** Haber linki veya kaba özeti eklendi.
- **idea_review:** Haberin yayınlanmaya değer (newsworthy) olup olmadığına karar verildi.
- **brief_ready:** Haber taslağı için gerekli yönergeler (kaynak link, uzunluk vs.) hazır.
- **drafting:** AI haberi Memos formatında yazdı.
- **verification:** Slop pattern (Taraf tutma/Clickbait) taraması yapılıyor.
- **draft_review:** Memos taslağı onay bekliyor.
- **approved:** Yayın sırasına girdi.
- **published:** memos.googig.cloud platformunda yayınlandı.
