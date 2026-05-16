# Master Avoid-Slop — 106 Pattern (Haber & Memos Odaklı)

> Haber Kuratör v2.4.0 — Doğrudan `haber_kurator_core.py` regex pattern'lerinden çıkarılmıştır.
> **Yeni Konsept Notu:** Bu sistem artık doğrudan ve tarafsız "Haber/Memos" paylaşımı için yapılandırılmıştır.
> İngilizce AI kalıplarının Türkçe karşılıklarından (Örn: "game-changing" -> "ezber bozan", "oyun değiştirici") kesinlikle kaçının. Haber metni tamamen objektif olmalıdır.
>
> **Tablolar:** # = Pattern ID | Trigger = Aranan regex/kelime | Çözüm = Haber formatına uyarlama

---

## 🔴 Tier 1 — Kritik (Sıfır Tolerans, Derhal Düzelt)

*Eşik: ≥1 pattern → REVISE | ≥3 pattern → REJECT*

| # | Kalıp | Trigger (Regex/Kelime) | Haber Memos Çözümü |
|---|-------|----------------------|--------------------|
| 1 | **Promosyon / Clickbait** | `groundbreaking`, `game-changing`, `revolutionary`, `transformative` | Sil. Haberi abartma, sadece ne olduğunu tarafsız bir dille aktar. (Örn: "Ezber bozan" -> "Yeni geliştirilen") |
| 2 | **Önem Atfetme Abartısı** | `pivotal moment`, `testament to`, `significant step`, `quantum leap` | Haberin önemini sen yorumlama, okuyucu metrikleri okuyup kendi karar versin. |
| 3 | **Belirsiz Atıf** | `experts believe`, `studies show`, `research suggests`, `data shows` | "Uzmanlar söylüyor" deme. "Hangi" uzman/kurum (Örn: "Reuters'a göre", "MIT araştırmasına göre") olduğunu tam yaz. |
| 4 | **Sahte Etkinlik** | `the system compounds`, `the data tells us`, `compound interest of` | Veriyi doğrudan ver, laf kalabalığı yapma. |
| 5 | **Retorik Kurulum** | `the question is whether`, `at its core`, `what if i told you` | Doğrudan olaya/habere gir. Memos kısa olmalıdır. |
| 6 | **Staccato Parçalama** | `no X. no Y. no Z.` veya 4+ kısa cümle | Haberi bu şekilde dramatize etme, düzgün ve akıcı bir bilgi cümlesi kur. |
| 7 | **Em Dash Aşırı Kullanımı** | `--` (1-2'den fazla em dash) | Kısa cümleler veya madde imleri (bullet points) kullan. |
| 8 | **Dolgu Zarfları** | `actually`, `literally`, `quietly`, `simply`, `just`, `basically` | Sil. Objektif haber metninde duygu ve yönlendirme zarfları olmaz. |

---

## 🟡 Tier 2 — Yüksek (3+ = REVISE, 5+ = REJECT)

| # | Kalıp | Trigger (Regex/Kelime) | Haber Memos Çözümü |
|---|-------|----------------------|--------------------|
| 9 | **Copula Avoidance** | `serves as`, `stands as`, `features`, `encompasses` | Basit, net haber dili kullan. Süslü fiillerden kaçın. |
| 10 | **-ing Padding** | `leveraging`, `implementing`, `optimizing`, `enabling` | Aksiyonu doğrudan ve sade bir fiil ile aktar. |
| 11 | **Rule of Three Zorlama** | `three things`, `three reasons`, `three ways` | Yapay liste yapma. Haberde kaç önemli detay varsa o kadar madde yaz. |
| 12 | **Filler Phrases** | `in order to`, `due to the fact that`, `at this point in time` | Uzatma. "Çünkü", "İçin" gibi kısa bağlaçlar kullan. |
| 13 | **Generic Conclusions** | `the future looks bright`, `exciting times ahead` | Haberin sonuna kendi iyimser/kötümser yorumunu ekleme. Doğrudan kaynak linki ile bitir. |
| 14 | **Signposting** | `let's dive in`, `here's what you need to know`, `tldr`, `in conclusion` | "İşte detaylar...", "Hadi inceleyelim..." gibi yapay geçişleri asla kullanma. |
| 15 | **Hyperbolic Quantifiers** | `every single`, `all the time`, `never ever`, `absolutely everyone` | Veriye dayanmayan "herkes", "hiçbir zaman" gibi kelimeleri habercilikte kullanma. |
| 16 | **Hedging** | `it could potentially`, `it might be argued`, `somewhat`, `arguably` | Şüpheliyse haberi yayınlama veya haberi verenin kesin alıntısını kullan. |

---

## 🟢 Tier 3 — Orta (Bağlamda Değerlendir, 8+ = REVISE, 15+ = REJECT)

| # | Kalıp | Trigger (Regex/Kelime) | Haber Memos Çözümü |
|---|-------|----------------------|--------------------|
| 17 | **Passive Voice** | `was/were/been/being + *ed` | Edilgen yapı (passive) habercilikte sıkça kullanılır, ancak bağlamı gizlemediğinden emin ol. |
| 18 | **Elegant Variation** | `also known as`, synonym chains (3+ farklı isim) | Kurum veya teknoloji ismini karmaşıklaştırma, aynı isimle devam et. |
| 19 | **False Ranges** | `from basic to advanced`, `from beginner to expert` | Ürün haberlerinde pazarlama diline girme. |
| 20 | **Conjunction Overuse** | Cümle başı `And` veya `But` (arka arkaya) | Arka arkaya bağlaçlarla uzayan metinler haber akışını bozar. |
| 21 | **Unnecessary Intensifiers** | `very`, `so`, `such` | "Çok büyük", "İnanılmaz hızlı" yerine oran veya sayı ver (Örn: "%40 daha hızlı"). |
| 22 | **Paragraph-Level Vagueness** | `it is important to note that`, `it should be noted that` | "Belirtmek gerekir ki" gibi laf kalabalıklarını at. |
| 23 | **Rhetorical Questions as Statements** | `have you ever wondered`, `can you imagine` | Soru sorup kendin cevaplama. Okuyucu sadece bilgi istiyor. |
| 24 | **Awkward List Introductions** | `there are X things`, `X is/are ...` (liste öncesi) | Listeyi doğrudan ver (Örn: "**Öne Çıkanlar:**"). |
| 25 | **False Precision** | `exactly X.Y%` (gereksiz ondalık) | Kesinlik haberde iyidir ancak gereksiz detaydan (virgülden sonraki) kaçın. |
| 26 | **Clichéd Metaphors** | `level up`, `dive deep`, `game plan`, `road map` | Klişe metaforları at, haberin somut verisine odaklan. |
| 27 | **Self-Referential Humility** | `i may be wrong`, `i could be wrong` | Sen haber sunucususun. Yorum yapmadığın için yanılma ihtimalin yok; kaynağa güven. |
| 28 | **Empty Emphasis** | `[PARANTEZ İÇİ]` veya `UPPERCASE` vurgu | Büyük harflerle bağırarak vurgu yapma. |
| 29 | **Temporal Vagueness** | `recently`, `lately`, `these days` | Net zaman ver: "Dün", "Geçen hafta", "Q1 raporunda". |
| 30 | **False Balance** | `some say X while others say Y`, `on one hand...` | Eğer haberde iki taraf varsa isim ver, yoksam uydurma. |
| 31 | **Unearned Authority** | `as someone who`, `having worked in` | Memos paylaşımlarında yazar ön planda değildir, haber ön plandadır. |
| 32 | **Hedging Through Specificity** | `exactly X.Y` (anlamsız ondalık sayı) | Rakamları doğru kullan. |
| 33 | **Template Language** | `in this post, we... [explore/dive/cover/discuss]` | Doğrudan "Özet:" ile başla. |
| 34 | **Unnecessary Qualification** | `the very real possibility`, `the very real chance` | Yalın kelimeler kullan. |

---

## ⚪ Bonus — Ton (Kontekst Bazlı Değerlendir)

| # | Kalıp | Trigger (Regex/Kelime) | Haber Memos Çözümü |
|---|-------|----------------------|--------------------|
| 35 | **Faux Authority** | `you should`, `you must`, `never do this` | Okuyucuya emir kipiyle tavsiye verme. Sen sadece haber veriyorsun. |
| 36 | **Vibes Over Data** | `it feels like`, `seems to me` | Kişisel hissiyatlarını habere katma. |
| 37 | **Bülten-Bait Hooks** | `here's the thing`, `the secret` | Tıklama tuzağı (clickbait) yapma, başlık içeriğin dürüst bir yansıması olsun. |
| 38 | **Oversharing Backstory** | `X years ago, I/we/my/our...` | Senin veya şirketinin geçmişi değil, haberin konusu önemli. |
| 39 | **Under-Explaining Proof** | `result: %...` (metodoloji yok) | Veri sunuyorsan neyi ölçtüğünü net belirt. |
| 40 | **Pseudo-Technical** | Anlamsız jargon kullanımı | Karmaşık terimleri kısa ve anlaşılır tut. |
