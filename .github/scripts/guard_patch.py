#!/usr/bin/env python3
"""Reject a git patch unless it only adds or modifies allowed test files.

Usage: guard_patch.py <patch>

Exit 0 if every file in the patch is an allowed test path and every change is a plain text
add/modify. Exit 1 (printing every violation) otherwise. Exit 2 on usage errors.

The patch is untrusted (it is produced by a job that ran an LLM on PR content), so it is parsed
strictly: anything this parser does not understand is a violation, including text that `git apply`
would accept as a traditional (non-git) diff between file sections.

Also importable: `parse_patch(text) -> (files, violations)` is used by check_decision.py.
"""

from __future__ import annotations

import re
import sys
from fnmatch import fnmatch
from pathlib import Path

# Keep identical to ALLOWED in .claude/hooks/guard_test_paths.py (minus ".agent-results/*", which
# make_patch.sh excludes from the patch). fnmatch's "*" also matches "/", so these cover subfolders.
ALLOWED = [
    "backend/tests/*.py",
    "frontend/src/*.test.ts",
    "frontend/src/*.test.tsx",
    "frontend/src/test/*",
]

# Paths that are allowed by ALLOWED but must never change: Vitest's global setup file
# (setupFiles in frontend/vite.config.ts) runs before every frontend test.
PROTECTED = {"frontend/src/test/setup.ts"}
# Added lines in backend/tests/** that would change how pytest runs (hooks, plugins). Normal fixtures
# in conftest.py stay allowed.
PYTEST_HOOK_RE = re.compile(r"^\s*(?:async\s+)?def pytest_\w+|\bpytest_plugins\b")

ALLOWED_MODES = {"100644", "100755"}
NEW_FILE_MODE = "100644"
MODE_NAMES = {"120000": "symlink", "160000": "submodule (gitlink)"}

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
INDEX_RE = re.compile(r"^index [0-9a-f]+\.\.[0-9a-f]+(?: (\d{6}))?$")


def path_violation(path: str) -> str | None:
    if not path:
        return "empty path"
    if path.startswith("/") or "\\" in path or "\0" in path:
        return f"{path}: absolute path or unsafe character"
    if ".." in path.split("/"):
        return f"{path}: path contains '..'"
    if not any(fnmatch(path, pattern) for pattern in ALLOWED):
        return f"{path}: not an allowed test path ({', '.join(ALLOWED)})"
    if path in PROTECTED:
        return f"{path}: protected test setup file; changes are not allowed"
    return None


def header_path(rest: str) -> str | None:
    """Return P from 'a/P b/P'; None for quoted, renamed or otherwise ambiguous headers."""
    if rest.startswith('"'):
        return None
    if len(rest) < 7 or (len(rest) - 5) % 2:
        return None
    path = rest[2 : 2 + (len(rest) - 5) // 2]
    return path if rest == f"a/{path} b/{path}" else None


def mode_problem(mode: str, path: str) -> str | None:
    if mode in MODE_NAMES:
        return f"{path}: {MODE_NAMES[mode]} (mode {mode}) is not allowed"
    if mode not in ALLOWED_MODES:
        return f"{path}: unexpected file mode {mode}"
    return None


def parse_patch(text: str) -> tuple[list[dict], list[str]]:
    """Parse a `git diff` patch. Returns ([{"path", "new"}], [violation, ...])."""
    files: list[dict] = []
    violations: list[str] = []
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    i, n = 0, len(lines)

    while i < n:
        line = lines[i]
        if not line.startswith("diff --git "):
            violations.append(f"line {i + 1}: unexpected content outside a file section: {line[:80]!r}")
            i += 1
            continue

        section_start = i + 1
        path = header_path(line[len("diff --git ") :])
        i += 1
        if path is None:
            violations.append(
                f"line {section_start}: unsupported file header (quoted path, rename or copy): {line[:120]!r}"
            )
            # Skip to the next section; its content is not trusted.
            while i < n and not lines[i].startswith("diff --git "):
                i += 1
            continue

        entry = {"path": path, "new": False}
        deleted = False
        files.append(entry)
        check_hooks = path.startswith("backend/tests/")
        problem = path_violation(path)
        if problem:
            violations.append(problem)

        # Extended header lines.
        while i < n and not lines[i].startswith(("--- ", "@@ ", "diff --git ")):
            h = lines[i]
            if h.startswith("new file mode "):
                mode = h.split()[-1]
                entry["new"] = True
                if mode != NEW_FILE_MODE:
                    violations.append(mode_problem(mode, path) or f"{path}: new file must have mode {NEW_FILE_MODE}, got {mode}")
            elif h.startswith("deleted file mode "):
                deleted = True
                violations.append(f"{path}: deleting files is not allowed")
            elif h.startswith(("old mode ", "new mode ")):
                mode = h.split()[-1]
                violations.append(mode_problem(mode, path) if mode in MODE_NAMES else f"{path}: mode change is not allowed ({h})")
            elif h.startswith(("similarity index ", "dissimilarity index ", "rename from ", "rename to ")):
                violations.append(f"{path}: renames are not allowed ({h})")
            elif h.startswith(("copy from ", "copy to ")):
                violations.append(f"{path}: copies are not allowed ({h})")
            elif h.startswith("index "):
                m = INDEX_RE.match(h)
                if not m:
                    violations.append(f"{path}: malformed index line: {h[:80]!r}")
                elif m.group(1):
                    problem = mode_problem(m.group(1), path)
                    if problem:
                        violations.append(problem)
            elif h.startswith("Binary files ") or h == "GIT binary patch":
                violations.append(f"{path}: binary patches are not allowed")
                while i + 1 < n and not lines[i + 1].startswith("diff --git "):
                    i += 1
            else:
                violations.append(f"{path}: unexpected header line: {h[:80]!r}")
            i += 1

        # Unified diff body.
        if i < n and lines[i].startswith("--- "):
            old = lines[i][4:]
            plus = lines[i + 1] if i + 1 < n else ""
            if not plus.startswith("+++ "):
                violations.append(f"{path}: '---' line not followed by '+++'")
                i += 1
                continue
            new = plus[4:]
            # git appends a tab to ---/+++ paths that contain a space (as in GNU diff); strip one.
            if " " in path:
                old = old[:-1] if old.endswith("\t") else old
                new = new[:-1] if new.endswith("\t") else new
            expected_old = "/dev/null" if entry["new"] else f"a/{path}"
            expected_new = "/dev/null" if deleted else f"b/{path}"
            if old != expected_old or new != expected_new:
                violations.append(f"{path}: ---/+++ paths do not match the file header ({old!r}, {new!r})")
            i += 2
            if i >= n or not lines[i].startswith("@@ "):
                violations.append(f"{path}: file section has no hunks")
            while i < n and lines[i].startswith("@@ "):
                m = HUNK_RE.match(lines[i])
                if not m:
                    violations.append(f"{path}: malformed hunk header: {lines[i][:80]!r}")
                    break
                old_left = int(m.group(2) if m.group(2) is not None else 1)
                new_left = int(m.group(4) if m.group(4) is not None else 1)
                i += 1
                while i < n and (old_left > 0 or new_left > 0):
                    body = lines[i]
                    tag = body[:1]
                    if tag in (" ", ""):
                        old_left -= 1
                        new_left -= 1
                    elif tag == "-":
                        old_left -= 1
                    elif tag == "+":
                        new_left -= 1
                        if check_hooks and PYTEST_HOOK_RE.search(body[1:]):
                            violations.append(
                                f"{path}: added line defines a pytest hook or plugin (not allowed): {body[1:].strip()[:80]!r}"
                            )
                    elif tag != "\\":
                        break
                    i += 1
                if old_left != 0 or new_left != 0:
                    violations.append(f"{path}: hunk line counts do not match its header")
                    while i < n and not lines[i].startswith("diff --git "):
                        i += 1
                    break
                while i < n and lines[i].startswith("\\"):
                    i += 1
        elif i < n and lines[i].startswith("@@ "):
            violations.append(f"{path}: hunk without ---/+++ header")
            while i < n and not lines[i].startswith("diff --git "):
                i += 1

    seen: set[str] = set()
    for entry in files:
        if entry["path"] in seen:
            violations.append(f"{entry['path']}: appears more than once in the patch")
        seen.add(entry["path"])
    return files, violations


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: guard_patch.py <patch>", file=sys.stderr)
        return 2
    patch = Path(argv[1])
    try:
        data = patch.read_bytes()
    except OSError as exc:
        print(f"error: cannot read patch {patch}: {exc}", file=sys.stderr)
        return 2
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        print("VIOLATION: patch is not valid UTF-8 text (binary content is not allowed)")
        return 1
    if "\r" in text:
        print("VIOLATION: patch contains carriage returns")
        return 1

    files, violations = parse_patch(text)
    for violation in violations:
        print(f"VIOLATION: {violation}")
    if violations:
        print(f"guard_patch: rejected ({len(violations)} violation(s), {len(files)} file(s))", file=sys.stderr)
        return 1
    print(f"guard_patch: ok ({len(files)} file(s))", file=sys.stderr)
    for entry in files:
        print(f"{'added' if entry['new'] else 'modified'}\t{entry['path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
