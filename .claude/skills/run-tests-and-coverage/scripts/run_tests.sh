#!/usr/bin/env bash
# Run Taskly test suites with coverage and write .agent-results/results-<label>.json.
# Usage: run_tests.sh [all|backend|frontend] [label]
set -uo pipefail

SUITE="${1:-all}"
LABEL="${2:-final}"
case "$SUITE" in all|backend|frontend) ;; *) echo "unknown suite: $SUITE" >&2; exit 2 ;; esac
[[ "$LABEL" =~ ^[a-z0-9_-]+$ ]] || { echo "invalid label: $LABEL" >&2; exit 2; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
OUT="$ROOT/.agent-results"
mkdir -p "$OUT"

backend_exit=""; frontend_exit=""; typecheck_exit=""

if [[ "$SUITE" == all || "$SUITE" == backend ]]; then
  (cd "$ROOT/backend" && python -m pytest -q -p no:cacheprovider \
      --cov=app --cov-report=term-missing --cov-report=xml --cov-report=json \
      --junitxml="$OUT/backend-junit.xml") >"$OUT/backend-$LABEL.log" 2>&1
  backend_exit=$?
fi

if [[ "$SUITE" == all || "$SUITE" == frontend ]]; then
  (cd "$ROOT/frontend" && npx --no-install vitest run --coverage \
      --reporter=default --reporter=junit --outputFile.junit="$OUT/frontend-junit.xml") \
      >"$OUT/frontend-$LABEL.log" 2>&1
  frontend_exit=$?
  (cd "$ROOT/frontend" && npx --no-install tsc --noEmit) >>"$OUT/frontend-$LABEL.log" 2>&1
  typecheck_exit=$?
fi

python3 - "$ROOT" "$OUT" "$LABEL" "$backend_exit" "$frontend_exit" "$typecheck_exit" <<'PY'
import json, sys
import xml.etree.ElementTree as ET
from pathlib import Path

root, out, label, b_exit, f_exit, t_exit = sys.argv[1:]
root, out = Path(root), Path(out)


def junit_counts(path):
    if not path.is_file():
        return {}
    tree = ET.parse(path).getroot()
    suites = [tree] if tree.tag == "testsuite" else tree.findall("testsuite")
    total = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for s in suites:
        for key in total:
            total[key] += int(s.get(key, 0) or 0)
    return total


def load(path):
    return json.loads(path.read_text()) if path.is_file() else None


result = {"label": label}

if b_exit:
    cov = load(root / "backend/coverage/coverage.json")
    result["backend"] = {
        "status": "passed" if b_exit == "0" else "failed",
        "exit_code": int(b_exit),
        **junit_counts(out / "backend-junit.xml"),
        "coverage": {"total": round(cov["totals"]["percent_covered"], 2)} if cov else None,
    }
else:
    result["backend"] = {"status": "not_run"}

if f_exit:
    summary = load(root / "frontend/coverage/coverage-summary.json")
    passed = f_exit == "0" and t_exit == "0"
    result["frontend"] = {
        "status": "passed" if passed else "failed",
        "exit_code": int(f_exit),
        "typecheck_exit_code": int(t_exit),
        **junit_counts(out / "frontend-junit.xml"),
        "coverage": {k: summary["total"][k]["pct"] for k in ("lines", "branches", "functions", "statements")}
        if summary else None,
    }
else:
    result["frontend"] = {"status": "not_run"}

(out / f"results-{label}.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
failed = any(result[s]["status"] == "failed" for s in ("backend", "frontend"))
sys.exit(1 if failed else 0)
PY
