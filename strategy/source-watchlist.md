# Source Watchlist — Haber Kuratör v3.1.0

> **Güvenilirlik Kademeleri:** Dünyanın önde gelen, doğruluğu kanıtlanmış medya kaynakları.
> Her haber en az 2 bağımsız kaynakta doğrulanmadan yayınlanmaz.
> Sistem otomatik olarak bu kaynaklardan RSS çeker, hikayeleri kümeler ve çapraz doğrular.

---

## 🔴 TIER 0 — PRIMARY (Wire Services) — En Yüksek Güvenilirlik

> **Kural:** 2+ farklı Tier 0 kaynağı aynı haberi bildiriyorsa → CONFIRMED (otomatik onay)
> Bu kaynaklar dünyanın en sıkı editoryal standartlarına sahiptir.

| # | Kaynak | Kategori | RSS Durumu | Özellik |
|---|--------|----------|------------|---------|
| 1 | **Reuters** | Genel Haber | ✅ Aktif | Dünyanın en büyük haber ajansı. 2,500+ gazeteci, 200+ lokasyon. |
| 2 | **Associated Press (AP)** | Genel Haber | ✅ Aktif | 1846'dan beri bağımsız haber ajansı. 1,500+ gazete tarafından kullanılır. |
| 3 | **Agence France-Presse (AFP)** | Genel Haber | ✅ Aktif | 1835'te kurulan 3. büyük küresel ajans. 2,400+ gazeteci, 151 ülke. |
| 4 | **BBC News** | Genel Haber | ✅ Aktif | Birleşik Krallık kamu yayıncısı. Kraliyet tüzüğü ile editoryal bağımsızlık. |

---

## 🟡 TIER 1 — MAJOR (Büyük Yayıncılar) — Yüksek Güvenilirlik

> **Kural:** 1 Tier 0 + 1 Tier 1 = VERIFIED. 2+ Tier 1 = MEDIUM CONFIDENCE.
> Pulitzer ödüllü, köklü editoryal süreçleri olan yayıncılar.

### Genel Haber
| # | Kaynak | RSS Durumu | Not |
|---|--------|------------|-----|
| 5 | **The New York Times** | ✅ Aktif | 138+ Pulitzer. ABD'nin en çok ödüllü gazetesi. |
| 6 | **The Washington Post** | ✅ Aktif | 70+ Pulitzer. Watergate, NSA belgeleri gibi tarihi haberler. |
| 7 | **The Guardian** | ✅ Aktif | Birleşik Krallık. Çok sayıda ödüllü araştırmacı gazetecilik. |
| 8 | **Al Jazeera English** | ✅ Aktif | Küresel haber ağı. Sahada güçlü varlık. |
| 9 | **NPR** | ✅ Aktif | ABD kamu radyosu. Tarafsız ve kapsamlı habercilik. |

### İş & Ekonomi
| # | Kaynak | RSS Durumu | Not |
|---|--------|------------|-----|
| 10 | **Bloomberg** | ✅ Aktif | 2,700+ gazeteci, 120 ülke. Finans haberlerinde altın standart. |
| 11 | **The Wall Street Journal** | ✅ Aktif | İş dünyasının bir numaralı gazetesi. Pulitzer ödüllü. |
| 12 | **Financial Times** | ✅ Aktif | Küresel iş dünyası. Doğru, kaynaklı finans haberciliği. |
| 13 | **The Economist** | ✅ Aktif | Haftalık analiz. Derinlemesine, veriye dayalı haber. |
| 14 | **CNBC** | ✅ Aktif | ABD iş dünyası ve finans haber ağı. |
| 15 | **Harvard Business Review** | ✅ Aktif | Akran denetimli iş dünyası araştırmaları. |

---

## 🟠 TIER 2 — SPECIALIZED (Uzman Yayıncılar) — Orta-Yüksek

> **Kural:** Sadece Tier 2 kaynağa dayanan haberler LOW CONFIDENCE olarak işaretlenir.
> İnsan onayı olmadan yayınlanamaz. Sadece belirtilen kategorilerde yetkindir.

### Teknoloji
| # | Kaynak | RSS Durumu | Not |
|---|--------|------------|-----|
| 16 | **MIT Technology Review** | ✅ Aktif | MIT bünyesinde. Yapay zeka ve teknoloji politikası. |
| 17 | **The Verge** | ✅ Aktif | Teknoloji haberleri, inovasyon ve politika. |
| 18 | **Wired** | ✅ Aktif | 1993'ten beri teknoloji kültürü. |

### Bilim
| # | Kaynak | RSS Durumu | Not |
|---|--------|------------|-----|
| 19 | **Nature** | ✅ Aktif | 1869'dan beri. Akran denetimli. Dünyanın önde gelen bilim dergisi. |
| 20 | **ScienceDaily** | ✅ Aktif | Akran denetimli dergilerden haberler. |
| 21 | **Scientific American** | ✅ Aktif | 1845'ten beri. Popüler bilim. |
| 22 | **New Scientist** | ✅ Aktif | Güncel bilim haberleri ve keşifler. |

---

## 🇹🇷 TÜRKÇE KAYNAKLAR — Türkiye Haberleri

> Türkiye'de yaşadığın için Türk haber kaynakları ayrı bir öneme sahip.
> Aşağıdaki kaynaklar Türkiye gündemini, ekonomisini, teknolojisini ve dünyadan Türkçe haberleri takip eder.
> Çapraz doğrulama: Bir Türkiye haberi, 2+ bağımsız Türk kaynağında veya 1 uluslararası + 1 Türk kaynağında teyit edilmelidir.

### 🔴 Tier 1 — MAJOR (Yüksek Güvenilirlik)

| # | Kaynak | Kategori | RSS | Özellik |
|---|--------|----------|-----|---------|
| 23 | **Anadolu Ajansı (AA)** | Genel Haber | ✅ `aa.com.tr/rss/ajansguncel.xml` | Türkiye'nin resmî haber ajansı. 1920'den beri. Wire service. |
| 24 | **BBC Türkçe** | Genel Haber | ✅ `feeds.bbci.co.uk/turkce/rss.xml` | BBC'nin Türkçe servisi. Kraliyet tüzüğü ile bağımsız. |
| 25 | **Euronews Türkçe** | Genel Haber | ✅ `tr.euronews.com/rss` | Çok dilli haber ağının Türkçe servisi. |
| 26 | **Deutsche Welle Türkçe** | Genel Haber | ✅ `rss.dw.com/rdf/Turkish` | Alman kamu yayıncısının Türkçe servisi. |
| 27 | **Bloomberg HT** | Ekonomi/Finans | ✅ `bloomberght.com/rss` | Bloomberg'in Türkiye ortaklığı. Finans haberciliği. |

### 🟠 Tier 2 — SPECIALIZED (Uzman / Bağımsız)

| # | Kaynak | Kategori | RSS | Özellik |
|---|--------|----------|-----|---------|
| 28 | **T24** | Genel Haber | ✅ `t24.com.tr/rss` | Bağımsız haber sitesi. Araştırmacı gazetecilik. |
| 29 | **Medyascope** | Genel Haber | ✅ `medyascope.tv/feed/` | Bağımsız haber platformu. Canlı yayın ve podcast. |
| 30 | **Gazete Duvar** | Genel Haber | ✅ `gazeteduvar.com.tr/rss` | Bağımsız internet gazetesi. Kültür-sanat. |
| 31 | **Diken** | Genel Haber | ✅ `diken.com.tr/feed/` | Bağımsız, eleştirel haber sitesi. |
| 32 | **BirGün** | Genel Haber | ✅ `birgun.net/rss` | Bağımsız sol gazete. Hak haberciliği. |
| 33 | **Sözcü** | Genel Haber | ✅ `sozcu.com.tr/feeds-haberler` | Türkiye'nin en çok okunan gazetelerinden. |
| 34 | **Cumhuriyet** | Genel Haber | ✅ `cumhuriyet.com.tr/rss/son_dakika.xml` | 1924'ten beri. Köklü gazetecilik geleneği. |
| 35 | **Hürriyet** | Genel Haber | ✅ `rss.hurriyet.com.tr/` | Geniş muhabir ağı. Güncel haber ve analiz. |
| 36 | **Webrazzi** | Teknoloji | ✅ `webrazzi.com/feed/` | Türkiye teknoloji haberciliği. Girişim odaklı. |

### Çapraz Doğrulama Kuralları (Türkiye Haberleri İçin)

| Senaryo | Minimum Doğrulama |
|----------|------------------|
| Uluslararası haber (Türkçe) | BBC Türkçe + Euronews Türkçe veya 1 uluslararası Tier 0 + 1 Türk kaynağı |
| Türkiye iç politika | AA + T24/Medyascope/Diken (2+ bağımsız) |
| Ekonomi haberi | Bloomberg HT + AA veya uluslararası Tier 1 |
| Teknoloji haberi | Webrazzi + uluslararası Tier 2 veya 2 Türk kaynağı |
| Yerel haber | AA + en az 1 bağımsız Türk kaynağı |

> **Uyarı:** Tek kaynaktan gelen Türkiye haberi LOW_CONFIDENCE olarak işaretlenir.
> İnsan onayı olmadan yayınlanamaz. Özellikle iç politika haberlerinde çapraz doğrulama şarttır.

---

## ⛔ REDLIST — Asla Kullanılmayacak Kaynaklar

> Bu kaynaklardan gelen bilgiler sisteme alınmaz, otomatik olarak reddedilir.
> Güncelleme: Süreç içinde genişletilecek.

- Bilinmeyen kaynaklar / doğrulanmamış web siteleri
- Sivil toplum / aktivist organizasyonların tarafsız olmayan yayınları
- Kullanıcı tarafından manuel olarak eklenecek

---

## Otomatik RSS Besleme Ayarları

> Sistem, her `haber haber fetch` veya `hermes haber fetch` komutunda
> yukarıdaki tüm kaynaklardan RSS beslemelerini otomatik çeker.
> Hikaye benzerliğine göre kümeler ve çapraz doğrulama yapar.

**Besleme Sıklığı:** Her komut çalıştırmada canlı
**Hata Yönetimi:** Erişilemeyen kaynak atlanır, loglanır
**Deduplikasyon:** Aynı haber birden fazla kaynaktan gelirse tekilleştirilir
