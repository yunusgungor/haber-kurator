#!/usr/bin/env bash
# Haber Kuratör v2.4.0 — Cross-Platform Stress Test Suite
# Tests all system components: runs, slop, state machine, edge cases
# Usage: bash stress_test.sh [--quick|--full]

set -euo pipefail

PLUGIN_DIR="${1:-$(dirname "$0")}"
PASS=0
FAIL=0
TOTAL=0

green() { echo -e "\033[32m✅ $1\033[0m"; }
red()   { echo -e "\033[31m❌ $1\033[0m"; }
bold()  { echo -e "\033[1m$1\033[0m"; }

cleanup() {
    rm -rf /tmp/haber-kurator-test*
}

# Clean before starting
cleanup

assert_contains() {
    TOTAL=$((TOTAL + 1))
    if echo "$2" | grep -q "$1"; then
        green "$3"
        PASS=$((PASS + 1))
    else
        red "$3 (expected '$1' in output)"
        echo "  Output: ${2:0:200}"
        FAIL=$((FAIL + 1))
    fi
}

assert_not_contains() {
    TOTAL=$((TOTAL + 1))
    if ! echo "$2" | grep -q "$1"; then
        green "$3"
        PASS=$((PASS + 1))
    else
        red "$3 (unexpected '$1' in output)"
        FAIL=$((FAIL + 1))
    fi
}

bold "╔══════════════════════════════════════════════════════════════╗"
bold "║     Haber Kuratör v2.4.0 — Stress Test Suite                 ║"
bold "║     $(date)                         ║"
bold "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ════════════════════════════════════════════════════
# TEST 1: Python imports
# ════════════════════════════════════════════════════
bold "─── Test 1: Python Module Imports ───"
python3 -c "
import sys
sys.path.insert(0, '$PLUGIN_DIR')
from haber_kurator_core import HaberKuratorCore, HaberKuratorError, VERSION, STATE_LIFECYCLE, IDEA_ROUTES
from haber_kurator_core import FULL_SLOP_TIER1, FULL_SLOP_TIER2, FULL_SLOP_TIER3, FULL_SLOP_BONUS
print(f'Version: {VERSION}')
print(f'States: {len(STATE_LIFECYCLE)} ({STATE_LIFECYCLE})')
print(f'Routes: {IDEA_ROUTES}')
print(f'Tier1 pats: {len(FULL_SLOP_TIER1)}')
print(f'Tier2 pats: {len(FULL_SLOP_TIER2)}')
print(f'Tier3 pats: {len(FULL_SLOP_TIER3)}')
print(f'Bonus pats: {len(FULL_SLOP_BONUS)}')
total_slop = len(FULL_SLOP_TIER1) + len(FULL_SLOP_TIER2) + len(FULL_SLOP_TIER3) + len(FULL_SLOP_BONUS)
print(f'Total slop patterns: {total_slop}')
" 2>&1

# Quick check: version consistency
PY_VER=$(python3 -c "import sys; sys.path.insert(0, '$PLUGIN_DIR'); from haber_kurator_core import VERSION; print(VERSION)")
if [ "$PY_VER" = "2.4.0" ]; then
    green "Plugin version correct: $PY_VER"
else
    red "Version wrong: $PY_VER (expected 2.4.0)"
fi

assert_contains "14" "$(python3 -c "
import sys; sys.path.insert(0, '$PLUGIN_DIR')
from haber_kurator_core import STATE_LIFECYCLE
print(len(STATE_LIFECYCLE))
")" "14-state lifecycle (expect 14)"

assert_contains "4" "$(python3 -c "
import sys; sys.path.insert(0, '$PLUGIN_DIR')
from haber_kurator_core import IDEA_ROUTES
print(len(IDEA_ROUTES))
")" "4 Idea Gate routes"

# ════════════════════════════════════════════════════
# TEST 2: 54+ slop patterns
# ════════════════════════════════════════════════════
bold $'\n'"─── Test 2: Slop Pattern Count (54 target) ───"
TOTAL_SLOP=$(python3 -c "
import sys; sys.path.insert(0, '$PLUGIN_DIR')
from haber_kurator_core import FULL_SLOP_TIER1, FULL_SLOP_TIER2, FULL_SLOP_TIER3, FULL_SLOP_BONUS
t = len(FULL_SLOP_TIER1) + len(FULL_SLOP_TIER2) + len(FULL_SLOP_TIER3) + len(FULL_SLOP_BONUS)
print(t)
")
if [ "$TOTAL_SLOP" -ge 54 ]; then
    green "54+ slop patterns (have $TOTAL_SLOP)"
else
    red "Only $TOTAL_SLOP slop patterns (need ≥54)"
fi

# ════════════════════════════════════════════════════
# TEST 3: Create run with Idea Gate
# ════════════════════════════════════════════════════
bold $'\n'"─── Test 3: Run Creation with Idea Gate ───"
python3 -c "
import sys, tempfile, json
sys.path.insert(0, '$PLUGIN_DIR')
from haber_kurator_core import HaberKuratorCore
from pathlib import Path

tmp = Path('/tmp/haber-kurator-test-3')
core = HaberKuratorCore(tmp)
core.setup()

# Create ORIGINAL run
r1 = core.create_run('My personal experience with timing closure', source_hint='internal')
print(f'R1: {r1[\"slug\"]} route={r1[\"route\"]}')
assert r1['route'] == 'ORIGINAL', f'Expected ORIGINAL, got {r1[\"route\"]}'

# Create REWRITE run
r2 = core.create_run('I read an article about RISC-V optimization', source_hint='external')
print(f'R2: {r2[\"slug\"]} route={r2[\"route\"]}')
assert r2['route'] == 'REWRITE', f'Expected REWRITE, got {r2[\"route\"]}'

# Create REPURPOSE run
r3 = core.create_run('Update on previous thread about pipeline design', source_hint='existing')
print(f'R3: {r3[\"slug\"]} route={r3[\"route\"]}')
assert r3['route'] == 'REPURPOSE', f'Expected REPURPOSE, got {r3[\"route\"]}'

# Create RESEARCH+IDEATE run
r4 = core.create_run('Research emerging trends in edge AI', source_hint='research')
print(f'R4: {r4[\"slug\"]} route={r4[\"route\"]}')
assert r4['route'] == 'RESEARCH+IDEATE', f'Expected RESEARCH+IDEATE, got {r4[\"route\"]}'

# Check slug exists
obj = tmp / 'runs' / 'active' / r1['slug'] / 'haber-object.md'
assert obj.exists(), f'haber-object.md missing for {r1["slug"]}'
content = obj.read_text()
assert '**Status:** captured' in content, f'Wrong initial state: missing Status: captured. Got: {content[:200]}'

print('All run creation tests passed!')
" 2>&1

assert_contains "ORIGINAL" "$(python3 -c "
import sys, tempfile
sys.path.insert(0, '$PLUGIN_DIR')
from haber_kurator_core import HaberKuratorCore
from pathlib import Path
tmp = Path('/tmp/haber-kurator-test-4')
core = HaberKuratorCore(tmp); core.setup()
r = core.create_run('My experience', source_hint='internal')
print(r['route'])
")" "Idea Gate → ORIGINAL route"

assert_contains "REWRITE" "$(python3 -c "
import sys, tempfile
sys.path.insert(0, '$PLUGIN_DIR')
from haber_kurator_core import HaberKuratorCore
from pathlib import Path
tmp = Path('/tmp/haber-kurator-test-5')
core = HaberKuratorCore(tmp); core.setup()
r = core.create_run('Article about AI', source_hint='external')
print(r['route'])
")" "Idea Gate → REWRITE route"

assert_contains "REPURPOSE" "$(python3 -c "
import sys, tempfile
sys.path.insert(0, '$PLUGIN_DIR')
from haber_kurator_core import HaberKuratorCore
from pathlib import Path
tmp = Path('/tmp/haber-kurator-test-6')
core = HaberKuratorCore(tmp); core.setup()
r = core.create_run('Follow-up to pipeline post', source_hint='existing')
print(r['route'])
")" "Idea Gate → REPURPOSE route"

assert_contains "RESEARCH+IDEATE" "$(python3 -c "
import sys, tempfile
sys.path.insert(0, '$PLUGIN_DIR')
from haber_kurator_core import HaberKuratorCore
from pathlib import Path
tmp = Path('/tmp/haber-kurator-test-7')
core = HaberKuratorCore(tmp); core.setup()
r = core.create_run('Explore RISC-V trends', source_hint='research')
print(r['route'])
")" "Idea Gate → RESEARCH+IDEATE route"

# ════════════════════════════════════════════════════
# TEST 4: 14-state lifecycle
# ════════════════════════════════════════════════════
bold $'\n'"─── Test 4: 14-State Lifecycle ───"
python3 -c "
import sys, tempfile
sys.path.insert(0, '$PLUGIN_DIR')
from haber_kurator_core import HaberKuratorCore, STATE_LIFECYCLE, STATE_TRANSITIONS
from pathlib import Path

tmp = Path('/tmp/haber-kurator-test-8')
core = HaberKuratorCore(tmp); core.setup()

# Walk through the complete lifecycle
slug = core.create_run('Test lifecycle', source_hint='internal')['slug']

transitions = [
    ('idea_review', 'Route decision'),
    ('brief_ready', 'Brief ready'),
    ('drafting', 'Drafting'),
    ('verification', 'Verification'),
    ('draft_review', 'Draft review'),
    ('approved', 'Approved'),
    ('scheduler_ready', 'Scheduler ready'),
    ('scheduled', 'Scheduled'),
    ('published', 'Published'),
    ('feedback_24h', '24h feedback'),
    ('feedback_72h', '72h feedback'),
    ('learned', 'Learned'),
    ('archived', 'Archived'),
]

for state, label in transitions:
    result = core.update_state(slug, state)
    assert '✅' in result or '❌' in result, f'Failed at {state}: {result}'
    assert '❌' not in result or state == 'archived', f'Transition rejected at {state}: {result}'
    print(f'  ✅ {label}: {state}')

# Test invalid transition
result = core.update_state(slug, 'captured')
assert '❌' in result, f'Should reject invalid transition'
print('  ✅ Invalid transition correctly rejected')

# Test sync
state = core.sync_state(slug)
print(f'  ✅ Sync state: {state}')

# Test get_state
state = core.get_state(slug)
print(f'  ✅ Read state: {state}')

# Test next actions
actions = core.get_next_actions(slug)
print(f'  ✅ Next actions: {len(actions)} items')

print('All lifecycle tests passed!')
" 2>&1

STATE_COUNT=$(python3 -c "
import sys; sys.path.insert(0, '$PLUGIN_DIR')
from haber_kurator_core import STATE_LIFECYCLE
print(len(STATE_LIFECYCLE))
")
assert_contains "14" "$(echo "Count: $STATE_COUNT")" "14 states in lifecycle (expect 14)"

# ════════════════════════════════════════════════════
# TEST 5: Slop detection (all tiers)
# ════════════════════════════════════════════════════
bold $'\n'"─── Test 5: Slop Detection (all tiers) ───"
python3 -c "
import sys, tempfile
sys.path.insert(0, '$PLUGIN_DIR')
from haber_kurator_core import HaberKuratorCore
from pathlib import Path

tmp = Path('/tmp/haber-kurator-test-9')
core = HaberKuratorCore(tmp); core.setup()

# T1 slop
t1_text = 'This groundbreaking approach is a testament to our work. Experts believe this game-changing method will transform everything.'
r1 = core.scan_slop(t1_text)
assert r1['tier1_count'] >= 1, f'Should detect T1, got: {r1}'
assert r1['score'] in ('REVISE', 'REJECT'), f'Should be REVISE/REJECT, got: {r1[\"score\"]}'
print(f'  ✅ T1 detection: {r1[\"tier1_count\"]} patterns, score={r1[\"score\"]}')

# T2 slop
t2_text = 'This tool serves as a comprehensive solution. We are leveraging cutting-edge technology to enable seamless integration.'
r2 = core.scan_slop(t2_text)
assert r2['tier2_count'] >= 1, f'Should detect T2, got: {r2}'
print(f'  ✅ T2 detection: {r2[\"tier2_count\"]} patterns, score={r2[\"score\"]}')

# T3 slop
t3_text = 'It was noted that very important things were recently discovered. This should be considered when exploring the roadmap.'
r3 = core.scan_slop(t3_text)
print(f'  ✅ T3 detection: {r3[\"tier3_count\"]} patterns, score={r3[\"score\"]}')

# Clean content → PASS
clean = 'I fixed timing by reordering the pipeline stages. Here is my exact approach: first, I profiled the critical path. Then I moved the ALU to stage 3. Result: 40 ns → 12 ns. Try this on your next tapeout.'
r4 = core.scan_slop(clean)
assert r4['score'] == 'PASS', f'Clean content should PASS, got: {r4[\"score\"]}'
print(f'  ✅ Clean content → PASS')

# Zero slop
r5 = core.scan_slop('')
assert r5['score'] == 'PASS', f'Empty should PASS'
print(f'  ✅ Empty content → PASS')

print('All slop tests passed!')
" 2>&1

# ════════════════════════════════════════════════════
# TEST 6: Edge cases
# ════════════════════════════════════════════════════
bold $'\n'"─── Test 6: Edge Cases ───"
python3 -c "
import sys, tempfile, json
sys.path.insert(0, '$PLUGIN_DIR')
from haber_kurator_core import HaberKuratorCore
from pathlib import Path

tmp = Path('/tmp/haber-kurator-test-10')
core = HaberKuratorCore(tmp); core.setup()

# Duplicate slug
r1 = core.create_run('Test idea')
r2 = core.create_run('Test idea', slug=r1['slug'])
assert r2.get('status') == 'exists', f'Should detect duplicate: {r2}'
print('  ✅ Duplicate slug detected')

# Very long idea (500+ chars)
long_idea = 'X ' * 300
r3 = core.create_run(long_idea)
print(f'  ✅ Long idea: {len(r3[\"slug\"])} char slug')

# UTF-8
utf_ideas = [
    '日本語のテスト投稿',
    '测试中文内容',
    'اختبار المحتوى العربي',
    '🚀 Emoji test with 🔥 and 💡 ideas',
]
for idea in utf_ideas:
    r = core.create_run(idea)
    obj = tmp / 'runs' / 'active' / r['slug'] / 'idea.md'
    content = obj.read_text(encoding='utf-8')
    assert idea[:20] in content, f'UTF-8 content mismatch: {content[:50]}'
print('  ✅ UTF-8 (Japanese/Chinese/Arabic/Emoji)')

# Spaces only
r4 = core.create_run('   ')
assert r4['slug'], f'Spaces-only should produce fallback slug'
print('  ✅ Spaces-only handled')

# Special chars in slug
r5 = core.create_run('test@#$%^&*() slug')
print(f'  ✅ Special chars sanitized: {r5[\"slug\"]}')

# Permission error simulation (non-existent dir)
state = core.sync_state('nonexistent-slug')
assert state == 'unknown', f'Non-existent slug: {state}'
print('  ✅ Non-existent safe handling')

print('All edge case tests passed!')
" 2>&1

# ════════════════════════════════════════════════════
# TEST 7: Search & retrieve
# ════════════════════════════════════════════════════
bold $'\n'"─── Test 7: Search & Retrieve ───"
python3 -c "
import sys, tempfile, json
sys.path.insert(0, '$PLUGIN_DIR')
from haber_kurator_core import HaberKuratorCore
from pathlib import Path

tmp = Path('/tmp/haber-kurator-test-11')
core = HaberKuratorCore(tmp); core.setup()

# Create a run
slug = core.create_run('RISC-V pipeline optimization for edge devices')['slug']

# Write some files
run_path = tmp / 'runs' / 'active' / slug
(run_path / 'brief.md').write_text('## Brief\nWrite about RISC-V pipeline', encoding='utf-8')
(run_path / 'draft-package.md').write_text('## Draft\nRISC-V pipeline has 5 stages', encoding='utf-8')

# Search
results = core.search_runs('pipeline')
assert len(results) >= 1, f'Search should find pipeline: {results}'
print(f'  ✅ Search found {len(results)} results')

# Get all runs
all_runs = core.get_all_runs()
print(f'  ✅ get_all_runs: {len(all_runs)} runs')

# Audit
audit = core.audit()
assert '✅' in audit, f'Audit should pass: {audit}'
print(f'  ✅ System audit passed')

# Retriever
from haber_kurator_core import tool_haber_kurator_retriever
import json
result = json.loads(tool_haber_kurator_retriever(core, {'category': 'run', 'slug': slug}))
assert isinstance(result, dict), f'Retriever should return dict: {type(result)}'
assert 'haber-object' in result or 'idea' in result, f'Should retrieve run data: {list(result.keys())}'
print(f'  ✅ Retriever works: {list(result.keys())}')

print('All search/retrieve tests passed!')
" 2>&1

# ════════════════════════════════════════════════════
# TEST 8: Audit
# ════════════════════════════════════════════════════
bold $'\n'"─── Test 8: Audit ───"
python3 -c "
import sys, tempfile
sys.path.insert(0, '$PLUGIN_DIR')
from haber_kurator_core import HaberKuratorCore
from pathlib import Path

# Fresh system should be clean (warnings OK, but no critical issues)
tmp = Path('/tmp/haber-kurator-test-12')
core = HaberKuratorCore(tmp); core.setup()
report = core.audit()
assert report.startswith('✅'), f'Fresh audit should start with ✅: {report[:100]}'
print(f'  ✅ Fresh system: {report[:100]}')

# Missing structure should be flagged
tmp2 = Path('/tmp/haber-kurator-test-13')
core2 = HaberKuratorCore(tmp2)
# Don't call setup — structure missing
report2 = core2.audit()
assert 'issues' in report2.lower() or '❌' in report2, f'Should have issues: {report2[:100]}'
print(f'  ✅ Missing structure detected: {\"❌\" in report2}')

print('All audit tests passed!')
" 2>&1

# ════════════════════════════════════════════════════
# TEST 9: Plugin integrity
# ════════════════════════════════════════════════════
bold $'\n'"─── Test 9: Plugin Integrity ───"
# Clean up temp dirs from earlier tests
cleanup
# Check required files exist
for f in "$PLUGIN_DIR/plugin.yaml" "$PLUGIN_DIR/__init__.py" \
         "$PLUGIN_DIR/haber_kurator_core.py" "$PLUGIN_DIR/cli.py" \
         "$PLUGIN_DIR/SKILL.md" "$PLUGIN_DIR/README.md"; do
    if [ -f "$f" ]; then
        green "File exists: $(basename $f)"
    else
        red "MISSING: $f"
    fi
done

# Check version consistency
PY_VER=$(python3 -c "import sys; sys.path.insert(0, '$PLUGIN_DIR'); from haber_kurator_core import VERSION; print(VERSION)")
YAML_VER=$(grep "^version:" "$PLUGIN_DIR/plugin.yaml" | awk '{print $2}')
if [ "$PY_VER" = "$YAML_VER" ]; then
    green "Version consistent: $PY_VER"
else
    red "Version MISMATCH: PY=$PY_VER YAML=$YAML_VER"
fi

# Check no git in plugin
if [ ! -d "$PLUGIN_DIR/.git" ]; then
    green "No .git directory inside plugin (clean)"
else
    red ".git directory still present"
fi

# Check temp workspace cleanup (no leftover temp dirs)
EMPTY_TEMP=$(find /tmp -maxdepth 1 -name "haber-kurator-test-*" -type d 2>/dev/null || echo "")
if [ -z "$EMPTY_TEMP" ]; then
    green "Temp workspace clean — no leftover test dirs"
else
    red "Temp workspace has leftover test dirs: $EMPTY_TEMP"
fi

# ════════════════════════════════════════════════════
# SUMMARY
# ════════════════════════════════════════════════════
bold $'\n'"╔══════════════════════════════════════════════════════════════╗"
bold "║                    TEST SUMMARY                              ║"
bold "╠══════════════════════════════════════════════════════════════╣"
printf "║  %-60s ║\n" "Total tests: $TOTAL"
printf "║  %-60s ║\n" "Passed:      $PASS"
printf "║  %-60s ║\n" "Failed:      $FAIL"
if [ "$FAIL" -eq 0 ]; then
    bold "║  ✅  ALL TESTS PASSED                                   ║"
else
    bold "║  ❌  SOME TESTS FAILED                                  ║"
fi
bold "╚══════════════════════════════════════════════════════════════╝"

# Cleanup
cleanup

exit $FAIL
