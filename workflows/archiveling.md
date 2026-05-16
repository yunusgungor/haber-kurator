# Workflow: Archiving — Run Folder'ı Arşivleme

> Bir içerik objesi `learned` state'ine ulaştıktan sonra runs/active'dan runs/archive'a taşınır.
> Bu workflow, archiveling sürecini adım adım açıklar.

---

## Ön Koşul

**Tamamlanmış kontrol listesi:**

- [ ] State = `learned` (postmortem yapıldı, learnings kaydedildi)
- [ ] `feedback.md` mevcut ve dolu
- [ ] `stores/hooks/` veya `stores/proof/` güncellendi (varsa)
- [ ] İnsan onayı alındı

---

## Archiveling Adımları

### Adım 1: Run Folder'ı Doğrula

```bash
# Run folder'ın tam olduğunu kontrol et
ls -la $HABER_KURATOR_PATH/runs/active/{YYYY-MM-slug}/
```

**Olması gereken dosyalar:**
- `haber-object.md` ✅
- `idea.md` ✅
- `brief.md` ✅
- `draft-package.md` ✅
- `verifier-report.md` ✅
- `feedback.md` ✅

**Eksik dosya varsa:** Archiveling'i DURDUR. Eksik dosyayı tamamla veya `missing-note.md` ekle.

---

### Adım 2: State'i `archived` Yap

`haber-object.md`'de state'i güncelle:

```markdown
## State Machine
### State Geçmiş Kaydı

| Tarih | Önceki State | Yeni State | Kim | Not |
|-------|-------------|------------|-----|-----|
| YYYY-MM-DD | learned | archived | Orchestrator/İnsan | Arşivlendi |
```

---

### Adım 3: Run Folder'ı Archive'a Taşı

```bash
# Taşıma (copy + delete — veri kaybını önlemek için önce copy)
mkdir -p $HABER_KURATOR_PATH/runs/archive/{YYYY-MM-slug}
cp -r $HABER_KURATOR_PATH/runs/active/{YYYY-MM-slug}/* \
    $HABER_KURATOR_PATH/runs/archive/{YYYY-MM-slug}/

# Doğrulama
diff -rq $HABER_KURATOR_PATH/runs/active/{YYYY-MM-slug} \
         $HABER_KURATOR_PATH/runs/archive/{YYYY-MM-slug}/

# Aktif folder'ı sil (sadece doğrulama sonrası)
rm -r $HABER_KURATOR_PATH/runs/active/{YYYY-MM-slug}/
```

> ⚠️ **KRİTİK:** `rm -r` komutunu çalıştırmadan ÖNCE `diff` doğrulaması yap. Fark varsa kopyalama başarısız — araştır.

---

### Adım 4: Arşiv Index'ini Güncelle

`runs/archive/index.md` dosyasını oluştur veya güncelle (yoksa oluştur):

```markdown
# Archive Index

## {YYYY-MM}

| Slug | Format | Rota | Yayın Tarihi | Rubric | Okunmalar | Toplam Impressions |
|------|--------|------|-------------|--------|-----------|-------------------|
| 2026-05-riscv-timing-violation | Bülten | ORIGINAL | YYYY-MM-DD | 11/12 | — | — |
```

---

### Adım 5: Proof/Hook Bank Güncellemesini Doğrula

Eğer postmortem'de yeni kanıt veya hook yakalandıysa:

```bash
# Hook bank güncellendi mi kontrol et
ls -la $HABER_KURATOR_PATH/stores/hooks/

# Proof bank güncellendi mi kontrol et
ls -la $HABER_KURATOR_PATH/stores/proof/
```

Güncellenmediyse: Şimdi güncelle veya `stores/{hooks,proof}/.pending/{slug}.md` dosyasına not al.

---

## Post-Archiveling Kontrol Listesi

- [ ] Run folder `runs/active/`'da artık yok
- [ ] Run folder `runs/archive/`'da mevcut
- [ ] `haber-object.md` state = `archived`
- [ ] State geçmiş kaydı güncellendi
- [ ] Arşiv index güncellendi
- [ ] Proof/Hook bank güncellendi (varsa)

---

## /haber archive-do Komutu — Otomatik Sürüm

```bash
/haber archive-do 2026-05-riscv-timing-violation
```

**Otomatik yapar:**
1. Run folder'ın `learned` state'inde olduğunu doğrula
2. Tüm dosyaların mevcut olduğunu kontrol eder
3. `haber-object.md`'de state'i `archived`'e günceller
4. Run folder'ı `runs/active/`'dan `runs/archive/`'a taşır
5. Arşiv index'ini günceller
6. Sonuç raporunu döndürür

**Hata durumları:**
- State `learned` değil → HATA, işlem iptal
- Dosya eksik → HATA, eksik dosyaları listele
- Archive folder zaten var → HATA, üzerine yazma

---

## Arşivden Geri Alma (Unarchive)

Bir içeriği archive'dan active'e geri taşımak nadiren gerekebilir (örneğin revision).

```bash
# Nadir — sadece gerekirse
cp -r $HABER_KURATOR_PATH/runs/archive/{YYYY-MM-slug}/ \
    $HABER_KURATOR_PATH/runs/active/{YYYY-MM-slug}/

# State'i uygun olana güncelle
# haber-object.md'de: archived → draft_review (revizyon için)
# veya: archived → approved (tekrar yayın için)
```

> ⚠️ Bu nadir bir operasyondur. Revision gerekiyorsa normal workflow'u takip et (drafting → verification → review).
