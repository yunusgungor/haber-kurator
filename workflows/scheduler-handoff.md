# Workflow: Scheduler Handoff

> İçerik onaylandıktan sonra yayınlama planlayıcıya (memos-cli, Postiz, vs.) teslim prosedürü.

---

## Genel Bakış

```
APPROVED (AŞAMA 7)
       │
       ▼
  SCHEDULER READY (AŞAMA 8)
       │
       ▼
  SON KONTROLLER
       │
       ├──► Görsel hazırlığı
       ├──► Metadata hazırlığı
       ├──► Zamanlama seçimi
       └──► Yedekleme
       │
       ▼
  SCHEDULED (AŞAMA 9)
       │
       ▼
  PUBLISHED (AŞAMA 10) — memos-cli veya Manuel
```

---

## Adım 1: Son Kontroller

### Görsel Kontrolü
```
┌─────────────────────────────────────────────────────┐
│  GÖRSEL KONTROLÜ                                  │
├─────────────────────────────────────────────────────┤
│                                                     │
│  [ ] Görsel dosyası mevcut mu?                   │
│      Dosya: {path}                                 │
│                                                     │
│  [ ] Boyut uygun mu?                              │
│      X: 1200x675px (optimal) veya 16:9 oran       │
│      Gerçek: ___ x ___ px                         │
│                                                     │
│  [ ] Dosya formatı doğru mu?                      │
│      PNG (önerilen) veya JPG                      │
│      Gerçek: {format}                              │
│                                                     │
│  [ ] Alt text / açıklama yazıldı mı?              │
│      "Bu görselde X gösteriliyor.                  │
│       Takeaway: Y."                                │
│                                                     │
│  [ ] Görsel metrik içeriyor mu?                   │
│      (Ekran görüntüsü varsa, metrikler OKUNABILIR │
│       olmalı — küçük font = okunma kaybı)        │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Metadata Kontrolü
```
┌─────────────────────────────────────────────────────┐
│  METADATA KONTROLÜ                                 │
├─────────────────────────────────────────────────────┤
│                                                     │
│  HASHTAG'LER (maksimum 3-5):                    │
│  [ ] #{hashtag1} — [ilgi alanı]                   │
│  [ ] #{hashtag2} — [ilgi alanı]                   │
│  [ ] #{hashtag3} — [ilgi alanı]                   │
│  [ ] #{hashtag4} — [opsiyonel]                    │
│  [ ] #{hashtag5} — [opsiyonel]                    │
│                                                     │
│  ⚠️ Hashtag kuralları:                            │
│  • Her hashtag en az 10.000 post içermeli        │
│  • Niş hashtag > genel hashtag                    │
│  • #RISCV > #technology                          │
│                                                     │
│  MENTIONS (varsa):                               │
│  [ ] @{hesap} — [neden?}                          │
│                                                     │
│  CALL-TO-ACTION (varsa):                         │
│  [ ] CTA metni: "____________"                     │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## Adım 2: Zamanlama Stratejisi

### Hedef Kitle Analizi
```
┌─────────────────────────────────────────────────────┐
│  ZAMANLAMA ANALİZİ                                 │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Hedef kitle: {brief'teki hedef kitle}            │
│                                                     │
│  Tahmini zaman dilimi (kullanıcı timezone):       │
│  [ ] Pazartesi-Cuma: 08:00-10:00 (iş başı)       │
│  [ ] Pazartesi-Cuma: 12:00-14:00 (öğle arası)    │
│  [ ] Pazartesi-Cuma: 17:00-19:00 (iş çıkışı)     │
│  [ ] Hafta sonu: 10:00-12:00                       │
│                                                     │
│  Bülten ise:                                        │
│  [ ] İlk madde UTC 09:00-11:00 arası             │
│  [ ] Geri kalan madde'ler 1 saat arayla          │
│                                                     │
│  SEÇİLEN ZAMAN: {tarih + saat}                    │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Platform-Özgü Notlar

**Memos Platformu:**
- Optimal zamanlar: Hafta içi 08:00-10:00 ve 17:00-19:00 (hedef kitleye göre ayarla)
- Bülten'ler: Sabah erken (08:00 UTC) veya akşam geç (20:00 UTC)
- Görseller: 1200x675px optimal, 16:9

**LinkedIn:**
- Hafta içi 08:00-09:00 ve 17:00-18:00
- Makale formatı için: Salı-Perşembe

**Instagram:**
- Hafta içi 11:00-13:00 ve 19:00-21:00
- Detaylı Rapor: Aynı gün içinde stack

---

## Adım 3: Yayınlama Yöntemi

### Yöntem A: memos-cli ile Otomatik (Önerilen)
```
# memos-cli ile tek madde
memos-cli post "{madde içeriği}"

# memos-cli ile bülten
memos-cli post "{madde1}" && memos-cli reply "{parent_id}" "{madde2}" && ...

# memos-cli ile görsel
memos-cli post "{içerik}" --image /path/to/image.png
```

### Yöntem B: Manuel Planlama (Memos / Postiz / vs.)
```
Memos'e gönder:
├── İçerik: {draft'tan}
├── Görsel: {varsa}
├── Hashtag'ler: {list}
├── Platform: Memos Platformu
├── Zamanlama: {tarih + saat}
└── İçerik objesi: haber-object.md'deki ID
```

### Yöntem C: Manuel (Kullanıcı Kendisi)
```
Hermes hazırladı, kullanıcı yayınlayacak:
├── [ ] Draft kopyalandı
├── [ ] Görsel hazır
├── [ ] Hashtag'ler kopyalandı
├── [ ] Yayınlama zamanı belirlendi
└── → Kullanıcıya bildir
```

---

## Adım 4: Yedekleme

**Yayınlamadan önce:**

```
┌─────────────────────────────────────────────────────┐
│  YEDEKLEME KONTROLÜ                                 │
├─────────────────────────────────────────────────────┤
│                                                     │
│  [ ] Draft birden fazla yere kaydedildi:           │
│      □ haber-kurator/runs/active/{slug}/draft-package  │
│      □ Google Docs / Notion                        │
│      □ Google Keep (hızlı erişim)                  │
│                                                     │
│  [ ] Post ID / URL kaydedildi:                     │
│      haber-object.md → published_url:            │
│                                                     │
│  [ ] Yayınlama hatırlatıcısı kuruldu:             │
│      □ Cron job                                    │
│      □ Takvim hatırlatıcı                          │
│      □ Alarm                                       │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## Adım 5: Yayınlama Sonrası

**Post yayınlandıktan hemen sonra:**

```bash
# haber-object.md güncelle
# status: "published"
# published_url: "{URL}"
# published_at: "{YYYY-MM-DD HH:MM}"

# Run folder'a not düş
echo "PUBLISHED: {slug} at {URL} on {YYYY-MM-DD HH:MM}" >> feedback.md
```

**Schedule'a kaydet:**
```markdown
# Yayınlama Kaydı

## Meta
- **Tarih:** {YYYY-MM-DD HH:MM}
- **Platform:** Memos Platformu
- **Post URL:** {URL}
- **Yöntem:** {memos-cli / Manuel / Postiz}
- **Zamanlama:** {planlanan vs. gerçekleşen}

## Yayınlama Özeti
- İçerik: {slug}
- Format: {format}
- Görsel: {var/yok}
- Hashtag'ler: {list}

## 24s Hatırlatıcı
- [ ] Feedback toplanacak
- [ ] Metrikler kaydedilecek
- [ ] Postmortem çalıştırılacak
```

---

## Otomatik Cronjob Entegrasyonu

**Önerilen:** Her Pazar akşamı bir sonraki haftanın içerik takvimini planla.

```
┌─────────────────────────────────────────────────────┐
│  HAFTALIK İÇERİK TAKVİM                           │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Pazartesi:    {post 1} — {format} — {pilar}     │
│  Çarşamba:    {post 2} — {format} — {pilar}     │
│  Cuma:         {post 3} — {format} — {pilar}     │
│                                                     │
│  Takvimde işaretle:                                │
│  [ ] Pazartesi 09:00 UTC                          │
│  [ ] Çarşamba 09:00 UTC                           │
│  [ ] Cuma 09:00 UTC                               │
│                                                     │
└─────────────────────────────────────────────────────┘
```
