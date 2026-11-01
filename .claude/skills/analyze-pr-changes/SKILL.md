---
name: analyze-pr-changes
description: Classify changed files in the Taskly repo (frontend/backend/test/skip), map each source file to its expected test file, and decide whether new or updated unit tests are warranted. Use at the start of any PR test-generation or coverage task.
---

# Analyze PR changes

## 1. Get the facts deterministically

PR mode (diff against a base ref):

```sh
python3 .claude/skills/analyze-pr-changes/scripts/changed_files.py --base origin/main
```

Coverage mode (explicit files or directories, no diff):

```sh
python3 .claude/skills/analyze-pr-changes/scripts/changed_files.py --files backend/app frontend/src/lib
```

The script prints JSON and also writes it to `.agent-results/changes.json`:

- `backend.source` / `frontend.source` — testable source files, each with `test_path` and `test_exists`
- `backend.indirect` — schemas/models: excluded from coverage, but behaviour changes must be tested
  through the code that uses them (usually `test_router.py`)
- `backend.tests` / `frontend.tests` — test files the PR already touched
- `skipped` — files out of scope, each with a `reason`
- `deleted` — removed files (check whether their tests should be removed too; report, do not delete)
- `preexisting_changes` — files already modified/untracked in the working tree before you started.
  They are not your work: never edit them unless they are test files you were asked to cover, and
  never list them in the report as yours. Run this script **before** writing anything.

Do not reclassify files by hand; if the script is wrong, report it.

## 2. Decide per file

Read the diff for each source file (`git diff <base>...HEAD -- <path>`) and the existing test file.

Write or update tests when the change adds or alters **behaviour**: new function/endpoint/component/
hook, changed branch or condition, changed validation, error handling, data mapping, or API contract.

Do not write tests when the change is only: formatting, renames without behaviour change, comments,
types-only edits, styling, stories, or when the PR already includes adequate tests for it
(check that the touched test file actually exercises the changed lines).

## 3. Output

Keep a short decision list for the report — one line per file:
`<path> → test | update | skip — <reason>`. If every file is `skip`, the overall decision is
`no_tests_needed`.
