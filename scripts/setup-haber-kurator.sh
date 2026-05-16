#!/bin/bash
#===============================================================================
# Haber Kuratör — V1 Kurulum Scripti
# Usage: ./setup-haber-kurator.sh [--interactive|--scaffold-only|--demo]
#
# Bu script iki modda çalışır:
#   --interactive  : Tüm dosyaları doldurur (tam kurulum, 1-2 saat)
#   --scaffold-only : Sadece klasör yapısını oluşturur (5 dakika)
#   --demo         : Demo içerikle doldurulmuş örnek sistem kurar
#   --wizard       : Adım adım interaktif kurulum sihirbazı
#
# Çıktı: ~/haber-kurator/ klasörü (veya $HABER_KURATOR_PATH varsa orası)
#===============================================================================

set -euo pipefail

# Renk kodları
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Config
HABER_KURATOR_PATH="${HABER_KURATOR_PATH:-$HOME/haber-kurator}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_REF_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

#-------------------------------------------------------------------------------
# Yardımcı fonksiyonlar
#-------------------------------------------------------------------------------

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()    { echo -e "\n${CYAN}${BOLD}▸ $1${NC}"; }

confirm() {
    local prompt="${1:-Devam?"
    local response
    read -p "$prompt [y/N] " response
    case "$response" in
        [yY]|[yY][eE][sS]) return 0 ;;
        *) return 1 ;;
    esac
}

ask() {
    local prompt="$1"
    local var_name="$2"
    local default="${3:-}"
    local response
    read -p "$prompt [$default]: " response
    response="${response:-$default}"
    eval "$var_name='$response'"
}

ask_multiline() {
    local prompt="$1"
    local var_name="$2"
    echo -e "\n${CYAN}$prompt${NC} (Bitirmek için boş satır + Enter)"
    echo -e "${YELLOW}(Çok satırlı giriş — bitirmek için boş satır)${NC}"
    local line
    local multiline=""
    while IFS= read -r line; do
        if [[ -z "$line" ]]; then break; fi
        multiline+="$line"$'\n'
    done
    # Sondaki yeni satırı kaldır
    multiline="${multiline%$'\n'}"
    eval "$var_name='$multiline'"
}

#-------------------------------------------------------------------------------
# Klasör yapısı oluşturma
#-------------------------------------------------------------------------------

create_scaffold() {
    log_step "Klasör yapısı oluşturuluyor..."

    local dirs=(
        "$HABER_KURATOR_PATH/strategy"
        "$HABER_KURATOR_PATH/voice"
        "$HABER_KURATOR_PATH/stores/ideas"
        "$HABER_KURATOR_PATH/stores/hooks"
        "$HABER_KURATOR_PATH/stores/proof"
        "$HABER_KURATOR_PATH/stores/feedback"
        "$HABER_KURATOR_PATH/runs/active"
        "$HABER_KURATOR_PATH/runs/archive"
        "$HABER_KURATOR_PATH/modules/writer/references/example-briefs"
        "$HABER_KURATOR_PATH/modules/writer/references/best-posts"
        "$HABER_KURATOR_PATH/modules/writer/templates"
        "$HABER_KURATOR_PATH/workflows"
    )

    for dir in "${dirs[@]}"; do
        mkdir -p "$dir"
        log_success "Oluşturuldu: ${dir#$HOME/}"
    done

    log_success "Tüm klasör yapısı hazır: $HABER_KURATOR_PATH"
}

#-------------------------------------------------------------------------------
# Strategy dosyalarını doldurma
#-------------------------------------------------------------------------------

fill_strategy() {
    log_step "Strategy dosyaları dolduruluyor..."

    # positioning.md
    echo -e "\n${BOLD}positioning.md — 3-5 satır${NC}"
    echo "Aşağıdaki formatı kullan:"
    echo "  'I help [WHO] do [WHAT] by [HOW].'"
    echo ""
    local positioning
    ask_multiline "positioning (ne yapıyorsunuz, kime, nasıl)" positioning
    cat > "$HABER_KURATOR_PATH/strategy/positioning.md" <<EOF
# Positioning

$positioning

---
*Otomatik oluşturuldu: $(date '+%Y-%m-%d')*
*Haber Kuratör v2 kurulum scripti tarafından*
EOF
    log_success "strategy/positioning.md yazıldı"

    # audience.md
    echo -e "\n${BOLD}audience.md — 3-5 satır${NC}"
    echo "Format: [Role] who [situation]. They want [goal] but [obstacle]."
    echo ""
    local audience
    ask_multiline "audience (hedef kitle, rol, durum, stake)" audience
    cat > "$HABER_KURATOR_PATH/strategy/audience.md" <<EOF
# Audience

$audience

---
*Otomatik oluşturuldu: $(date '+%Y-%m-%d')*
*Haber Kuratör v2 kurulum scripti tarafından*
EOF
    log_success "strategy/audience.md yazıldı"

    # pillars.md
    echo -e "\n${BOLD}pillars.md — 3-4 konu${NC}"
    echo "Format:"
    echo "## Pillar 1: [Name] — [why you have credibility]"
    echo "## Pillar 2: [Name] — [why you have credibility]"
    echo ""
    local pillars
    ask_multiline "pillars (konular, yetkinlik alanları)" pillars
    cat > "$HABER_KURATOR_PATH/strategy/pillars.md" <<EOF
# Content Pillars

$pillars

---
*Otomatik oluşturuldu: $(date '+%Y-%m-%d')*
*Haber Kuratör v2 kurulum scripti tarafından*

## Kullanım Kuralları
- İçerik üretimi SADECE bu pillar'larda yapılır
- Yeni bir pillar eklemek için mevcut üçü arasından birinin
  yerine veya en fazla dördüncü olarak eklenebilir
- Her yıl pillars.md gözden geçirilir
EOF
    log_success "strategy/pillars.md yazıldı"

    # source-watchlist.md
    cat > "$HABER_KURATOR_PATH/strategy/source-watchlist.md" <<EOF
# Source Watchlist

*Hedef kitle: $(cat "$HABER_KURATOR_PATH/strategy/audience.md" | head -3)*

## İzlenecek Kaynaklar

### Memos Platformu
@username1 — [neden izleniyor]
@username2 — [neden izleniyor]
@username3 — [neden izleniyor]

### RSS / Bloglar
- [URL] — [neden]
- [URL] — [neden]

### Podcast'ler
- [Podcast adı] — [bölüm/başlık] — [neden]

### Araçlar
- [Alet] — [kullanım amacı]

---
*Otomatik oluşturuldu: $(date '+%Y-%m-%d')*
*Araştırma yaparken bu kaynakları tarayın*
EOF
    log_success "strategy/source-watchlist.md yazıldı"
}

#-------------------------------------------------------------------------------
# Voice dosyalarını doldurma
#-------------------------------------------------------------------------------

fill_voice() {
    log_step "Voice dosyaları dolduruluyor..."

    # voice-profile.md
    echo -e "\n${BOLD}voice-profile.md — Üslup Profili${NC}"
    echo "Önce en iyi post'unuzdan 2-3 cümle yazın (ses örneği olarak):"
    echo ""
    local voice_sample
    ask_multiline "ses örneği (en iyi döneminden 2-3 cümle)" voice_sample

    cat > "$HABER_KURATOR_PATH/voice/voice-profile.md" <<EOF
# Voice Profile

## Ses Örneği (En İyi Dönemimden)
$voice_sample

---

## Üslup Kurallarım (Her Zaman Uygulanır)

1. **Kural:** _____________________________________________
   *Örnek:* _____________________________________________

2. **Kural:** _____________________________________________
   *Örnek:* _____________________________________________

3. **Kural:** _____________________________________________
   *Örnek:* _____________________________________________

4. **Kural:** _____________________________________________
   *Örnek:* _____________________________________________

5. **Kural:** _____________________________________________
   *Örnek:* _____________________________________________

---

## Yasaklı Kalıplarım (Asla Kullanılmaz)

1. _____________________________________________
   *Neden:* _____________________________________________

2. _____________________________________________
   *Neden:* _____________________________________________

3. _____________________________________________
   *Neden:* _____________________________________________

4. _____________________________________________
   *Neden:* _____________________________________________

5. _____________________________________________
   *Neden:* _____________________________________________

---

## Referans Post'larım (En İyi Örneklerim)

### Referans 1:
*[Post metni veya URL]*
*Neden en iyi örnek:* _____________________________________________

### Referans 2:
*[Post metni veya URL]*
*Neden en iyi örnek:* _____________________________________________

### Referans 3:
*[Post metni veya URL]*
*Neden en iyi örnek:* _____________________________________________

---
*Otomatik oluşturuldu: $(date '+%Y-%m-%d')*
*Haber Kuratör v2 kurulum scripti tarafından*
EOF
    log_success "voice/voice-profile.md yazıldı"

    # master-avoid-slop.md — Tier 1 başlangıç kalıpları
    cat > "$HABER_KURATOR_PATH/voice/master-avoid-slop.md" <<'EOF'
# Master Avoid-Slop Document

> 54 AI slop kalıbı, 3 şiddet seviyesi.
> Başlangıç: Tier 1 (8 kalıp). Her postmortem'den sonra güncellenir.
> Kaynak: Memos Küratörü (@memos) — Haber Kuratör

## Tier 1 — Kritik (Sıfır Tolerans)

| # | Kalıp | Tetikleyici | Örnek |
|---|-------|------------|-------|
| 1 | Promosyon dili | groundbreaking, game-changing, revolutionary | Somut sonuçla değiştir |
| 2 | Önem abartısı | pivotal moment, testament to | Spesifik gözlemle değiştir |
| 3 | Belirsiz atıf | experts believe, studies show | Kaynak belirt veya kaldır |
| 4 | Sahte etkinlik | the system compounds, the data tells us | Birinci tekil şahıs anlatıma geç |
| 5 | Retorik kurulum | The question is whether... | Doğrudan iddia ile değiştir |
| 6 | Staccato parçalama | no X. no Y. no Z. | Paragraf olarak yeniden yaz |
| 7 | Tire aşırı kullanımı | -- her yerde | Hedef: sıfır. Virgül/nokta ile değiştir |
| 8 | Dolgu zarfları | actually, literally, quietly | Çıkar veya güçlendirici olarak kullan |

## Tier 2 — Yüksek (Revize Et)

| # | Kalıp | Açıklama |
|---|-------|---------|
| 9 | Copula avoidance | "serves as", "stands as" → "is", "has" |
| 10 | -ing padding | Gereksiz -ing ile biten fiiller |
| 11 | Rule of three zorlama | Mecburen 3'e dayatılmış listeler |
| 12 | Filler phrases | "In order to" → "To", "Due to the fact that" → "Because" |
| 13 | Generic conclusions | "The future looks bright", "Exciting times ahead" |
| 14 | Signposting | "Let's dive in", "Here's what you need to know" |
| 15 | Hyperbolic quantifiers | every, all, always, never (abartılı kullanımda) |
| 16 | Hedging | "it could potentially", "it might be argued" |

## Tier 3 — Orta (Gözden Geçir)

| # | Kalıp | Açıklama |
|---|-------|---------|
| 17 | Passive voice | Özne gizlenmiş cümleler |
| 18 | Elegant variation | Aynı kavram 3+ farklı şekilde adlandırılmış |
| 19 | False ranges | "from X to Y" anlamsız ölçeklerde |
| 20 | Conjunction overuse | "and"/"but" ile aşırı başlayan cümleler |
| 21 | Unnecessary intensifiers | Very/So/Such gereksiz kullanımda |
| 22 | Paragraph-level vagueness | Her paragraf genel iddia, somut kanıt yok |
| 23 | Rhetorical questions as statements | Soru şeklinde açık cevap |

## Güncelleme Log'u

| Tarih | Eklenen Kalıp | Kaynak |
|-------|--------------|--------|
| *$(date '+%Y-%m-%d')* | *İlk kurulum* | *Setup script* |

---
*Otomatik oluşturuldu: $(date '+%Y-%m-%d')*
*Tam liste: references/avoid-slop-patterns.md*
EOF
    log_success "voice/master-avoid-slop.md yazıldı"
}

#-------------------------------------------------------------------------------
# Stores dosyalarını doldurma
#-------------------------------------------------------------------------------

fill_stores() {
    log_step "Stores dosyaları dolduruluyor..."

    # inbox.md
    cat > "$HABER_KURATOR_PATH/stores/inbox.md" <<EOF
# İçerik Fikirleri Inbox'ı

> Her fikir bu dosyada başlar. En az 10 fikir tut.
> Yarısı gerçek olmalı (DM, görüşme, deneyimden gelen).
> Her fikir: ### Fikir [N] + kaynak + tarih + notlar.

---

## Fikir 1 — [Kısa başlık]

- **Kaynak:** [DM / görüşme / makale / deneyim / vs.]
- **Tarih:** YYYY-MM-DD
- **Rota önerisi:** [ORIGINAL / REPURPOSE / REWRITE / RESEARCH+IDEATE]
- **Notlar:** _____________________________________________

---

## Fikir 2 — [Kısa başlık]

- **Kaynak:**
- **Tarih:**
- **Rota önerisi:**
- **Notlar:**

---

*(En az 8 fikir daha ekle — yarısı gerçek olmalı)*

EOF
    log_success "stores/inbox.md yazıldı"

    # workboard.md
    cat > "$HABER_KURATOR_PATH/stores/workboard.md" <<EOF
# Content Workboard

> Bu hafta/ay yapılacak içerik işleri.
> Her satır: [ ] [SLUG] — [Format] — [Pilar] — [Durum]

---

## Bu Hafta

- [ ] _____________________________________________ — ____________ — ____________ — [draft/verify/approved/scheduled]

---

## Gelecek Hafta (Planlı)

- [ ] _____________________________________________ — ____________ — ____________
- [ ] _____________________________________________ — ____________ — ____________

---

## Yapıldı (Bu Ay)

- [x] _____________________________________________ — ____________ — ____________
- [x] _____________________________________________ — ____________ — ____________

EOF
    log_success "stores/workboard.md yazıldı"

    # Proof bank — starter
    mkdir -p "$HABER_KURATOR_PATH/stores/proof"
    cat > "$HABER_KURATOR_PATH/stores/proof/_INDEX.md" <<EOF
# Proof Bank — Dizin

> Somut, doğrulanabilir kanıtlar. İçerik moat'un.
> En az 10 kanıt. Her ay en az 3 yeni kanıt ekle.

| # | Tip | İçerik | Kullanım Alanı |
|---|-----|--------|---------------|
| 1 | metric | *ekle* | *ekle* |
| 2 | project | *ekle* | *ekle* |
| 3 | person | *ekle* | *ekle* |
| 4 | method | *ekle* | *ekle* |
| 5 | tool | *ekle* | *ekle* |
| 6 | outcome | *ekle* | *ekle* |
| 7 | metric | *ekle* | *ekle* |
| 8 | project | *ekle* | *ekle* |
| 9 | person | *ekle* | *ekle* |
| 10 | outcome | *ekle* | *ekle* |

---

*Kurulum tarihi: $(date '+%Y-%m-%d')*
EOF
    log_success "stores/proof/ dizini oluşturuldu"

    # Hooks bank — starter
    mkdir -p "$HABER_KURATOR_PATH/stores/hooks"
    cat > "$HABER_KURATOR_PATH/stores/hooks/_INDEX.md" <<EOF
# Hook Bank — Dizin

> Dikkat çekici açılış koleksiyonu. Her postmortem'den sonra güncellenir.
> Format: Her hook = neden çalıştığının açıklamasıyla birlikte.

---

## Açılış Cümleleri

### Hook 1:
*[Hook metni]*
**Neden çalışıyor:** _____________________________________________
**Kullanıldığı post:** _____________________________________________

### Hook 2:
*[Hook metni]*
**Neden çalışıyor:**
**Kullanıldığı post:**

---

*(En az 10 hook ekle — en iyi performans gösteren post'lardan)*
EOF
    log_success "stores/hooks/ dizini oluşturuldu"

    # Feedback templates
    mkdir -p "$HABER_KURATOR_PATH/stores/feedback"
    cat > "$HABER_KURATOR_PATH/stores/feedback/24h-template.md" <<EOF
# 24h Feedback Template

**Post SLUG:**
**Yayınlanma:**
**Kontrol tarihi:**

## Metrikler
- Impressions:
- Okunmalar:
- Likes:
- Paylaşımlar:
- Replies:
- Okunma oranı: ___%

## İlk Gözlemler
- Beklentiler karşılandı mı?
- Sürpriz olan ne oldu?
- Hangi kısım en çok ilgi çekti?
EOF
    cat > "$HABER_KURATOR_PATH/stores/feedback/72h-template.md" <<EOF
# 72h Feedback Template

**Post SLUG:**
**Yayınlanma:**
**Kontrol tarihi:**

## Nihai Metrikler
- Impressions:
- Okunmalar:
- Likes:
- Paylaşımlar:
- Okunma oranı:

## Kalıcı Örüntüler

## Ses İçgörüleri

## Slop Tespiti (varsa)

## Öğrenilenler

## Sistem Güncellemeleri
- [ ] voice-profile.md güncellendi
- [ ] hooks/ eklendi
- [ ] master-avoid-slop.md güncellendi
EOF
    log_success "stores/feedback/ templates oluşturuldu"
}

#-------------------------------------------------------------------------------
# Modules ve workflows
#-------------------------------------------------------------------------------

fill_modules_workflows() {
    log_step "Modules ve workflows dolduruluyor..."

    # Writer SKILL.md
    cat > "$HABER_KURATOR_PATH/modules/writer/SKILL.md" <<EOF
# Writer Agent Skill

> Bu dosya, Writer Agent için referans dokümandır.
> Haber Kuratör v2 — Memos Küratörü (@memos) sisteminden uyarlanmıştır.

## Giriş Dosyaları (Her Zaman Önce Oku)

1. `brief.md` — Writer context packet (posta özel)
2. `voice-profile.md` — Üslup kuralları ve çapaları
3. `master-avoid-slop.md` — Kaçınılacak kalıplar

## Yazım Kuralları

- 400-900 token hedefli brief okunur
- Üslup kurallarına sıkı sıkıya uyulur
- Yasaklı kalıplar kontrol edilir
- Memos haber formatı hedeflenir

## Çıktı Formatı

`draft-package.md` — taslak + rubric_self_assessment + avoid_slop_pass + open_loops_flagged + voice_check

## Daha Fazla Bilgi

Tüm detaylar için: Haber Kuratör SKILL.md ve references/production-prompts.md
EOF
    log_success "modules/writer/SKILL.md yazıldı"

    # Workflows
    cat > "$HABER_KURATOR_PATH/workflows/README.md" <<EOF
# Haber Kuratör Workflows

> Her içerik objesi bu workflow'ları takip eder.

## Workflow Dosyaları

1. **idea-to-published-post.md** — 13 aşamalı ana playbook
2. **verifier-checklist.md** — Adım adım doğrulama kontrol listesi
3. **scheduler-handoff.md** — Planlayıcıya teslim prosedürü
4. **feedback-loop.md** — 24s/72s feedback mekanizması

## Hızlı Erişim

```
/haber audit    — Tüm run folder'ları kontrol et
/haber verify   — Taslak doğrulama
/haber feedback — Yayın sonrası analiz
```

## Daha Fazla Bilgi

Haber Kuratör SKILL.md — Ana doküman
references/production-prompts.md — 4 üretim prompt'u
references/avoid-slop-patterns.md — 54 slop kalıbı
EOF
    log_success "workflows/README.md yazıldı"
}

#-------------------------------------------------------------------------------
# Demo içerik oluşturma
#-------------------------------------------------------------------------------

fill_demo_content() {
    log_step "Demo içerik oluşturuluyor..."

    local demo_slug="2026-05-demo-memos"
    mkdir -p "$HABER_KURATOR_PATH/runs/active/$demo_slug"

    # haber-object.md
    cat > "$HABER_KURATOR_PATH/runs/active/$demo_slug/haber-object.md" <<EOF
# Haber Nesnesi — $demo_slug

## Meta
- **ID:** $demo_slug
- **Created:** $(date '+%Y-%m-%d')
- **Status:** captured
- **Format:** Bülten (8 madde)
- **Pilar:** [PILAR-1 — Doldurulacak]
- **Source:** demo (setup script)

## Lifecycle
- [ ] captured
- [ ] idea_review
- [ ] brief_ready
- [ ] drafting
- [ ] verification
- [ ] draft_review
- [ ] approved
- [ ] scheduler_ready
- [ ] scheduled
- [ ] published
- [ ] feedback_24h
- [ ] feedback_72h
- [ ] learned
EOF
    log_success "Demo run folder oluşturuldu: $demo_slug"
}

#-------------------------------------------------------------------------------
# README oluşturma
#-------------------------------------------------------------------------------

create_readme() {
    log_step "README oluşturuluyor..."

    cat > "$HABER_KURATOR_PATH/README.md" <<EOF
# Haber Kuratör v2 — AI-Augmented Haber Üretimi System

> Hermes Agent için uyarlanmış, AI destekli içerik üretim operasyonel sistemi.
> Kaynak: Memos Küratörü (@memos) — 5M impressions (2 hafta), 11M views + 100K okunmalar (2 ay).

## Hızlı Başlangıç

```bash
# 1. Haber Kuratör dizinine git
cd ~/haber-kurator

# 2. İçerik oluşturmaya başla
# (skill'teki komutları kullan)
```

## Komutlar

```
/haber new [idea]      — Yeni içerik objesi başlat
/haber brief [post]     — Brief oluştur
/haber draft [slug]     — Taslak üret
/haber verify [slug]    — Doğrula
/haber post [slug]      — Yayınla (memos-cli ile)
/haber feedback [slug]  — Feedback topla
/haber score [draft]    — Rubric puanla
/haber audit           — Sistem kontrolü
/haber setup            — Etkileşimli kurulum
/haber signal           — Sinyal taraması
```

## Dizin Yapısı

```
haber-kurator/
├── strategy/           — Positioning, audience, pillars
├── voice/              — Voice profile, avoid-slop
├── stores/             — Inbox, hooks, proof, feedback
├── runs/               — İçerik objeleri (her biri ayrı folder)
├── modules/writer/     — Writer agent referansları
└── workflows/          — 4 workflow playbook
```

## Önemli Dosyalar

| Dosya | Açıklama |
|-------|---------|
| \`strategy/positioning.md\` | Tek cümlelik pozisyonlama |
| \`voice/voice-profile.md\` | Üslup Profili (5 kural + 5 yasak) |
| \`voice/master-avoid-slop.md\` | 54 AI slop kalıbı |
| \`stores/inbox.md\` | Ham fikirler |
| \`stores/proof/_INDEX.md\` | Kanıt bankası |
| \`runs/active/{slug}/\` | Aktif içerik objeleri |

## Sistem İlkeleri

1. **Okunma = Birincil Metrik** — Beğeni değil, okunma.
2. **Sistem = Hızlandırıcı** — Otomasyon değil.
3. **Her taslak elle bitirilir** — AI draft üretir, insan onaylar.
4. **Proof = Moat'un** — Somut kanıtlar içerik moat'un oluşturur.
5. **Feedback her zaman toplanır** —闭环 = iyileşme.

## Daha Fazla Bilgi

- Ana doküman: \`SKILL.md\`
- Üretim prompt'ları: \`references/production-prompts.md\`
- Slop kalıpları: \`references/avoid-slop-patterns.md\`
- Rubric şablonu: \`references/rubric-template.md\`
- Workflow'lar: \`workflows/\`

---

*Kuruldu: $(date '+%Y-%m-%d')*
*Haber Kuratör v2 — Hermes Agent Plugin*
EOF
    log_success "README.md yazıldı"
}

#-------------------------------------------------------------------------------
# Interaktif kurulum sihirbazı
#-------------------------------------------------------------------------------

interactive_wizard() {
    echo -e "\n${BOLD}${CYAN}"
    echo "═══════════════════════════════════════════════════════════"
    echo "  Haber Kuratör v2 — Kurulum Sihirbazı"
    echo "═══════════════════════════════════════════════════════════"
    echo -e "${NC}"
    echo "Bu sihirbaz 1-2 saat sürecek tam kurulum yapar."
    echo "Her adımda açıklamalar ve örnekler verilecek."
    echo ""
    echo "İlk olarak bazı temel bilgileri alalım:"
    echo ""

    # Temel bilgiler
    ask "İçerik üretilecek platform(lar)" PLATFORMS "Memos Platformu"
    ask "Hedeflenen içerik hacmi (haftada kaç post?)" WEEKLY_TARGET "3"
    ask "Kullanılacak araçlar (örn: memos-cli, postiz, manuel)" TOOLS "memos-cli"

    echo ""
    log_info "Platform: $PLATFORMS | Haftalık hedef: $WEEKLY_TARGET post | Araçlar: $TOOLS"
    echo ""

    if ! confirm "Hazır mısın? Başlayalım!"; then
        log_warn "Kurulum iptal edildi."
        exit 0
    fi

    # Adım 1: Klasör yapısı
    echo ""
    create_scaffold

    # Adım 2: Strategy
    echo ""
    if confirm "Strategy dosyalarını şimdi doldurmak ister misin?"; then
        fill_strategy
    else
        log_warn "Strategy dosyaları boş bırakıldı. Sonra doldur."
    fi

    # Adım 3: Voice
    echo ""
    if confirm "Voice dosyalarını şimdi doldurmak ister misin?"; then
        fill_voice
    else
        log_warn "Voice dosyaları boş bırakıldı. Sonra doldur."
    fi

    # Adım 4: Stores
    echo ""
    if confirm "Stores dosyalarını şimdi doldurmak ister misin?"; then
        fill_stores
    else
        log_warn "Stores dosyaları boş bırakıldı. Sonra doldur."
    fi

    # Adım 5: Modules & Workflows
    echo ""
    fill_modules_workflows

    # Adım 6: Demo içerik
    echo ""
    if confirm "Demo içerik objesi oluşturalım mı?"; then
        fill_demo_content
    fi

    # Adım 7: README
    echo ""
    create_readme

    # Özet
    echo ""
    echo -e "${GREEN}${BOLD}"
    echo "═══════════════════════════════════════════════════════════"
    echo "  Kurulum Tamamlandı!"
    echo "═══════════════════════════════════════════════════════════"
    echo -e "${NC}"
    echo -e "📁 Haber Kuratör dizini: ${CYAN}$HABER_KURATOR_PATH${NC}"
    echo ""
    echo -e "Sonraki adımlar:"
    echo -e "  1. ${CYAN}cd $HABER_KURATOR_PATH${NC}"
    echo -e "  2. ${CYAN}strategy/positioning.md${NC} — Doldur (yapmadıysan)"
    echo -e "  3. ${CYAN}voice/voice-profile.md${NC} — Doldur (yapmadıysan)"
    echo -e "  4. ${CYAN}stores/inbox.md${NC} — En az 10 fikir ekle"
    echo -e "  5. İlk run folder'ı aç: ${CYAN}runs/active/2026-05-ilk-post/${NC}"
    echo -e "  6. ${CYAN}hermes-agent/haber-kurator skill${NC} — Skill'i yükle"
    echo ""
    echo -e "Kullanım:"
    echo -e "  ${CYAN}/haber new [fikir]${NC}  — İçerik üretmeye başla"
    echo -e "  ${CYAN}/haber audit${NC}          — Sistem kontrolü"
    echo ""
}

#-------------------------------------------------------------------------------
# Ana
#-------------------------------------------------------------------------------

main() {
    local mode="${1:-}"

    case "$mode" in
        --scaffold-only)
            log_info "Scaffold modu: Sadece klasör yapısı oluşturuluyor..."
            create_scaffold
            create_readme
            echo ""
            log_success "Tamamlandı: $HABER_KURATOR_PATH"
            ;;
        --demo)
            log_info "Demo modu: Klasör yapısı + demo içerik oluşturuluyor..."
            create_scaffold
            fill_stores
            fill_modules_workflows
            fill_demo_content
            create_readme
            echo ""
            log_success "Demo tamamlandı: $HABER_KURATOR_PATH"
            ;;
        --interactive|-i|"")
            interactive_wizard
            ;;
        --help|-h)
            echo "Usage: $0 [MODE]"
            echo ""
            echo "Modes:"
            echo "  --scaffold-only   Sadece klasör yapısı (5 dakika)"
            echo "  --demo            Demo içerikle birlikte"
            echo "  --interactive     Etkileşimli kurulum sihirbazı (1-2 saat)"
            echo "  --help, -h        Bu yardım mesajı"
            echo ""
            echo "Örnek:"
            echo "  $0 --scaffold-only              # Hızlı başlangıç"
            echo "  $0 --interactive               # Tam kurulum"
            ;;
        *)
            log_error "Bilinmeyen mod: $mode"
            echo "Use --help for usage information."
            exit 1
            ;;
    esac
}

main "$@"
