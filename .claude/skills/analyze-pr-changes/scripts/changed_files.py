#!/usr/bin/env python3
"""Classify changed files for the test agent.

Usage:
  changed_files.py --base origin/main     # files changed on HEAD since merge-base with base
  changed_files.py --files PATH [PATH...] # explicit files or directories (coverage mode)

Prints JSON to stdout and writes it to .agent-results/changes.json.
Rules mirror the coverage scope in backend/pyproject.toml and frontend/vite.config.ts.
"""

import argparse
import json
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / ".agent-results" / "changes.json"

BACKEND_SKIP = ["*/__init__.py", "backend/app/main.py", "*/types.py", "*/constants.py"]
BACKEND_INDIRECT = ["*/schemas.py", "*/models.py"]
FRONTEND_SKIP = [
    "frontend/src/main.tsx",
    "frontend/src/test/*",
    "frontend/src/design-system/*",
    "*/types.ts",
    "*.types.ts",
    "*/index.ts",
    "*.constants.ts",
    "*/constants.ts",
    "*/constants.tsx",
    "*.stories.tsx",
    "*.styles.ts",
    "*.variants.ts",
    "frontend/src/features/todos/api/queryKeys.ts",
    "frontend/src/lib/queryClient.ts",
]


def matches(path, patterns):
    return any(fnmatch(path, p) for p in patterns)


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def changed_from_base(base):
    """Return (changed, deleted) relative paths from `git diff base...HEAD`."""
    out = git("diff", "--name-status", "-z", "-M", f"{base}...HEAD")
    fields = out.split("\0")
    changed, deleted = [], []
    i = 0
    while i < len(fields) and fields[i]:
        status = fields[i]
        if status.startswith(("R", "C")):
            changed.append(fields[i + 2])
            i += 3
            continue
        (deleted if status == "D" else changed).append(fields[i + 1])
        i += 2
    return changed, deleted


def expand(paths):
    files = []
    for raw in paths:
        p = (ROOT / raw).resolve()
        if not p.is_relative_to(ROOT):
            sys.exit(f"Refusing path outside the repository: {raw}")
        if p.is_dir():
            files += [f for f in p.rglob("*") if f.is_file() and "node_modules" not in f.parts]
        elif p.is_file():
            files.append(p)
    return sorted(str(f.relative_to(ROOT).as_posix()) for f in files)


def backend_test_path(path):
    rel = PurePosixPath(path).relative_to("backend/app")
    return str(PurePosixPath("backend/tests", *rel.parts[:-1], f"test_{rel.name}"))


def frontend_test_path(path):
    p = PurePosixPath(path)
    return str(p.with_name(f"{p.stem}.test{p.suffix}"))


def entry(path, test_path):
    return {"path": path, "test_path": test_path, "test_exists": (ROOT / test_path).is_file()}


def classify(changed, deleted):
    result = {
        "backend": {"source": [], "indirect": [], "tests": []},
        "frontend": {"source": [], "tests": []},
        "skipped": [],
        "deleted": deleted,
    }
    for path in changed:
        if path.startswith("backend/tests/") and path.endswith(".py"):
            result["backend"]["tests"].append(path)
        elif path.startswith("backend/app/") and path.endswith(".py"):
            if matches(path, BACKEND_SKIP):
                result["skipped"].append({"path": path, "reason": "excluded from backend coverage"})
            elif matches(path, BACKEND_INDIRECT):
                result["backend"]["indirect"].append(
                    {"path": path, "reason": "test behaviour through the router/repository tests"}
                )
            else:
                result["backend"]["source"].append(entry(path, backend_test_path(path)))
        elif path.startswith("frontend/src/") and path.endswith((".ts", ".tsx")):
            if fnmatch(path, "*.test.ts") or fnmatch(path, "*.test.tsx"):
                result["frontend"]["tests"].append(path)
            elif matches(path, FRONTEND_SKIP):
                result["skipped"].append({"path": path, "reason": "excluded from frontend coverage"})
            else:
                result["frontend"]["source"].append(entry(path, frontend_test_path(path)))
        else:
            result["skipped"].append({"path": path, "reason": "not unit-testable application code"})
    result["has_testable_changes"] = bool(
        result["backend"]["source"] or result["backend"]["indirect"] or result["frontend"]["source"]
    )
    return result


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--base", help="base ref, e.g. origin/main")
    group.add_argument("--files", nargs="+", help="files or directories to analyze")
    args = parser.parse_args()

    if args.base:
        changed, deleted = changed_from_base(args.base)
    else:
        changed, deleted = expand(args.files), []
    result = {"mode": "diff" if args.base else "files", "base": args.base, **classify(changed, deleted)}

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
