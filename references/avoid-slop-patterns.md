# Avoid-Slop Patterns — 54 Kalıp, 3 Seviye

> AI tarafından üretilen içeriğin "yapay", "otomatik", "ses taklidi" hissi vermesini engelleyen kalıplar.
> Tam liste: 54 kalıp, 3 şiddet seviyesi.
> Kaynak: Memos Küratörü — Haber Kuratör
> Her postmortem'den sonra güncellenir.

---

## Özet

| Tier | Şiddet | İhlal Sayısı | Karar |
|------|--------|-------------|-------|
| **Tier 1** | Kritik | ≥3 | REJECT |
| **Tier 2** | Yüksek | ≥5 toplam | REVISE |
| **Tier 3** | Orta | Bağlamda | Gözden geçir |

---

## Tier 1 — Kritik (Sıfır Tolerans)

> 8 kalıp. Herhangi biri tespit edilirse DÜZELTİLMELİ.

| # | Kalıp | Tetikleyici | Neden | Çözüm |
|---|-------|------------|-------|-------|
| **1** | Promosyon Dili | groundbreaking, game-changing, revolutionary, transformative, paradigm-shifting | Yapay coşku, somut değil | Somut sonuçla değiştir |
| **2** | Önem Atfetme Abartısı | pivotal moment, testament to, a testament to, significant step, quantum leap | Boş övgü, kanıtsız | Spesifik gözlemle değiştir |
| **3** | Belirsiz Atıf | experts believe, studies show, research suggests, data shows, it turns out that | Kaynak yok, genel iddia | Kaynak belirt veya kaldır |
| **4** | Sahte Etkinlik | the system compounds, the data tells us, compound interest of, the power of | İnsani karar yerine mekanik süreç iddiası | Birinci tekil şahıs anlatıma geç |
| **5** | Retorik Kurulum | The question is whether..., At its core..., What if I told you | Gerçek soru değil, manipülatif | Doğrudan iddia ile değiştir |
| **6** | Staccato Parçalama | no X. no Y. no Z. / X. Y. Z. / fail. fail. fail. | Yapay drama, okumayı zorlaştırır | Paragraf olarak yeniden yaz |
| **7** | Tire Aşırı Kullanımı | -- her yerde (em dash > 1-2) | Yapay vurgulama | Virgül, nokta veya noktalı virgül ile değiştir |
| **8** | Dolgu Zarfları | actually, literally, quietly, simply, just, basically | Gereksiz zayıflatma | Çıkar veya cümleyi güçlendir |

### Tier 1 — Concrete Rewrite Örnekleri

```
❌ "This is a groundbreaking approach to timing optimization."
✅ "Bu yaklaşımla ilk iterasyonda timing violation'ların %80'ini yakaladım."

❌ "A pivotal moment in my engineering career."
✅ "Bu hata beni 3 ay geriye götürdü. Bir daha asla aynı hatayı yapmadım."

❌ "Studies show that 90% of engineers struggle with timing."
✅ "GitHub issue tracker'larına baktığınızda, en çok star alan 10 timing
    debugging issue'unun hepsi aynı 3 konuda yoğunlaşmış."

❌ "The system compounds over time."
✅ "Her iterasyonda aynı hatayı düzeltmek yerine, kontrol listesi
    kullandığımda tasarım süresi %40 kısaldı."

❌ "The question is whether we should optimize early or late."
✅ "RTL yazarken mi yoksa synthesis sonrası mı optimize etmeli?
    Cevap: her ikisi farklı maliyet taşıyor."

❌ "Timing. Bugs. Rework. No more."
✅ "Timing violation'lar, bugs ve rework döngüsü — her mühendisin
    kabusu. Ama çözüm var ve beklediğinizden daha basit."

❌ "The solution--it changed everything--was this."
✅ "Çözüm çok basitti: RTL yazmadan önce timing budget hesaplamak."

❌ "This literally saved me 6 months of work."
✅ "Bu yaklaşımla 6 ay tasarım süresinden kurtuldum."
```

---

## Tier 2 — Yüksek (Revize Et)

> 8 kalıp. 3+ tespit edilirse REVISE, 5+ tespit edilirse REJECT.

| # | Kalıp | Tetikleyici | Neden | Çözüm |
|---|-------|------------|-------|-------|
| **9** | Copula Avoidance | serves as, stands as, features, encompasses, utilizes | Yapay resmiyet | Basit fiillerle değiştir: "is", "has", "uses" |
| **10** | -ing Padding | implementing, leveraging, optimizing, enabling | Yapay jargondan kaçış | Gerçek fiillere dönüştür |
| **11** | Rule of Three Zorlama | three things, three reasons, three ways, triad | Mecburen 3'e sıkıştırma | Gerçek sayıyı kullan |
| **12** | Filler Phrases | In order to, Due to the fact that, at this point in time, in today's world | Gereksiz dolgu | Kısalt: "To", "Because", "Now" |
| **13** | Generic Conclusions | The future looks bright, exciting times ahead, the best is yet to come | Boş gelecek vaadi | Somut sonuç veya eylemle değiştir |
| **14** | Signposting | Let's dive in, Here's what you need to know, TL;DR, In conclusion | Yapay sunucu hissi | Doğrudan içeriğe başla |
| **15** | Hyperbolic Quantifiers | every single, all the time, never ever, absolutely everyone | Abartılı ifadeler | Somut nicelikle değiştir |
| **16** | Hedging | it could potentially, it might be argued, somewhat, arguably | Güvensiz ses | Kesin ol veya "bilmiyorum" de |

### Tier 2 — Concrete Rewrite Örnekleri

```
❌ "This tool serves as a comprehensive solution."
✅ "Bu tool timing closure için ihtiyacınız olan her şeyi yapıyor."

❌ "We're leveraging open-source tools for cost reduction."
✅ "Açık kaynak araçları kullanıyoruz — maliyeti düşürüyor."

❌ "Here are three things every engineer should know."
✅ "Timing debugging yaparken kaçınmam gereken 7 hata var.
    En kritik 3'ü şunlar:"

❌ "In order to achieve optimal results."
✅ "En iyi sonuçları almak için."

❌ "The future of ASIC design looks exciting."
✅ "Açık kaynak ASIC toolchain'leri artık ticari araçlarla
    performans farkı %10'un altında."

❌ "Let's dive into the world of RISC-V optimization."
✅ "RISC-V pipeline timing'de en sık yapılan hata..."

❌ "Every single engineer makes this mistake."
✅ "10 mühendisten 7'si bu hatayı yapıyor."

❌ "This approach could potentially save significant time."
✅ "Bu yaklaşım 6 aya kadar tasarım süresi kısaltabilir."
```

---

## Tier 3 — Orta (Gözden Geçir)

> 8+ kalıp. Bağlamda değerlendir. Çok fazla tespit edilirse düzelt.

| # | Kalıp | Açıklama | Çözüm |
|---|-------|---------|-------|
| **17** | Passive Voice | Öznenin gizlendiği cümleler ("was done", "is being built") | Özneyi açıkça belirt |
| **18** | Elegant Variation | Aynı kavramın 3+ farklı şekilde adlandırılması | Tutarlı terim kullan |
| **19** | False Ranges | "from basic to advanced" gibi anlamsız ölçekler | Somut değerlerle değiştir |
| **20** | Conjunction Overuse | "And"/"But" ile başlayan aşırı cümleler | Cümleleri birleştir veya yeniden yapılandır |
| **21** | Unnecessary Intensifiers | "very", "so", "such" gereksiz kullanımda | Çıkar veya güçlü kelime bul |
| **22** | Paragraph-Level Vagueness | Her paragraf genel iddia, somut kanıt yok | Her paragrafa en az 1 kanıt ekle |
| **23** | Rhetorical Questions as Statements | Soru şeklinde sunulan açık cevaplar | Doğrudan ifade et |
| **24** | Awkward List Introductions | "There are X things that..." veya "X is/are..." ile aşırı başlangıç | Doğrudan liste ile başla |
| **25** | False Precision | "exactly 93.7%" gibi gereksiz hassasiyet | Yuvarlaştır veya "yaklaşık" de |
| **26** | Clichéd Metaphors | "level up", "dive deep", "game plan", "roadmap" | Somut eylemle değiştir |
| **27** | Self-Referential Humility | "I may be wrong, but..." | Doğrudan iddia veya kanıt sun |
| **28** | Empty Emphasis | KÖŞELI PARANTEZ veya UPPERCASE aşırı kullanımı | Vurguyu cümle yapısıyla sağla |
| **29** | Temporal Vagueness | "recently", "lately", "these days" — zaman belirtmez | Somut tarih veya dönem belirt |
| **30** | False Balance | "Bazıları X diyor, bazıları Y diyor" — gerçek denge yok | Gerçek perspektifi belirt |
| **31** | Unearned Authority | "As someone who..." veya "Having worked in..." gereksiz | Somut deneyimle destekle |
| **32** | Hedging Through Specificity | "exactly 3.7 nanoseconds" — bilinmeyen bir değer | "yaklaşık" de veya kanıt sun |
| **33** | Template Language | "In this post, we'll explore..." — her post'ta aynı | Farklı giriş kalıpları kullan |
| **34** | Unnecessary Qualification | "the very real possibility" — "real" gereksiz | "the possibility" de |

---

## Bonus Kalıplar — Tone & Voice

| # | Kalıp | Açıklama | Çözüm |
|---|-------|---------|-------|
| **35** | Faux Authority | "You should", "You must", "Never do this" — otoriter ama kanıtsız | Somut sonuçla destekle |
| **36** | Vibes Over Data | "It feels like", "Seems to me" — somut veri yerine hissiyat | Veri sun veya "benim deneyimimde" de |
| **37** | Bülten-Bait Hooks | "Here's the thing:" / "The secret:" — her post'ta | Daha organik girişler kullan |
| **38** | Oversharing Backstory | "5 yıl önce..." — 3 paragraf giriş | Hızlı geç veya backstory gereksiz |
| **39** | Pseudo-Technical | Bilinmeyen jargon — okuyucu için değil | Her teknik terimi açıkla |
| **40** | Under-Explaining Proof | "Sonuç: %40 hız artışı" — nasıl? | Metodoloji veya bağlam ekle |

---

## Slop Kontrol Komutları

Terminalde hızlı kontrol:

```bash
# Promosyon dili
grep -in "groundbreaking\|game-changing\|revolutionary\|transformative" draft.md

# Önem abartısı
grep -in "pivotal\|testament\|significant step" draft.md

# Belirsiz atıf
grep -in "experts believe\|studies show\|research suggests" draft.md

# Tire aşırı kullanımı
grep -oc "\-\-" draft.md  # Hedef: 0-1

# Dolgu zarfları
grep -in "actually\|literally\|quietly\|simply\|just " draft.md

# Tier 2 kontrolü
grep -in "serves as\|stands as\|utilizes" draft.md
grep -in "In order to\|Due to the fact that" draft.md
grep -in "every single\|all the time\|never ever" draft.md
```

---

## Yeni Kalıp Ekleme

Her postmortem'den sonra tespit edilen yeni slop kalıbı:

```markdown
## Kalıp #[N]: [Adı]
- **Tetikleyici:** [regex veya kelime]
- **Neden slop:** [açıklama]
- **Örnek ihlal:** "[taslaktan alıntı]"
- **Düzeltme:** [önerilen rewrite]
- **Eklendi:** YYYY-MM-DD
- **Kaynak:** {post slug}
```

---

## Güncelleme Log'u

| Tarih | Eklenen Kalıp | Tier | Kaynak |
|-------|--------------|------|--------|
| 2026-05-11 | İlk kurulum (54 kalıp) | 1-3 | Haber Kuratör (Memos Küratörü) |
