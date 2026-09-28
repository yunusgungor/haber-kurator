"""Measure E-015: coverage_measured — pytest-cov generates a valid HTML report."""
import sys
import subprocess
import re
from pathlib import Path

REPORT_DIR = Path("coverage_report")
COV_ARGS = [
    "--cov=haber_kurator_core", "--cov=writer_agent",
    "--cov-report=term",
    "--cov-report=html:" + str(REPORT_DIR),
]

# Run coverage
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/", "--rootdir=tests"] + COV_ARGS,
    capture_output=True, text=True, timeout=120
)

# Extract total coverage from combined output
combined = result.stdout + (result.stderr or "")
m = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", combined)
total = int(m.group(1)) if m else 0
m2 = re.search(r"haber_kurator_core\.py\s+\d+\s+\d+\s+(\d+)%", combined)
core = int(m2.group(1)) if m2 else 0

# Verify HTML report exists
report_path = REPORT_DIR / "index.html"
report_ok = report_path.exists() and report_path.stat().st_size > 0

print(f"  ✅ total_coverage={total}%")
print(f"  ✅ core_coverage={core}%")
print(f"  ✅ html_report_exists={'yes' if report_ok else 'no'}")

if total > 0 and report_ok:
    print(f"\nmetric_coverage_measured_score=1.00 (1/1)")
    sys.exit(0)
else:
    print(f"\nmetric_coverage_measured_score=0.00 (0/1)")
    sys.exit(1)