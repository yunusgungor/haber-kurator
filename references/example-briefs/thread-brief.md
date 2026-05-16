# Örnek Brief — Bülten Formatı

> Farklı formatlar için örnek brief'ler. Bunları参考 alarak kendi brief'lerini yaz.

---

## Örnek 1: Bülten Brief (8 Madde)

```markdown
# Writer Context Packet — risc-v-pipeline-timing
## Meta
- **Oluşturan:** hermes-agent
- **Tarih:** 2026-05-11
- **Rota:** ORIGINAL
- **Format:** Bülten
- **Pilar:** ASIC tasarımı / Pipeline optimizasyonu

## Thesis
RISC-V pipeline timing violation'larını ilk iterasyonda yakalamak, 6 aylık gecikmeyi önler.

## Target Reader
SKY130 ile RISC-V tasarımı yapan, OpenROAD deneyimi olan 2-5 yıllık mühendis. İlk timing closure deneyimi öncesinde.

## Angle (Beklenmedik Çerçeve)
Herkes synthesis'den sonra timing'a bakıyor. Ama gerçek savaş RTL书写ında başlıyor.

## Proof Elements
- SKY130 timing data: setup slack = -0.08ns, hold slack = +0.12ns
- OpenROAD raporu iterasyon 4'te düzeldi
- 6 ay gecikme → ilk yakalama ile 2 haftaya düştü

## Constraints
- Format: Bülten, her madde en fazla 280 karakter
- Uzunluk: 6-10 madde
- Ton: Teknik, pratik, doğrudan
- Yasaklı: "groundbreaking", "game-changing", "pivotal moment"
- Görsel: Timing diagram (varsa)

## Voice Anchors
"RISC-V'de timing debugging yaparken ilk hata her zaman aynı yerden geliyor: register-to-register path. OpenROAD raporu okumayı bilmek yetmiyor, raporun hangi satırına bakacağını bilmek gerekiyor."

## Risks (Slop / Cringe Tuzağı)
- "Timing her mühendisin kabusu" → cliché, gerçek data ile değiştir
- "Doğru tool kullanmak her şeyi değiştirir" → belirsiz, spesifik tool+data ver

## Open Loops
- Bilmiyorum: Belirli OpenROAD versiyon numarası
- Tahmin etmem gerekiyor: Spesifik SKY130 library versiyonu

## Rubric Targets
- Saves reader a task: 2/2 — checklist formatında olacak
- Includes proof: 2/2 — SKY130 data kullanılacak
- Reusable takeaway: 2/2 — RTL timing checklist
- Specific audience: 2/2 — pipeline mühendisi net tanımlı
- Portable: 1/2 — tool-specific ama adım genel
- Strong visual: 1/2 — timing diagram açıklaması olacak

Target: 10/12
```

---

## Örnek 2: Single Post Brief

```markdown
# Writer Context Packet — openlane-tapeout-checklist
## Meta
- **Oluşturan:** hermes-agent
- **Tarih:** 2026-05-11
- **Rota:** ORIGINAL
- **Format:** Single Post (Memos Platformu)
- **Pilar:** Tape-out süreci

## Thesis
İlk OpenLane tape-out'tan önce kontrol edilmesi gereken 7 madde, 6 aylık iterasyon döngüsünü 2 haftaya kısaltır.

## Target Reader
RISC-V tasarımı yapıyor, ilk tape-out deneyimi yaklaşıyor. Karar vermesi gereken mühendis.

## Angle (Beklenmedik Çerçeve)
Tape-out checklist değil — tape-out öncesi "karar" checklist'i. Tool değil, karar noktaları.

## Proof Elements
- 6 ay → 2 hafta (kullanıcı hikayesi)
- 7 kontrol noktası (spesifik)
- Tool: OpenLane, Sky130

## Constraints
- Format: Single madde, en fazla 280 karakter
- Ton: Doğrudan, emir kipinde değil, öğretici
- Görsel: Yok (tek madde)

## Voice Anchors
"İlk tape-out deneyimim 6 ay sürdü. İki hafta değil. Bunu baştan bilseydim farklı bir mühendis olurdum."

## Risks
- Liste çok uzun → 7 madde hedef, aşma
- Her maddeyi açıkla → tek madde kısıtlaması

## Open Loops
- Yok

## Rubric Targets
Target: 8/12 (tek madde için yüksek hedef)
```

---

## Örnek 3: Detaylı Rapor Brief

```markdown
# Writer Context Packet — asic-design-tools-2026
## Meta
- **Oluşturan:** hermes-agent
- **Tarih:** 2026-05-11
- **Rota:** REPURPOSE
- **Kaynak:** ~/blog/asic-tools-comparison.md
- **Format:** Detaylı Rapor/PPT (10 slayt)
- **Pilar:** ASIC tasarım araçları

## Thesis
2026'da ASIC tasarımı için en iyi açık kaynak toolchain, maliyet ve öğrenme eğrisi açısından Sky130 + OpenROAD + OpenLane combination'ıdır.

## Target Reader
ASIC tasarımına başlayacak veya mevcut toolchain'ini değiştirmeyi düşünen mühendis.

## Angle (Beklenmedik Çerçeve)
Karşılaştırma tablosu değil — "hangi tool hangi aşamada kullanılır" workflow'u.

## Proof Elements
- Maliyet karşılaştırması (Synopsys vs açık kaynak)
- Learning curve dataları
- Kullanıcı sayıları (GitHub stars, commit frequency)

## Constraints
- Format: 10 slayt
- Her slayt: Başlık + 3-4 madde + görsel
- Ton: Profesyonel, karşılaştırmalı

## Rubric Targets
Target: 10/12
```
