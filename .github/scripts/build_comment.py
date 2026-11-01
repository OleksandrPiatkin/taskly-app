#!/usr/bin/env python3
"""Compose the sticky PR comment for the test agent.

Usage:
  build_comment.py [--report report.md] [--verify verify.json] [--tests tests-results.json]
                   [--plain-tests-status passed|failed|skipped|cancelled]
                   [--bot-pr-url URL] [--run-url URL] [--reason TEXT [--outcome skipped|failed]]
                   > comment.md

  --report   the agent's report.md (untrusted LLM output; sanitized and truncated)
  --verify   check_decision.py output, merged in CI with results-verify.json and the guard result
             ("ok" must already be check.ok and guard_exit == 0)
  --tests    CI re-verification results, schema of run_tests.sh (results-<label>.json);
             if omitted, the "backend"/"frontend" results are read from --verify
  --plain-tests-status  result of the plain (existing tests) CI job, e.g. needs.<job>.result
  --reason   why the agent did not run or failed (shown at the top)
  --outcome  requires --reason; sets the headline explicitly when the agent was not run or failed:
             skipped -> "ℹ️ No testable changes — test agent not run", failed -> ❌.
             The "⚠️ This PR breaks existing tests" banner is still shown whenever
             --plain-tests-status is failure (or verify.json reports a broken existing test).

Inputs that are missing or unreadable are treated as "not available", so the script can also
be used when the agent did not run. The status banner is derived only from --verify, --tests and
--plain-tests-status, never from the report.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MARKER = "<!-- test-agent-report -->"
REPORT_LIMIT = 50_000
ZWSP = "​"

FENCE_RE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})")
# Inline code may wrap lines but never spans a blank line (a paragraph break ends it on GitHub).
INLINE_CODE_RE = re.compile(r"(`+)((?:(?!\n[ \t]*\n).)+?)\1", re.DOTALL)
HTML_COMMENT_RE = re.compile(r"<!--.*?(?:-->|\Z)", re.DOTALL)
HTML_TAG_RE = re.compile(r"</?[A-Za-z][^>]*>|<![A-Za-z][^>]*>|<\?.*?\?>", re.DOTALL)
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)|!\[[^\]]*\]\[[^\]]*\]")
MENTION_RE = re.compile(r"@(?=[A-Za-z0-9_-])")


def load_json(path: str | None) -> dict | None:
    if not path:
        return None
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"warning: ignoring {path}: {exc}", file=sys.stderr)
        return None
    return data if isinstance(data, dict) else None


def strip_html(text: str) -> str:
    """Remove HTML comments, tags and images from prose; neutralize any remaining '<'."""
    text = HTML_COMMENT_RE.sub("", text)
    text = HTML_TAG_RE.sub("", text)
    text = IMAGE_RE.sub("", text)
    return text.replace("<", "&lt;")


def sanitize_prose(text: str) -> str:
    # Inline code is shown literally by GitHub, so keep it; clean only the text between spans.
    out, pos = [], 0
    for m in INLINE_CODE_RE.finditer(text):
        out.append(strip_html(text[pos : m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(strip_html(text[pos:]))
    return "".join(out)


def sanitize_markdown(text: str) -> str:
    """Strip raw HTML and images outside code blocks, neutralize @mentions everywhere."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\0", "")
    chunks, prose, fence = [], [], None
    for line in text.split("\n"):
        m = FENCE_RE.match(line)
        if fence is None and m:
            if prose:
                chunks.append(sanitize_prose("\n".join(prose)))
            prose, fence = [], m.group(1)
            chunks.append(line)
        elif fence is not None:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and line.strip() == m.group(1):
                fence = None
            chunks.append(line)
        else:
            prose.append(line)
    if prose:
        chunks.append(sanitize_prose("\n".join(prose)))
    if fence is not None:
        chunks.append(fence)  # close an unterminated code block so it cannot swallow the footer
    text = "\n".join(chunks)
    return MENTION_RE.sub("@" + ZWSP, text)


def truncate(text: str, limit: int = REPORT_LIMIT) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    fences = [FENCE_RE.match(line) for line in cut.split("\n")]
    open_fence = sum(1 for m in fences if m) % 2 == 1
    return cut + ("\n```" if open_fence else "") + "\n\n_… report truncated; see the workflow run for the full text._"


def tests_state(tests: dict | None) -> str:
    """'passed' | 'failed' | 'not_run' for the CI re-verification run."""
    if not tests:
        return "not_run"
    statuses = [tests.get(s, {}).get("status") for s in ("backend", "frontend") if isinstance(tests.get(s), dict)]
    if any(s == "failed" for s in statuses):
        return "failed"
    if any(s == "passed" for s in statuses):
        return "passed"
    return "not_run"


def build(args: argparse.Namespace) -> str:
    verify = load_json(args.verify)
    # verify.json is check_decision.py output merged with results-verify.json, so it can carry the
    # suite results too; an explicit --tests file wins.
    tests = load_json(args.tests) if args.tests else verify
    rerun = tests_state(tests)
    decision = verify.get("decision") if verify else None
    verify_ok = bool(verify and verify.get("ok") is True)
    plain_failed = args.plain_tests_status == "failed"
    finding_breaks = bool(verify and verify.get("breaks_existing_tests") is True)
    breaks = plain_failed or finding_breaks

    if args.outcome == "skipped":
        icon, headline = "ℹ️", "No testable changes — test agent not run"
    elif args.outcome == "failed":
        icon, headline = "❌", "Test agent failed"
    elif verify is not None and not verify_ok:
        icon, headline = "❌", "Test agent output failed verification"
    elif rerun == "failed":
        icon, headline = "❌", "Tests failed when re-run in CI"
    elif decision == "failed":
        icon, headline = "❌", "Test agent could not finish"
    elif verify is None:
        icon, headline = "⚠️", "Test agent produced no verified result"
    elif breaks:
        icon, headline = "⚠️", "Test agent finished, but existing tests are affected"
    elif decision == "no_tests_needed":
        icon, headline = "✅", "No new tests needed"
    else:
        icon, headline = "✅", "Tests generated and verified"

    parts = [MARKER, f"### {icon} {headline}"]
    if breaks:
        why = []
        if plain_failed:
            why.append("The existing test suite fails on this PR.")
        if finding_breaks:
            why.append("The test agent had to update existing tests; see the findings below.")
        parts.append("> [!WARNING]\n> **⚠️ This PR breaks existing tests.** " + " ".join(why) + " Details are in the workflow run.")
    if verify and not verify_ok:
        errors = [sanitize_markdown(str(e))[:300] for e in (verify.get("errors") or [])[:10]]
        if verify.get("guard_ok") is False:
            errors.insert(0, "the patch was rejected by guard_patch.py (outside allowed test paths or a forbidden change); see the workflow run")
        if not errors:
            errors.append("see the workflow run")
        parts.append("**Verification errors:**\n" + "\n".join(f"- {e}" for e in errors))
    if args.reason:
        parts.append(f"**Reason:** {sanitize_markdown(args.reason)[:1000]}")

    report = None
    if args.report:
        try:
            report = Path(args.report).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"warning: ignoring report {args.report}: {exc}", file=sys.stderr)
    if report and report.strip():
        parts.append("---\n\n" + truncate(sanitize_markdown(report.strip())))
    elif not args.reason:
        parts.append("_No agent report available._")

    footer = []
    if args.bot_pr_url:
        footer.append(f"**Proposed tests:** {args.bot_pr_url}")
    footer.append(f"**Independently re-verified in CI:** {rerun.replace('_', ' ')}")
    if args.run_url:
        footer.append(f"[Workflow run]({args.run_url})")
    footer.append("Generated tests are proposed in a separate PR for human review.")
    parts.append("---\n\n<sub>" + " · ".join(footer) + "</sub>")
    return "\n\n".join(parts) + "\n"


def https_url(value: str) -> str:
    if not re.fullmatch(r"https://[A-Za-z0-9.-]+(/[A-Za-z0-9._~%/?#&=+:@!$,;-]*)?", value):
        raise argparse.ArgumentTypeError(f"not a plain https URL: {value!r}")
    return value


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Compose the sticky test-agent PR comment.")
    parser.add_argument("--report")
    parser.add_argument("--verify")
    parser.add_argument("--tests")
    parser.add_argument("--plain-tests-status", choices=["success", "passed", "failure", "failed", "skipped", "cancelled"])
    parser.add_argument("--bot-pr-url", type=https_url)
    parser.add_argument("--run-url", type=https_url)
    parser.add_argument("--reason")
    parser.add_argument("--outcome", choices=["skipped", "failed"])
    args = parser.parse_args(argv[1:])
    if args.outcome and not (args.reason and args.reason.strip()):
        parser.error("--outcome requires --reason")
    # Accept GitHub job results (success/failure) as well as passed/failed.
    args.plain_tests_status = {"success": "passed", "failure": "failed"}.get(args.plain_tests_status, args.plain_tests_status)
    sys.stdout.write(build(args))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
