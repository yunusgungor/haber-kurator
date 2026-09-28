"""
Haber Kuratör — Scanner Module
=================================
ScannerMixin for HaberKuratorCore.

Handles: LLM generation (brief/draft/verifier), slop detection,
hallucination check, correction, audit, signal scanning,
pattern analysis, run analytics.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from haber_kurator.modules.models import (
    VERSION,
    SourceTier, VerificationLevel,
    SlopResult,
    CONFIG, ROUTE_VERIFIED, ROUTE_HIGH_SLOP, ROUTE_ESCALATED,
    STATE_ALIAS_MAP,
    HaberKuratorError, LLMError,
)

logger = logging.getLogger(__name__)

class ScannerMixin:
    """Mixin providing content generation, verification,
    slop detection, audit, and analysis capabilities."""

    async def generate_brief(self, slug: str, llm: Any = None,
                             extra_context: str = "") -> Dict[str, Any]:
        """Generate a Writer Context Packet (brief.md) using LLM.

        For news items, includes source attribution requirements.
        """
        run_path = self.active_runs / slug
        if not run_path.exists():
            return {"error": f"Run {slug} not found."}

        idea_path = run_path / "idea.md"
        context_path = run_path / "context.md"
        fact_check_path = run_path / "fact-check-report.md"

        idea = idea_path.read_text(encoding="utf-8") if idea_path.exists() else slug
        ctx = context_path.read_text(encoding="utf-8") if context_path.exists() else ""
        fact_check = fact_check_path.read_text(encoding="utf-8") if fact_check_path.exists() else ""

        voice_profile = self._get_voice_summary()
        slop_doc = ""
        slop_path = self.voice / "master-avoid-slop.md"
        if slop_path.exists():
            slop_doc = slop_path.read_text(encoding="utf-8")[:500]

        route = "VERIFIED"
        rm = re.search(r'Route:\s*(.+)', idea, re.IGNORECASE)
        if rm:
            route = rm.group(1).strip()

        # Determine if this is a news item requiring source attribution
        is_verified_news = route == "VERIFIED"

        source_attribution_section = ""
        if is_verified_news and fact_check:
            source_attribution_section = f"""
## Source Attribution Requirements (MANDATORY)
This is a VERIFIED NEWS item. Every factual claim MUST include:
1. The specific source(s) that reported it (Source: Reuters, AP, etc.)
2. A direct link to the source article where available
3. The credibility tier of the source

Rules:
- NEVER use vague attribution ("according to reports", "sources say")
- NEVER fabricate facts — only use information from the verified sources
- If a claim cannot be attributed to a specific source, FLAG IT as unverified
- End with a clear "Sources:" section listing all cited articles

## Cross-Verification Report (from fact-check)
{fact_check}
"""
        prompt = f"""You are writing a Writer Context Packet (brief.md) for a news content post.
Target 400-900 tokens. Be specific. Every field must be filled from available context.

ROUTE: {route}

INPUT FILES:
1. Idea + Route Decision:
{idea}

2. Context (Stores, Proof, Voice):
{ctx}

3. Voice Profile Summary:
{voice_profile}

4. Slop Patterns (abridged):
{slop_doc}

{source_attribution_section}

{extra_context}

OUTPUT — produce a complete brief.md with EXACTLY this structure:

```markdown
# Writer Context Packet — {{SLUG}}
## Meta
- **Route:** {{ROUTE}}
- **Format:** Haber Bülteni
- **Pillar:** {{pillar}}
- **Target Date:** {{optional}}

## Thesis
ONE sentence — what fact does this news deliver?

## Target Reader
ONE specific person who needs this news.

## Key Facts
- Fact 1 with source attribution
- Fact 2 with source attribution
- (every fact must cite its source)

## Angle
What makes this news item noteworthy?

## Source List
- Source 1 (Tier): URL
- Source 2 (Tier): URL

## Constraints
- News format: [Özet] - [Detaylar] - [Kaynak]
- Tone: objective, factual
- No commentary, no analysis — just the facts
- Every claim = source citation

## Risks
- False balance: don't invent opposing views
- Speculation: don't predict outcomes
- Vague sourcing: always name the source

## Rubric Targets
- [ ] Tarafsızlık (Objectivity) → target: 2/2
- [ ] Kaynak Gösterimi (Sourcing) → target: 2/2
- [ ] Kısalık ve Netlik (Brevity) → target: 2/2
- [ ] Bilgi Yoğunluğu (Fact Density) → target: 2/2
- [ ] Clickbait Uzaklığı → target: 2/2
- [ ] Format Yapısı (Structure) → target: 2/2
Target total: 12/12
```

Return ONLY the markdown brief. No extra commentary."""

        try:
            if llm and hasattr(llm, "acomplete"):
                response = await llm.acomplete([
                    {"role": "system", "content": "You are an expert news editor who writes tight, sourced briefs."},
                    {"role": "user", "content": prompt},
                ])
                text = response.text
            else:
                try:
                    from agent.auxiliary_client import async_call_llm
                except ImportError as _ie:
                    raise RuntimeError(
                        "Hermes LLM unavailable outside agent context. "
                        "Use '/haber brief <slug>' via Hermes agent instead."
                    ) from _ie
                messages = [
                    {"role": "system", "content": "You are an expert news editor."},
                    {"role": "user", "content": prompt},
                ]
                raw = await async_call_llm(task="curator", messages=messages)
                try:
                    text = raw.choices[0].message.content
                except (AttributeError, IndexError):
                    text = str(raw)

            text = text.strip()
            if text.startswith("```"):
                text = re.sub(r"^```\w*\n?", "", text)
                text = re.sub(r"\n```$", "", text)

            brief_path = run_path / "brief.md"
            brief_path.write_text(text, encoding="utf-8")
            # Brief ready — advance to verified if not already past that stage
            current = self.get_state(slug)
            if current not in ("verified", "published", "corrected"):
                self.update_state(slug, "verified")

            return {"slug": slug, "status": "verified", "length": len(text)}

        except Exception as e:
            return {"error": f"Brief generation failed: {str(e)}"}


    async def generate_draft(self, slug: str, llm: Any = None) -> Dict[str, Any]:
        """Generate draft-package.md using the Writer Agent with source enforcement.

        For VERIFIED news: ALL facts must be traceable to sources in the brief.
        Hallucination guard: LLM is instructed to ONLY use facts from sources.
        """
        run_path = self.active_runs / slug
        if not run_path.exists():
            return {"error": f"Run {slug} not found."}

        brief_path = run_path / "brief.md"
        if not brief_path.exists():
            return {"error": "No brief.md found."}

        brief = brief_path.read_text(encoding="utf-8")
        fact_check_path = run_path / "fact-check-report.md"
        fact_check = fact_check_path.read_text(encoding="utf-8") if fact_check_path.exists() else ""

        voice_profile = ""
        vp_path = self.voice / "voice-profile.md"
        if vp_path.exists():
            voice_profile = vp_path.read_text(encoding="utf-8")

        slop_doc = ""
        slop_path = self.voice / "master-avoid-slop.md"
        if slop_path.exists():
            slop_doc = slop_path.read_text(encoding="utf-8")[:1500]

        proof = self._get_relevant_proof(brief)
        hooks = self._get_successful_hooks()

        # Determine route
        route = "VERIFIED"
        rm = re.search(r'\*{0,2}Route\*{0,2}:\*{0,2}\s*(.+)', brief, re.IGNORECASE)
        if rm:
            route = rm.group(1).strip().lstrip('* ')

        is_verified_news = route == "VERIFIED"

        # Hallucination guard section for news
        hallucination_guard = ""
        if is_verified_news:
            hallucination_guard = """
## ⚠️ HALLUCINATION GUARD — CRITICAL INSTRUCTIONS
You are writing NEWS. Every single fact, number, name, and date MUST come from
the sources listed in the brief.md. You MUST NOT:

❌ Invent facts not present in the source materials
❌ Add analysis, commentary, or opinions
❌ Speculate about future outcomes
❌ Use phrases like "this could mean" or "experts believe"
❌ Create quotes that weren't in the source articles
❌ Add statistics without source attribution

✅ DO:
- Restate facts from the verified sources in your own words
- Attribute every factual claim: "Source: Reuters reports..."
- Use the [Özet] - [Detaylar] - [Kaynak] structure
- End with a "Sources:" section listing all URLs

If a source article mentions a specific number, you may use it WITH the source name.
If you are unsure about any fact, FLAG IT in open_loops_flagged — do NOT guess.
"""

        prompt = f"""ROLE
You are a Writer Agent for a News Curation platform. You produce objective,
factual news summaries from verified sources. Every claim MUST cite its source.
No fabrication. No speculation.

INPUT FILES:

## FILE 1: brief.md (Writer Context Packet)
{brief}

## FILE 2: voice-profile.md (Voice Rules)
{voice_profile}

## FILE 3: master-avoid-slop.md (Banned Patterns)
{slop_doc}

## FILE 4: Cross-Verification Report
{fact_check}

{hallucination_guard}

## Optional: Proof Bank
{proof}

## Optional: Successful Hooks
{hooks}

TASK
1. Read all input files carefully — ESPECIALLY THE SOURCE LIST
2. Internalize the hallucination guard rules
3. Internalize voice rules and banned patterns
4. Draft content following the [Özet] - [Detaylar] - [Kaynak] news format
5. Every factual claim MUST include the source name
6. After drafting, verify EVERY claim in your draft has a source in the brief
7. Flag any open loop (things you had to guess)

OUTPUT — produce a complete draft-package.md:

```
---
draft:
[News content in [Özet] - [Detaylar] - [Kaynak] format]

rubric_self_assessment:
- Tarafsızlık (Objectivity): [0/1/2] — [evidence]
- Kaynak Gösterimi (Sourcing): [0/1/2] — [evidence]
- Kısalık ve Netlik (Brevity): [0/1/2] — [evidence]
- Bilgi Yoğunluğu (Fact Density): [0/1/2] — [evidence]
- Clickbait Uzaklığı: [0/1/2] — [evidence]
- Format Yapısı (Structure): [0/1/2] — [evidence]
- TOTAL: [X/12]

avoid_slop_pass:
- [ ] LINE [N]: "[exact phrase]" — [pattern name] — [rewrite suggestion]
- (empty if clean)

open_loops_flagged:
- [specific fact I had to guess — CRITICAL for news accuracy]
- (empty if all facts sourced)

voice_check:
- All voice rules followed: [yes/no]
  - Rule 1: [followed / violated]
  - Rule 2: [followed / violated]
  - Rule 3: [followed / violated]
  - Rule 4: [followed / violated]
  - Rule 5: [followed / violated]

source_attribution_check:
- Every claim has a source: [yes/no]
- All sources from approved list: [yes/no]
- Number of unsourced claims: [N]
- Open loops that need fact-checking: [list]
```

QUALITY GATES:
- [ ] Every claim has a source citation
- [ ] No hallucinated/speculative content
- [ ] Voice rules followed
- [ ] Slop patterns avoided
- [ ] Format matches news brief specification
- [ ] [Özet] - [Detaylar] - [Kaynak] structure used"""

        try:
            if llm and hasattr(llm, "acomplete"):
                response = await llm.acomplete([
                    {"role": "system", "content": "You are a Writer Agent for Haber Kuratör News. You produce ONLY source-attributed factual news. Hallucination = system failure."},
                    {"role": "user", "content": prompt},
                ])
                text = response.text
            else:
                try:
                    from agent.auxiliary_client import async_call_llm
                except ImportError as _ie:
                    raise RuntimeError(
                        "Hermes LLM unavailable outside agent context. "
                        "Use '/haber draft <slug>' via Hermes agent instead."
                    ) from _ie
                messages = [
                    {"role": "system", "content": "You are a Writer Agent for Haber Kuratör News. Source-attributed factual news only."},
                    {"role": "user", "content": prompt},
                ]
                raw = await async_call_llm(task="writer", messages=messages)
                try:
                    text = raw.choices[0].message.content
                except (AttributeError, IndexError):
                    text = str(raw)

            text = text.strip()
            if text.startswith("```"):
                text = re.sub(r"^```\w*\n?", "", text)
                text = re.sub(r"\n```$", "", text)

            draft_path = run_path / "draft-package.md"
            draft_path.write_text(text, encoding="utf-8")
            # Draft hazırlandı — state cross_verified olarak kalır
            return {"slug": slug, "status": "drafted", "length": len(text)}

        except Exception as e:
            return {"error": f"Draft generation failed: {str(e)}"}

    # ══════════════════════════════════════════════════════════
    # 10. VERIFIER AGENT (Updated for Source Verification)
    # ══════════════════════════════════════════════════════════

    # ══════════════════════════════════════════════════════════

    async def run_verifier(self, slug: str, llm: Any = None) -> Dict[str, Any]:
        """Run Verifier Agent with source attribution checking."""
        run_path = self.active_runs / slug
        if not run_path.exists():
            return {"error": f"Run {slug} not found."}

        draft_path = run_path / "draft-package.md"
        brief_path = run_path / "brief.md"
        fact_check_path = run_path / "fact-check-report.md"

        if not draft_path.exists():
            return {"error": "No draft-package.md found."}

        draft = draft_path.read_text(encoding="utf-8")
        brief = brief_path.read_text(encoding="utf-8") if brief_path.exists() else ""
        fact_check = fact_check_path.read_text(encoding="utf-8") if fact_check_path.exists() else ""
        slop_doc = ""
        slop_path = self.voice / "master-avoid-slop.md"
        if slop_path.exists():
            slop_doc = slop_path.read_text(encoding="utf-8")[:2000]

        prompt = f"""ROLE
You are a Verifier Agent for a News Curation platform. You check drafts
for factual accuracy, source attribution, and journalistic standards.

Your PRIMARY job: catch HALLUCINATIONS — claims not supported by sources.
Your SECONDARY job: catch slop, voice violations, and rubric gaps.

INPUT FILES:

## FILE 1: brief.md (What was supposed to be written)
{brief}

## FILE 2: draft-package.md (What was written)
{draft}

## FILE 3: Cross-Verification Report (Verified facts)
{fact_check}

## FILE 4: master-avoid-slop.md (Banned patterns)
{slop_doc}

TASK — Two-phase verification:

PHASE 1: SOURCE ATTRIBUTION CHECK (CRITICAL)
- Does every factual claim in the draft cite a specific source?
- Are all cited sources from the approved list in the brief?
- Are there ANY claims that appear to be hallucinated (not in the source materials)?
- Check for: fake statistics, made-up quotes, invented names/dates, unverified numbers

PHASE 2: QUALITY CHECK
- Rubric scoring (0-12)
- Slop pattern detection
- Voice rule compliance

OUTPUT — produce verifier-report.md:

```
---
## source_attribution_audit
**Hallucination scan:**
- Claims with proper source: [N]
- Claims without source: [N]
- Potentially hallucinated claims: [list each with line number and reason]
- Sources used but not in brief: [list]
- All sources from approved list: [yes/no]

**Source chain integrity:**
- Every fact maps back to a source: [yes/partial/no]
- Appropriate source tiers used: [yes/no]

## brief_check
- Thesis delivered: [yes/partial/no] — [evidence]
- Constraints met: [yes/partial/no] — [evidence]
- News format followed ([Özet]-[Detaylar]-[Kaynak]): [yes/partial/no]

## rubric_scoring
- Tarafsızlık (Objectivity): [0/1/2] — [evidence]
- Kaynak Gösterimi (Sourcing): [0/1/2] — [evidence]
- Kısalık ve Netlik (Brevity): [0/1/2] — [evidence]
- Bilgi Yoğunluğu (Fact Density): [0/1/2] — [evidence]
- Clickbait Uzaklığı: [0/1/2] — [evidence]
- Format Yapısı (Structure): [0/1/2] — [evidence]
- TOTAL: [X/12]
- PASSES_THRESHOLD (8/12): [yes/no]

## avoid_slop_findings
TIER 1 — Critical:
- [ ] LINE [N]: "[phrase]" — [pattern]
TIER 2 — High:
- [ ] LINE [N]: "[phrase]" — [pattern]
TIER 3 — Medium:
- [ ] LINE [N]: "[phrase]" — [pattern]

## VERDICT
- [APPROVE] — All claims sourced, rubric ≥8/12, minor slop only
- [REVISE] — Some claims need source fixes or rubric close but under
- [REJECT] — Hallucinated claims OR rubric <6/12

## required_fixes
1. [Line N]: [specific fix — especially source issues]
2. [Line M]: [specific fix]

## hallucination_detail
For each potentially hallucinated claim:
1. Claim: "[exact text]"
   Line: [N]
   Evidence it's hallucinated: [explain why this isn't in sources]
   Source check: [what the fact-check report actually says]
   Suggested fix: [how to fix — add source or remove claim]
```

CRITICAL RULES:
- If ANY claim appears hallucinated → REJECT
- If ANY source is cited but NOT in the approved list → FLAG
- Every rubric score needs specific quote evidence
- Generic feedback is REJECTED"""

        try:
            if llm and hasattr(llm, "acomplete"):
                response = await llm.acomplete([
                    {"role": "system", "content": "You are a strict Verifier Agent for Haber Kuratör News. Hallucination detection is your primary job."},
                    {"role": "user", "content": prompt},
                ])
                text = response.text
            else:
                try:
                    from agent.auxiliary_client import async_call_llm
                except ImportError as _ie:
                    raise RuntimeError(
                        "Hermes LLM unavailable outside agent context. "
                        "Use '/haber verify <slug>' via Hermes agent instead."
                    ) from _ie
                messages = [
                    {"role": "system", "content": "You are a strict Verifier Agent for Haber Kuratör News."},
                    {"role": "user", "content": prompt},
                ]
                raw = await async_call_llm(task="curator", messages=messages)
                try:
                    text = raw.choices[0].message.content
                except (AttributeError, IndexError):
                    text = str(raw)

            text = text.strip()
            if text.startswith("```"):
                text = re.sub(r"^```\w*\n?", "", text)
                text = re.sub(r"\n```$", "", text)

            report_path = run_path / "verifier-report.md"
            report_path.write_text(text, encoding="utf-8")

            return {"slug": slug, "status": "verified", "length": len(text)}

        except Exception as e:
            return {"error": f"Verification failed: {str(e)}"}

    # ══════════════════════════════════════════════════════════
    # 11. HALLUCINATION GUARD — Automated Claim Verification
    # ══════════════════════════════════════════════════════════

    # ══════════════════════════════════════════════════════════

    def hallucination_check(self, slug: str) -> Dict[str, Any]:
        """Automated hallucination detection using regex patterns.

        Checks draft for claims that might not be sourced:
        - Statistics without source attribution
        - Quotes without attribution
        - Specific numbers/dates without source context
        - Speculative language
        """
        run_path = self.active_runs / slug
        draft_path = run_path / "draft-package.md"

        if not draft_path.exists():
            return {"error": "No draft found."}

        draft = draft_path.read_text(encoding="utf-8")

        # Skip rubric_self_assessment and similar metadata sections
        draft_main = re.split(r'\nrubric_self_assessment|\n---\nrubric_|\nvoice_check|\navoid_slop_pass|open_loops_flagged', draft)[0]

        findings = []

        # Pattern 1: Numbers/statistics without nearby source name (scan main content only)
        number_claims = re.finditer(r'(?:\$?\d+[\.\d,]*\s*(?:million|billion|trillion|percent|%|people|dollars|euros)?)', draft_main)
        for match in number_claims:
            num_text = match.group(0)

            # Skip numbers that are part of URLs (false positive prevention)
            line_start = draft_main.rfind('\n', 0, match.start()) + 1
            line_end = draft_main.find('\n', match.end())
            if line_end == -1:
                line_end = len(draft_main)
            line_text = draft_main[line_start:line_end]
            # If the line contains a URL pattern, skip numbers in that line
            if re.search(r'https?://\S*', line_text):
                continue

            start = max(0, match.start() - 200)
            end = min(len(draft), match.end() + 200)
            context = draft[start:end]

            # Check if a source name appears within 200 chars
            source_in_context = any(
                src in context
                for src in ["Reuters", "AP", "AFP", "Bloomberg", "BBC", "WSJ", "FT",
                           "Guardian", "NYT", "Washington Post", "Al Jazeera",
                           "Anadolu Ajansı", "AA", "BBC Türkçe", "Euronews",
                           "Deutsche Welle", "DW", "Bloomberg HT", "T24",
                           "Medyascope", "Duvar", "Diken", "BirGün", "Sözcü",
                           "Cumhuriyet", "Hürriyet", "Webrazzi",
                           "Source:", "Kaynak:", "kaynak", "reports", "according to",
                           "bildirdi", "açıkladı", "duyurdu", "belirtti", "göre"]
            )
            if not source_in_context:
                findings.append({
                    "type": "unsourced_statistic",
                    "text": num_text.strip()[:80],
                    "position": match.start(),
                    "severity": "high",
                    "message": f"Number/statistic without clear source attribution within 200 chars",
                })

        # Pattern 2: Speculative language
        speculative_patterns = [
            r"could (?:mean|lead to|result in|become)",
            r"might indicate",
            r"may suggest",
            r"raises questions",
            r"it remains to be seen",
            r"only time will tell",
            r"could potentially",
        ]
        for pat in speculative_patterns:
            for match in re.finditer(pat, draft_main, re.IGNORECASE):
                findings.append({
                    "type": "speculation",
                    "text": match.group(0),
                    "position": match.start(),
                    "severity": "medium",
                    "message": "Speculative language — not appropriate for verified news",
                })

        # Pattern 3: Quotes without attribution (scan main content only)
        quote_claims = re.finditer(r'"([^"]{8,})"', draft_main)
        for match in quote_claims:
            start = max(0, match.start() - 150)
            context = draft_main[start:match.end() + 50]
            has_attribution = any(
                word in context.lower()
                for word in ["said", "told", "according to", "stated", "reported",
                            "says", "added", "noted", "explained", "wrote",
                            "dedi", "belirtti", "açıkladı", "bildirdi", "duyurdu",
                            "söyledi", "ifade etti", "vurguladı", "kaydetti",
                            "sözleriyle", "tanımladı", "nitelendirdi"]
            )
            if not has_attribution:
                findings.append({
                    "type": "floating_quote",
                    "text": match.group(1)[:80],
                    "position": match.start(),
                    "severity": "high",
                    "message": "Quote without speaker attribution",
                })

        # Pattern 4: Unverified claims
        unverified_markers = [
            r"it is believed that",
            r"many think that",
            r"some argue that",
            r"critics say",
            r"supporters say",
        ]
        for pat in unverified_markers:
            for match in re.finditer(pat, draft, re.IGNORECASE):
                findings.append({
                    "type": "unverified_claim",
                    "text": match.group(0),
                    "position": match.start(),
                    "severity": "high",
                    "message": "Vague attribution — who exactly said this?",
                })

        result = {
            "slug": slug,
            "total_findings": len(findings),
            "high_severity": len([f for f in findings if f["severity"] == "high"]),
            "medium_severity": len([f for f in findings if f["severity"] == "medium"]),
            "findings": findings[:20],  # Cap at 20 findings
            "pass": len([f for f in findings if f["severity"] == "high"]) == 0,
        }

        return result

    # ══════════════════════════════════════════════════════════
    # 12. CORRECTION WORKFLOW (New for v3.0)
    # ══════════════════════════════════════════════════════════

    # ══════════════════════════════════════════════════════════

    def issue_correction(self, slug: str, error_description: str,
                         correct_information: str, retract: bool = False) -> str:
        """Issue a correction or retraction for a published news item.

        Args:
            slug: The run slug
            error_description: What was wrong
            correct_information: What the correct fact is
            retract: True if the entire story should be retracted

        Returns:
            Status message
        """
        run_path = self.active_runs / slug
        if not run_path.exists():
            # Check archive
            run_path = self.archive / slug
            if not run_path.exists():
                return f"❌ Run {slug} not found in active or archive."

        current_state = self.get_state(slug)
        if current_state not in ("published", "corrected"):
            return f"❌ Cannot issue correction in state '{current_state}'. Must be published first."

        # Write correction file
        corr_content = f"""# Correction Notice — {slug}

**Date:** {datetime.now().isoformat()}
**Type:** {"RETRACTION" if retract else "CORRECTION"}
**Original State:** {current_state}

## Error Description
{error_description}

## Correct Information
{correct_information}

## Impact
{"This story has been retracted due to factual inaccuracies." if retract else "The error has been corrected. See updated version below."}

## Updated Content
---
"""

        if retract:
            corr_content += """
## Retraction Statement
We have retracted this story. The information could not be verified
to our editorial standards. We apologize for the error.

**Status:** RETRACTED
"""
        else:
            corr_content += """
## Correction
The error has been corrected. We maintain our commitment to factual accuracy.

**Status:** CORRECTED
"""

        (run_path / "correction.md").write_text(corr_content, encoding="utf-8")

        # Update state — both correction and retraction map to corrected
        self.update_state(slug, "corrected", force=True)
        return f"✅ {'Retraction' if retract else 'Correction'} issued for {slug}. State: corrected."


    def check_correction_needed(self, slug: str) -> str:
        """Check if a published run has known issues requiring correction."""
        run_path = self.active_runs / slug
        if not run_path.exists():
            return f"Run {slug} not found."

        # Look for user feedback with error reports
        feedback_path = run_path / "feedback.md"
        if feedback_path.exists():
            content = feedback_path.read_text(encoding="utf-8").lower()
            error_indicators = ["wrong", "incorrect", "hatalı", "yanlış", "error",
                                "false", "inaccurate", "yanlış bilgi", "düzeltme"]
            found = [ind for ind in error_indicators if ind in content]
            if found:
                return f"⚠️ Potential errors flagged in feedback: {', '.join(found)}. Run '/haber correct {slug}' to issue correction."

        return f"✅ No correction indicators found for {slug}."

    # ══════════════════════════════════════════════════════════
    # 13. LEGACY: ORIGINAL METHODS (Preserved)
    # ══════════════════════════════════════════════════════════

    # --- Slop Detection ---


    def scan_slop(self, text: str) -> Dict[str, Any]:
        """Full slop detection across all tiers (preserved)."""
        logger.info("scan_slop called with text length=%d", len(text))
        findings_t1 = []
        findings_t2 = []
        findings_t3 = []
        findings_bonus = []

        for p in self.slop_tier1:
            if re.search(p, text, re.IGNORECASE):
                findings_t1.append(p)
        for p in self.slop_tier2:
            if re.search(p, text, re.IGNORECASE):
                findings_t2.append(p)
        for p in self.slop_tier3:
            if re.search(p, text, re.IGNORECASE):
                findings_t3.append(p)
        for p in self.slop_bonus:
            if re.search(p, text, re.IGNORECASE):
                findings_bonus.append(p)

        t1 = len(findings_t1)
        t2 = len(findings_t2)
        t3 = len(findings_t3)
        tb = len(findings_bonus)

        if t1 >= 3 or t2 >= 5 or t3 >= 15:
            score = "REJECT"
        elif t1 >= 1 or t2 >= 3 or t3 >= 8:
            score = "REVISE"
        else:
            score = "PASS"

        return {
            "score": score,
            "tier1_count": t1,
            "tier2_count": t2,
            "tier3_count": t3,
            "bonus_count": tb,
            "findings": findings_t1 + findings_t2 + findings_t3 + findings_bonus,
            "findings_tier1": findings_t1[:10],
            "findings_tier2": findings_t2[:10],
            "findings_tier3": findings_t3[:15],
            "findings_bonus": findings_bonus[:5],
            "all_findings": findings_t1 + findings_t2 + findings_t3 + findings_bonus,
        }

    # --- Rubric Evaluation ---


    async def evaluate_rubric(self, slug: str, llm: Any = None) -> Dict[str, Any]:
        """12-point rubric evaluation (preserved)."""
        run_path = self.active_runs / slug
        draft_path = run_path / "draft-package.md"
        if not draft_path.exists():
            return {"error": f"Draft not found for {slug}"}

        content = draft_path.read_text(encoding="utf-8")
        prompt = f"""Audit this news content against our 12-point News Rubric:

{content}

Score each criterion 0 (fails), 1 (partial), or 2 (meets fully).
Threshold to pass: 8/12.

Return EXACTLY valid JSON:
{{
  "scores": {{
    "tarafsizlik": 0-2,
    "kaynak_gosterimi": 0-2,
    "kisalik_netlik": 0-2,
    "bilgi_yogunlugu": 0-2,
    "clickbait_uzakligi": 0-2,
    "format_yapisi": 0-2
  }},
  "summary": "string assessment with specific evidence",
  "total": 0-12,
  "passes": true/false,
  "lowest_scores": ["criterion1", "criterion2"]
}}"""

        try:
            if llm and hasattr(llm, "acomplete"):
                response = await llm.acomplete([
                    {"role": "system", "content": "You are a strict news editor scoring against a rubric."},
                    {"role": "user", "content": prompt},
                ])
                text = response.text
            else:
                try:
                    from agent.auxiliary_client import async_call_llm
                except ImportError as _ie:
                    raise RuntimeError(
                        "Hermes LLM unavailable outside agent context. "
                        "Use '/haber score <slug>' via Hermes agent instead."
                    ) from _ie
                messages = [
                    {"role": "system", "content": "You are a strict news editor."},
                    {"role": "user", "content": prompt},
                ]
                raw = await async_call_llm(task="curator", messages=messages)
                try:
                    text = raw.choices[0].message.content
                except (AttributeError, IndexError):
                    text = str(raw)

            json_match = re.search(r"(\{.*\})", text, re.DOTALL)
            if json_match:
                res = json.loads(json_match.group(1))
            else:
                res = {"scores": {}, "summary": f"Failed to parse: {text[:200]}",
                       "total": 0, "passes": False}

            if "total" not in res or not res["total"]:
                res["total"] = sum(res.get("scores", {}).values())
            res["passes"] = res.get("total", 0) >= 8
            return res

        except Exception as e:
            return {"error": str(e)}

    # --- Postmortem ---


    async def run_postmortem(self, slug: str, metrics: Dict[str, Any] = None,
                             llm: Any = None) -> Dict[str, Any]:
        """LLM-based postmortem analysis for a published run.

        Writes feedback.md but stays in current lifecycle state — does NOT
        attempt invalid state transitions (postmortem is an advisory pass).
        """
        run_path = self.active_runs / slug
        if not run_path.exists():
            return {"error": f"Run {slug} not found."}

        draft_path = run_path / "draft-package.md"
        if not draft_path.exists():
            return {"error": "Draft not found for postmortem."}

        draft_content = draft_path.read_text(encoding="utf-8")

        if not metrics:
            metrics = {
                "impressions": 0, "engagements": 0,
                "likes": 0, "paylasimlar": 0,
                "okunma": 0, "replies": 0,
            }

        prompt = f"""You are running a POSTMORTEM on a published news article.

CONTEXT:
POST SLUG: {slug}
METRICS: {json.dumps(metrics, indent=2)}

PUBLISHED DRAFT:
---
{draft_content}
---

TASK — Analyze:

1. WHAT DROVE THE OKUNMA SAYISI?
   Quote the exact factual content readers valued.

2. WHAT DROVE ENGAGEMENT?
   What specific aspects drove likes/shares?

3. SOURCE ACCURACY CHECK
   Were all cited sources correct?
   Any reader feedback about factual errors?

4. WHAT WOULD YOU CHANGE?
   One factual improvement if doing again.

5. WHAT PATTERN TO CAPTURE?

Return as markdown:
---
## what_drove_okunma
...
## what_drove_engagement
...
## source_accuracy_check
...
## what_would_i_change
...
## pattern_to_capture
..."""

        try:
            if llm and hasattr(llm, "acomplete"):
                response = await llm.acomplete([
                    {"role": "system", "content": "You are a news content analyst."},
                    {"role": "user", "content": prompt},
                ])
                text = response.text
            else:
                try:
                    from agent.auxiliary_client import async_call_llm
                except ImportError as _ie:
                    raise RuntimeError(
                        "Hermes LLM unavailable outside agent context."
                    ) from _ie
                messages = [
                    {"role": "system", "content": "You are a news content analyst."},
                    {"role": "user", "content": prompt},
                ]
                raw = await async_call_llm(task="curator", messages=messages)
                try:
                    text = raw.choices[0].message.content
                except (AttributeError, IndexError):
                    text = str(raw)

            text = text.strip()
            if text.startswith("```"):
                text = re.sub(r"^```\w*\n?", "", text)
                text = re.sub(r"\n```$", "", text)

            feedback_path = run_path / "feedback.md"
            existing = ""
            if feedback_path.exists():
                existing = feedback_path.read_text(encoding="utf-8") + "\n\n---\n\n"

            okunma_rate = (
                metrics.get("okunma", 0) / max(metrics.get("impressions", 1), 1) * 100
            )

            feedback_content = f"""{existing}# Postmortem — {slug}

**Date:** {datetime.now().isoformat()}
**Metrics:** {json.dumps(metrics, indent=2)}
**Okunma Rate:** {okunma_rate:.1f}%

## Analysis
{text}
"""
            feedback_path.write_text(feedback_content, encoding="utf-8")

            return {
                "slug": slug,
                "metrics": metrics,
                "okunma_rate": okunma_rate,
                "analysis": text,
            }

        except Exception as e:
            return {"error": f"Postmortem failed: {str(e)}"}

    # --- Voice Evolution ---


    def update_voice_profile(self, updates: Dict[str, Any]) -> str:
        """Update voice profile based on learnings."""
        vf = self.voice / "voice-profile.md"
        if not vf.exists():
            return "No voice profile exists."

        current = vf.read_text(encoding="utf-8")
        section = f"\n\n---\n\n## Updates from Feedback ({datetime.now().strftime('%Y-%m-%d')})\n\n"

        if updates.get("new_rules"):
            section += "### New Rules\n"
            for r in updates["new_rules"]:
                section += f"- {r}\n"
        if updates.get("banned_patterns"):
            section += "### Banned Patterns\n"
            for p in updates["banned_patterns"]:
                section += f"- {p}\n"
        if updates.get("insights"):
            section += "### Voice Insights\n"
            for i in updates["insights"]:
                section += f"- {i}\n"

        vf.write_text(current + section, encoding="utf-8")

        if updates.get("new_slop_patterns"):
            self._update_avoid_slop(updates["new_slop_patterns"])

        return "✅ Voice profile updated."


    def _update_avoid_slop(self, new_patterns: List[str]):
        sf = self.voice / "master-avoid-slop.md"
        if not sf.exists():
            return
        current = sf.read_text(encoding="utf-8")
        section = f"\n\n---\n\n## New Patterns ({datetime.now().strftime('%Y-%m-%d')})\n\n"
        for p in new_patterns:
            section += f"- {p}\n"
        sf.write_text(current + section, encoding="utf-8")

    # --- Signal Processing ---
    def _scan_x_signals(self) -> List[str]:
        inbox = self.stores / "inbox.md"
        signals = []
        if inbox.exists():
            content = inbox.read_text(encoding="utf-8")
            entries = re.findall(r'### .*?(?=\n###|\Z)', content, re.DOTALL)
            for e in entries:
                if any(x in e.lower() for x in ['x', 'memos', 'x.com']):
                    signals.append(e.strip()[:200])
        if not signals:
            signals = [
                "Signal: New RISC-V optimization patterns emerging",
                "Signal: AI Agents moving to local-first architectures",
                "Signal: Open-source hardware momentum growing",
            ]
        return signals[:5]


    def _scan_rss_signals(self) -> List[str]:
        """Fetch RSS headlines from NEWS_SOURCES via shared _fetch_rss_feed.

        Uses the same RSS parser as fetch_all_news to avoid code duplication.
        """
        signals = []
        for key, src in self.sources.items():
            if len(signals) >= 5:
                break
            for feed_url in src.rss_feeds:
                if len(signals) >= 5:
                    break
                try:
                    items = self._fetch_rss_feed(feed_url, src)
                    for item in items[:1]:
                        signals.append(f"[{src.name}] {item.title[:110]}")
                except (SourceError, urllib.error.URLError, OSError):
                    continue

        if not signals:
            signals = [
                "RSS: No live feed reached — check NEWS_SOURCES RSS URLs",
                "Try: hermes haber fetch for the full news pipeline",
            ]

        return signals[:5]


    def get_learnings_for_brief(self, topic: str = None) -> str:
        learnings = []
        feedback_dir = self.stores / "feedback"
        if feedback_dir.exists():
            for f in feedback_dir.glob("*.md"):
                content = f.read_text(encoding="utf-8")
                if "Good" in content or "okunma" in content.lower():
                    learnings.append(f"From {f.stem}: {content[:150]}")
        proof_dir = self.stores / "proof"
        if proof_dir.exists():
            for p in proof_dir.glob("*.md"):
                content = p.read_text(encoding="utf-8")
                learnings.append(f"Proof: {content[:150]}")
        if not learnings:
            return "No learnings available yet."
        return "\n\n".join(learnings[:5])

    # --- Context Retrieval ---


    def _get_relevant_proof(self, idea: str) -> str:
        proof_dir = self.stores / "proof"
        if not proof_dir.exists():
            return "No proof directory found."
        proof_files = list(proof_dir.glob("*.md"))
        if not proof_files:
            return "No proof available."
        return "\n\n".join(
            [f"## {p.stem}\n{p.read_text(encoding='utf-8')[:300]}"
             for p in proof_files[:3]]
        )


    def _get_successful_hooks(self) -> str:
        hooks_dir = self.stores / "hooks"
        if not hooks_dir.exists() or not list(hooks_dir.glob("*.md")):
            return "No successful hooks recorded yet."
        return "\n".join(
            [f"- {h.stem}: {h.read_text(encoding='utf-8')[:100]}"
             for h in list(hooks_dir.glob("*.md"))[:5]]
        )


    def _get_top_performing_runs(self) -> str:
        if not self.archive.exists():
            return "No archived runs yet."
        runs = []
        for d in self.archive.iterdir():
            if d.is_dir():
                fb = d / "feedback.md"
                if fb.exists():
                    content = fb.read_text(encoding="utf-8")
                    bm = re.search(r'okunma?[\s:]+(\d+)', content, re.IGNORECASE)
                    okunma = int(bm.group(1)) if bm else 0
                    runs.append((d.name, okunma))
        runs.sort(key=lambda x: x[1], reverse=True)
        if not runs:
            return "No run feedback available."
        return "\n".join([f"- {name}: {okunma} okunma" for name, okunma in runs[:5]])


    def _get_voice_summary(self) -> str:
        vf = self.voice / "voice-profile.md"
        if not vf.exists():
            return "No voice profile set."
        content = vf.read_text(encoding="utf-8")
        lines = [line for line in content.split('\n')
                 if line.strip().startswith(('1.', '2.', '3.', '4.', '5.'))]
        return "\n".join(lines[:5]) if lines else content[:300]
    def _query_gbrain(self, query: str) -> Dict[str, str]:
        """Query GBrain for relevant context (stub).

        Integration point: when GBrain MCP tools are connected,
        this method can use them. Returns empty dict by default.
        """
        logger.debug(f"GBrain query (stub): {query[:80]}")
        return {}

    # --- Pattern Analysis ---


    def analyze_run_patterns(self) -> Dict[str, Any]:
        all_runs = []
        for base_dir in [self.active_runs, self.archive]:
            if base_dir.exists():
                for d in base_dir.iterdir():
                    if d.is_dir():
                        try:
                            rd = self._analyze_single_run(d)
                            if rd:
                                all_runs.append(rd)
                        except (OSError, PermissionError):
                            continue

        if not all_runs:
            return {"message": "No runs to analyze."}

        total = len(all_runs)
        avg_bm = sum(r.get("okunma", 0) for r in all_runs) / max(total, 1)
        formats = {}
        pillars = {}
        for r in all_runs:
            formats[r.get("format", "unknown")] = formats.get(r.get("format", "unknown"), 0) + 1
            pillars[r.get("pillar", "unknown")] = pillars.get(r.get("pillar", "unknown"), 0) + 1

        states = {}
        for r in all_runs:
            st = r.get("state", "unknown")
            states[st] = states.get(st, 0) + 1

        return {
            "total_runs": total,
            "avg_okunma": round(avg_bm, 1),
            "top_formats": sorted(formats.items(), key=lambda x: x[1], reverse=True)[:5],
            "top_pillars": sorted(pillars.items(), key=lambda x: x[1], reverse=True)[:5],
            "state_distribution": states,
            "archive_count": len([r for r in all_runs if r.get("status") == "archived"]),
        }


    def _analyze_single_run(self, run_path: Path) -> Optional[Dict[str, Any]]:
        try:
            result = {"slug": run_path.name}
            obj = run_path / "haber-object.md"
            if obj.exists():
                content = obj.read_text(encoding="utf-8")
                for field in ["state", "route"]:
                    m = re.search(rf'{field}:\s*(.+)', content, re.IGNORECASE)
                    if m:
                        result[field] = m.group(1).strip()
            fb = run_path / "feedback.md"
            if fb.exists():
                content = fb.read_text(encoding="utf-8")
                bm = re.search(r'okunma?[\s:]+(\d+)', content, re.IGNORECASE)
                if bm:
                    result["okunma"] = int(bm.group(1))
            result["status"] = "archived" if "archive" in str(run_path) else "active"
            return result
        except PermissionError:
            return None

    # --- Audit & Retrieval ---


    def audit(self) -> str:
        """Full system audit."""
        issues = []
        warnings = []
        critical = [self.strategy, self.voice, self.stores,
                    self.workflows, self.references,
                    self.root / "runs", self.active_runs]
        for d in critical:
            if not d.exists():
                issues.append(f"Missing directory: {d.name}")

        for sub in ["ideas", "hooks", "proof", "feedback"]:
            if not (self.stores / sub).exists():
                issues.append(f"Missing stores subdirectory: {sub}")

        for sf in ["positioning.md", "audience.md", "pillars.md"]:
            if not (self.strategy / sf).exists():
                warnings.append(f"Missing strategy file: {sf}")

        active_count = len([d for d in self.active_runs.iterdir() if d.is_dir()]) if self.active_runs.exists() else 0
        archive_count = len([d for d in self.archive.iterdir() if d.is_dir()]) if self.archive.exists() else 0

        # Check source directory health
        total_sources = len(self.sources)
        tier0_count = len(self.get_sources_by_tier(SourceTier.PRIMARY))
        tier1_count = len(self.get_sources_by_tier(SourceTier.MAJOR))

        if not issues:
            base = (
                f"✅ Haber Kuratör v{VERSION} Audit: {active_count} active, {archive_count} archived.\n"
                f"📡 News Sources: {total_sources} total ({tier0_count} primary, {tier1_count} major)"
            )
            if warnings:
                base += "\n⚠️ " + "\n⚠️ ".join(warnings)
            return base

        return (
            f"❌ Haber Kuratör v{VERSION} Audit\n"
            f"📡 News Sources: {total_sources} total\n"
            f"❌ Issues:\n- " + "\n- ".join(issues) +
            ("\n⚠️ " + "\n⚠️ ".join(warnings) if warnings else "")
        )
    def _get_run_info(self, run_path: Path) -> Dict[str, Any]:
        info = {"slug": run_path.name, "files": []}
        try:
            for f in run_path.iterdir():
                if f.is_file():
                    info["files"].append(f.name)
        except PermissionError:
            info["files"] = ["[locked]"]
            return info

        obj = run_path / "haber-object.md"
        if obj.exists():
            content = obj.read_text(encoding="utf-8")
            for field in ["title", "state", "route"]:
                m = re.search(rf'(?:\*\*)?{field}(?:\*\*)?:\*{{0,2}}\s*(.+)', content, re.IGNORECASE)
                if m:
                    info[field] = m.group(1).strip().lstrip('* ')
        return info


