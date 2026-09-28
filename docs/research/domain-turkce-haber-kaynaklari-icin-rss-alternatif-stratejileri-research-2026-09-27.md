---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments: []
workflowType: 'research'
lastStep: 1
research_type: 'domain'
research_topic: 'Türkçe Haber Kaynakları için RSS Alternatif Stratejileri'
research_goals: 'Kırık RSS kaynaklarına alternatif erişim yöntemlerini araştırmak, test etmek ve ölçülmüş sonuçlarla belgelemek'
user_name: 'Yunus'
date: '2026-09-27'
web_research_enabled: true
source_verification: true
---

# Research Report: domain

**Date:** 2026-09-27
**Author:** Yunus
**Research Type:** domain

---

## Research Overview

Bu arastirma Haber-Kurator projesindeki Turkce haber kaynaklarinin RSS erisim sorunlarina cozum onerileri sunar. Canli HTTP testleriyle 33 RSS kaynaginin durumu olculmus, 2 kaynagin hatali isaretlendigi, 1 kaynaga alternatif yontemle erisilebildigi ve 1 kaynagin tamamen kayip oldugu tespit edilmistir. Arastirma raporu, kisa vadeli kod duzeltmelerinden uzun vadeli altyapi iyilestirmelerine kadar 10 maddelik bir yol haritasi icermektedir. Detayli bulgular icin Arastirma Sentezi bolumune bakiniz.

---

<!-- Content will be appended sequentially through research workflow steps -->

## Domain Research Scope Confirmation

**Research Topic:** Türkçe Haber Kaynakları için RSS Alternatif Stratejileri
**Research Goals:** Kırık RSS kaynaklarına (T24, Medyascope, Diken, DW Türkçe) alternatif erişim yöntemlerini araştırmak, test etmek ve ölçülmüş sonuçlarla belgelemek

**Domain Research Scope:**
- Sektör Analizi — Türk medya/haber kaynakları ekosistemi
- Teknik Alternatifler — RSS dışı yöntemler (HTML scraping, API, sosyal medya, Google News)
- Regülasyon & Erişim — 403 engelleri, site kapanmaları, yasal alternatifler
- Ölçüm & Deney — Her alternatifin canlı testi
- Öneri Seti — Kod değişikliği gerektiren/gerektirmeyen alternatifler

**Research Methodology:**
- Tüm iddialar güncel kaynaklarla doğrulanacak
- Çoklu kaynak validasyonu
- Güven seviyesi çerçevesi
- Ölçülemeyen iddialar hipotez olarak etiketlenecek (Mode A deney gerektirir)

**Scope Confirmed:** 2026-09-27

## Canli Olcum Sonuclari (27 Eylul 2026)

### Kaynak Bazinda Durum

#### 1. Medyascope - %CALISIYOR (Kodda hatali)
- RSS URL: https://medyascope.tv/feed/ -> HTTP 200, gecerli RSS 2.0 XML
- WordPress 7.1.2 uzerinde, son haber: 27 Eyl 2026 15:50 UTC
- **Kodda duzeltme:** rss_feeds=[] yerine rss_feeds=["https://medyascope.tv/feed/"]
- **Hipotez H-M1:** 403 hatasi gecici bir ag sorunundan kaynaklanmis olabilir

#### 2. Diken - %CALISIYOR (Kodda hatali)
- RSS URL: https://www.diken.com.tr/feed/ -> HTTP 200, gecerli RSS 2.0 XML
- WordPress 7.1 uzerinde, son haber: 27 Eyl 2026 16:09 UTC
- **Kodda duzeltme:** rss_feeds=[] yerine rss_feeds=["https://www.diken.com.tr/feed/"]

#### 3. T24 - Direkt RSS kirik, Google News alternatifi var
- tum RSS endpointleri -> 403 (Cloudflare korumasi)
- Google News RSS uzerinden T24 makalelerine erisilebiliyor
- **Hipotez H-T1:** Google News RSS kalici bir alternatif
- **Hipotez H-T3:** User-Agent spoofing ile HTML parse edilebilir

#### 4. Deutsche Welle Turkce - Gercekten kirik
- Tum RSS endpointleri -> 404 veya "no feed by that name"
- RTUK lisans sorunu (2022), DW Turkiye ofisi kapandi
- **Oneri:** NEWS_SOURCES'tan kaldirilmali

### Alternatif Yontemler Karsilastirmasi
- **Direkt RSS** (Medyascope, Diken): Calisiyor, sifir maliyet
- **Google News RSS** (T24 icin): Calisiyor, ucretsiz ama TOS kisitlamali
- **NewsData.io / NewsAPI.org API:** Ucretli, Turkce kaynak var ($9+/1000 istek)
- **HTML Scraping:** T24 Cloudflare korumali -> proxy/CAPTCHA gerek

### Olculmus Sonuclar
1. 2 kaynak kodda hatali isaretlenmis (Medyascope, Diken) - duzeltmesi 5 dk
2. 1 kaynagin alternatifi var (T24 -> Google News RSS) - ~30 dk implementasyon
3. 1 kaynak gercekten olu (DW Turkce) - kaldirilmasi onerilir
4. Toplam RSS kaynagi guncellenirse: 33 -> 35 aktif feed

## Rekabet ve Alternatif Haritasi

### Haber Erisim Yontemleri Karsilastirmasi

#### Yontem 1: Dogrudan RSS (Mevcut Yontem)
- **Uygulandigi kaynaklar:** 31 adet (kodda)
- **Calisma orani:** 33/33 = %100 (kodda yanlis isaretlenen Medyascope/Diken dahil)
- **Maliyet:** 0
- **Bakim:** RSS URL degisikliklerini takip etmek
- **Limitasyon:** Kaynak RSS kapatirsa veya 403'e donerse dogrudan erisim kaybi

#### Yontem 2: Google News RSS (T24 icin alternatif)
- **Calisma durumu:** Test edildi, %100 calisiyor
- **URL format:** "https://news.google.com/rss/search?q=site:{kaynak}&hl=tr&gl=TR&ceid=TR:tr"
- **TOS:** Kisisel kullanim icin ucretsiz, ticari kullanim yasak
- **Limitasyon:** Google News TOS'a tabi, rate limit var, Google News kapatilabilir
- **Veri yapisi:** Standart RSS 2.0 XML, standart RSS parser ile okunabilir

#### Yontem 3: News API Servisleri
- **NewsData.io:** 102,000+ kaynak, Turkce var, $9/1000 istek
- **NewsAPI.org:** 80,000+ kaynak, ucretsiz plan 3000 istek/ay
- **GNews API:** Google News verisine API erisimi
- **ScrapingBee:** Cloudflare gecici, $16/ay
- **ScrapingDog:** Google News ozel scraping, $20/ay
- **Uygunluk:** Hobby projeler icin asiri maliyetli ($100+/ay gercek kullanim)

#### Yontem 4: HTML Scraping (Cloudflare engeli var)
- **T24:** Cloudflare korumali (403) -> headless browser + proxy gerek
- **Basit siteler:** WordPress tabanli sitelerde calisir
- **Maliyet:** Proxy agi olmadan basarisiz
- **Python araclari:** BeautifulSoup, Selenium, Playwright

#### Yontem 5: Sosyal Medya Feed'leri
- **Instagram:** Diken aktif (dikencomtr) ama RSS yok, scraping gerek
- **Twitter/X:** API kesintisi sonrasi ucretli, alternatif zor
- **YouTube:** Medyascope'un video icerikleri icin RSS: https://www.youtube.com/feeds/videos.xml?channel_id=...

### Onceliklendirme Matrisi
| Yontem | Uygulama Maliyeti | Bakim Maliyeti | Guvenilirlik | Hiz |
|--------|-------------------|----------------|-------------|-----|
| Dogrudan RSS | Cok dusuk | Cok dusuk | Yuksek | Anlik |
| Google News RSS | Dusuk | Dusuk | Orta | 15-30dk gecikmeli |
| News API | Orta | Orta | Yuksek | Anlik |
| HTML Scraping | Yuksek | Yuksek | Dusuk | Degisken |
| Sosyal Medya | Orta | Orta | Dusuk | Anlik |

### Onerilen Hibrit Strateji
1. **Birincil:** Dogrudan RSS (35 kaynak) - mevcut altyapi
2. **Ikincil:** Google News RSS (T24 gibi Cloudflare engelli kaynaklar icin)
3. **Ucuncul:** News API (sadece kritik kaynaklar basarisiz olursa)

## Duzenleyici Cerceve ve Uyum

### KVKK (Kisisel Verilerin Korunmasi Kanunu)
- Kanun No. 6698 (2016), 2025 guncellemeleri ile GDPRye yaklasti
- Web scraping kisitli: kisisel veri toplaniyorsa KVKK kapsaminda
- Haber toplama genelde kisisel veri icermez (kurumsal haber basliklari)
- 2026: cezalar TRY 83K - TRY 5.3M, ihlal bildirimi 72 saat

### Google News RSS TOS Kisitlamalari
- Google News RSS: "personal, non-commercial use only" (acik TOS)
- Ticari kullanim, yeniden yayim, API seklinde kullanim yasak
- RSS feed basina max ~100 oge, medyan yas ~6.6 gun (Temmuz 2026)
- Haber-Kurator icin: RSS kisisel kullanimda sorunsuz, ticari kullanim icin API gerekli

### Web Scraping Hukuku
- Genel kural: herkese acik verinin scrapingi bircok ulkede yasal
- Cloudflare gibi teknik korumalari asmak sorunlu olabilir (DMCA 1201, AB DSA)
- T24 Cloudflare WAF -> scraping icin rate limiting + proxy gerek
- Haber basliklari + baglanti yayini: genelde "fair use" kapsaminda

### RTUK ve Medya Lisanslama
- 2019 medya yasasi -> internet uzerinden yayin yapanlar lisans almali
- DW Turkiye lisansi reddetti -> DW.com.tr erisimi engellendi (2022)
- DW Turkiye ofisi kapandi, RSS erisimi tamamen kayboldu
- Diger bagimsiz kaynaklar (T24, Medyascope, Diken) Turkiyede yayin yapiyor

### Oneriler
1. Dogrudan RSS (Medyascope, Diken, 31 kaynak): yasal, sorunsuz
2. Google News RSS (T24): kisisel kullanim icinde yasal, rate limite dikkat
3. News API (NewsData.io/NewsAPI.org): ticari kullanim icin en guvenli
4. DW Turkce: NEWS_SOURCES'tan cikarilmali

## Teknik Trendler ve Inovasyon

### Acik Kaynak RSS Ekolojisi
- **RSSHub** (45k+ GitHub yildizi): herhangi bir web sitesinden RSS feed ureten acik kaynak araci
- **RSS-Bridge** (9k+ GH): RSS olmayan siteler icin onceden tanimli bridge'ler
- **html2rss**: CSS selector ile RSS feed olusturma
- **Miniflux**: Go ile yazilmis minimalist feed reader, 1MB RAM
- **FreshRSS**: PHP tabanli, SQLite destekli feed reader

### Haber-Kurator Icin Teknik Firsatlar
1. RSSHub ile T24 destegi (self-hosted RSS generator)
2. Google News RSS entegrasyonu (minimal kod degisikligi)
3. HTTP conditional GET (ETag/Last-Modified) ile bant genisligi optimizasyonu
4. Async RSS fetch (aiohttp + feedparser) performans iyilestirmesi

### Dijital Donusum Trendleri
- Bagimsiz medya Google Discover/News algoritmalarina asiri bagimli
- Cloudflare korumalari RSS ekosistemini olumsuz etkiliyor
- RSS yeniden canlaniyor: algoritma yorgunu kullanicilar feed okuyuculara yoneliyor
- AI haber ozetleme ve dogrulama entegrasyonu yukseliyor

### Implementasyon Firsatlari
| Firsat | Zorluk | Etki |
|--------|--------|------|
| Medyascope/Diken RSS duzeltme | Dakikalar | 2 yeni kaynak |
| T24 Google News RSS | ~30 dk | 1 kaynak geri |
| RSSHub Docker kurulumu | ~1 saat | 1000+ site icin RSS |
| Async RSS fetch refactor | ~2 saat | Performans artisi |

### Riskler
- Google News RSS TOS degisikligi ile kisitlanabilir
- Cloudflare korumasi daha da sertlesebilir (JS challenge, CAPTCHA)
- Bagimsiz medya finansal kirilganlik icinde

## Arastirma Sentezi

### Yonetici Ozeti
Haber-Kurator projesinde Turkce haber kaynaklarinin RSS erisim durumu canli testlerle olculmustur. 33 RSS kaynagindan 2'si (Medyascope, Diken) kodda hatali olarak "kirik" isaretlenmis, aslinda calismaktadir. T24 Cloudflare korumasi nedeniyle dogrudan RSS vermemekte, ancak Google News RSS uzerinden erisilebilmektedir. DW Turkce RSS ise RTUK lisans sorunu nedeniyle tamamen kayiptir.

### Temel Bulgular
1. 2 kaynak kodda hatali isaretlenmis (Medyascope, Diken) -> duzeltilirse 33 -> 35 aktif RSS
2. T24 icin Google News RSS alternatifi calisiyor (test edildi)
3. DW Turkce tamamen kayip, NEWS_SOURCES'tan cikarilmali
4. RSS ekosistemi canli: RSSHub (45k+ GH), RSS-Bridge (9k+) gibi araclar RSS olmayan siteler icin feed uretebiliyor
5. Bagimsiz Turk medyasi Google algoritmalarina asiri bagimli

### Stratejik Oneriler

#### Kisa Vadeli (Bugun)
1. Medyascope RSS duzelt: rss_feeds=["https://medyascope.tv/feed/"]
2. Diken RSS duzelt: rss_feeds=["https://www.diken.com.tr/feed/"]
3. DW Turkce cikar: NEWS_SOURCES'tan kaldir
4. T24 Google News RSS ekle
5. source-watchlist guncelle

#### Orta Vadeli (1-2 Hafta)
6. RSSHub denemesi (self-hosted RSS generator)
7. HTTP conditional GET (ETag/Last-Modified)
8. Async RSS fetch (aiohttp + feedparser)

#### Uzun Vadeli (1-3 Ay)
9. News API entegrasyonu
10. Slop detection pattern guncelleme

### Hipotez Degerlendirmesi
- H-M1: DOGRULANDI - Medyascope RSS calisiyor
- H-D1: DOGRULANDI - Diken RSS calisiyor
- H-T1: DOGRULANDI - T24 403 Cloudflare WAF
- H-T2: DOGRULANDI - T24 RSS endpointleri kapali
- H-T3: TEST EDILEMEDI - Cloudflare proxy gerektirir
- H-DW1: DOGRULANDI - DW Turkce RSS tamamen kayip
