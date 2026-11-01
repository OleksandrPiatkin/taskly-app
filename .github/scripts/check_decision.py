#!/usr/bin/env python3
"""Validate the agent's decision.json against the patch it produced.

Usage: check_decision.py <decision.json> <patch>

Prints a JSON summary to stdout (save it as verify.json for build_comment.py):
  {"ok": bool, "decision": str|null, "errors": [...], "warnings": [...],
   "patch_files": [...], "decision_files": [...], "findings_count": int,
   "breaks_existing_tests": bool}
Exit 0 if ok, 1 if validation failed, 2 on usage errors.

Checks: required keys and types; "decision" is a known value; the "files" paths equal the set of
files in the patch exactly; no_tests_needed/failed => empty patch; tests_added/tests_updated =>
non-empty patch. Path policy (allowed test paths, no deletions, ...) is guard_patch.py's job.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # keep the checkout clean (no __pycache__ next to the scripts)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard_patch import parse_patch  # noqa: E402

DECISIONS = {"tests_added", "tests_updated", "no_tests_needed", "failed"}
NEEDS_PATCH = {"tests_added", "tests_updated"}
REQUIRED = {"decision": str, "summary": str, "files": list, "skipped": list, "findings": list, "suites": dict}
CHANGES = {"added", "updated"}
# Wording required by .claude/skills/summarize-results/SKILL.md for PR-caused test breaks.
BREAKS_RE = re.compile(r"breaks? (an )?existing tests?", re.IGNORECASE)


def check(decision_path: Path, patch_path: Path) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    result = {
        "ok": False,
        "decision": None,
        "errors": errors,
        "warnings": warnings,
        "patch_files": [],
        "decision_files": [],
        "findings_count": 0,
        "breaks_existing_tests": False,
    }

    patch_files: dict[str, bool] | None = None
    try:
        text = patch_path.read_bytes().decode("utf-8")
        files, violations = parse_patch(text)
        if violations:
            errors.append(f"patch could not be parsed cleanly ({len(violations)} problem(s)); run guard_patch.py for details")
        patch_files = {f["path"]: f["new"] for f in files}
        result["patch_files"] = sorted(patch_files)
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"cannot read patch {patch_path}: {exc}")

    try:
        data = json.loads(decision_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"cannot read {decision_path}: {exc}")
        return result
    except json.JSONDecodeError as exc:
        errors.append(f"{decision_path} is not valid JSON: {exc}")
        return result
    if not isinstance(data, dict):
        errors.append("decision.json must be a JSON object")
        return result

    for key, kind in REQUIRED.items():
        if key not in data:
            errors.append(f"missing required key '{key}'")
        elif not isinstance(data[key], kind):
            errors.append(f"'{key}' must be a {kind.__name__}")

    decision = data.get("decision")
    if isinstance(decision, str) and decision in DECISIONS:
        result["decision"] = decision
    elif "decision" in data:
        errors.append(f"'decision' must be one of {sorted(DECISIONS)}, got {decision!r}")

    decision_files: dict[str, str] = {}
    for idx, item in enumerate(data.get("files") if isinstance(data.get("files"), list) else []):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not item["path"]:
            errors.append(f"files[{idx}] must be an object with a non-empty string 'path'")
            continue
        if item["path"] in decision_files:
            errors.append(f"files[{idx}]: duplicate path {item['path']}")
        change = item.get("change")
        if change not in CHANGES:
            errors.append(f"files[{idx}]: 'change' must be one of {sorted(CHANGES)}, got {change!r}")
        decision_files[item["path"]] = change
    result["decision_files"] = sorted(decision_files)

    findings = data.get("findings") if isinstance(data.get("findings"), list) else []
    result["findings_count"] = len(findings)
    result["breaks_existing_tests"] = any(
        isinstance(f, dict) and isinstance(f.get("issue"), str) and BREAKS_RE.search(f["issue"])
        for f in findings
    )

    if patch_files is not None:
        missing = sorted(set(patch_files) - set(decision_files))
        extra = sorted(set(decision_files) - set(patch_files))
        if missing:
            errors.append(f"files in the patch but not in decision.json: {', '.join(missing)}")
        if extra:
            errors.append(f"files in decision.json but not in the patch: {', '.join(extra)}")
        for path, change in decision_files.items():
            if path in patch_files and change in CHANGES:
                actual = "added" if patch_files[path] else "updated"
                if change != actual:
                    warnings.append(f"{path}: decision says '{change}' but the patch shows it as {actual}")

        if result["decision"] in NEEDS_PATCH and not patch_files:
            errors.append(f"decision '{result['decision']}' requires a non-empty patch")
        if result["decision"] in DECISIONS - NEEDS_PATCH and patch_files:
            errors.append(f"decision '{result['decision']}' requires an empty patch, but it touches {len(patch_files)} file(s)")

    result["ok"] = not errors
    return result


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: check_decision.py <decision.json> <patch>", file=sys.stderr)
        return 2
    result = check(Path(argv[1]), Path(argv[2]))
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    for error in result["errors"]:
        print(f"ERROR: {error}", file=sys.stderr)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
