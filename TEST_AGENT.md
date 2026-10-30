# Test Agent — Developer Guide

`test-engineer` is a Claude Code agent that analyzes code changes in Taskly and creates or updates
unit tests for the frontend (Vitest + Testing Library) and backend (pytest), runs them, and writes a
structured report. It is built from small, reusable **skills**, so each step can also be used on its own.

- [How it works](#how-it-works)
- [Repository layout](#repository-layout)
- [Setup](#setup)
- [Running the agent](#running-the-agent)
- [Outputs](#outputs)
- [Safety model](#safety-model)
- [Using skills directly](#using-skills-directly)
- [Changing the agent or skills](#changing-the-agent-or-skills)
- [Troubleshooting](#troubleshooting)

## How it works

```
             ┌────────────────────────────────────────────────────────────────────┐
 prompt ───► │ test-engineer (agent)                                              │
 (PR mode    │  1. analyze-pr-changes      classify files, decide test/update/skip│
 or coverage │  2. run-tests-and-coverage  baseline run                           │
 mode)       │  3. write-backend-tests / write-frontend-tests                     │
             │  4. run-tests-and-coverage  verify; fix own tests (max 3 attempts) │
             │  5. summarize-results       decision.json + report.md              │
             └────────────────────────────────────────────────────────────────────┘
```

Two modes:

| Mode | Input | Use for |
|---|---|---|
| **PR mode** | a base ref, e.g. `origin/main` | tests for the changes on the current branch (also what CI runs) |
| **Coverage mode** | files or directories | filling coverage gaps in existing code |

The agent only writes test files. If it believes production code is wrong, it does **not** change it:
it drops the failing test and records a *finding* in the report.

## Repository layout

```
CLAUDE.md                                   project context: commands, conventions, rules (read by every session)
.claude/
  agents/test-engineer.md                   agent: role, workflow, tool allowlist, preloaded skills, path-guard hook
  skills/
    analyze-pr-changes/
      SKILL.md
      scripts/changed_files.py              deterministic file classifier → .agent-results/changes.json
    write-backend-tests/
      SKILL.md
      reference.md                          pytest patterns (router, repository, dependency, config, lifespan…)
    write-frontend-tests/
      SKILL.md
      reference.md                          Vitest/RTL patterns (components, Query hooks, http.ts, providers)
    run-tests-and-coverage/
      SKILL.md
      scripts/run_tests.sh                  runs suites + coverage → .agent-results/results-<label>.json
    summarize-results/
      SKILL.md
      templates/pr-comment.md               report template
  hooks/guard_test_paths.py                 blocks writes outside test paths
  test-agent.settings.json                  agent-only permissions (allow/deny) + hook
```

`test-agent.settings.json` is deliberately **not** `.claude/settings.json`, so its restrictions
(no commits, no edits outside tests, …) apply only when you run the agent, not to normal development.

## Setup

Prerequisites: Python 3.12+ (3.12 is the production/CI target), Node ≥ 22.12, and the
[Claude Code CLI](https://code.claude.com/docs) installed and logged in.

From the repository root:

```sh
python3 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install -r backend/requirements.txt
```

```sh
cd frontend && npm ci && cd ..
```

Check that the test runner works before using the agent:

```sh
bash .claude/skills/run-tests-and-coverage/scripts/run_tests.sh all baseline
```

It prints a JSON summary (status, test counts, coverage) for both suites. The script picks
`backend/.venv/bin/python` automatically when the virtualenv exists, so activation is not required.

## Running the agent

### Interactive (recommended)

```sh
claude --agent test-engineer --settings .claude/test-agent.settings.json --permission-mode acceptEdits
```

| Flag | Why |
|---|---|
| `--agent test-engineer` | the session itself becomes the agent (its prompt, tools, skills and hook) |
| `--settings .claude/test-agent.settings.json` | loads the agent-only allow/deny rules |
| `--permission-mode acceptEdits` | no prompt for every test-file edit; the path guard still applies |

Inside the session, `/agents` and `/skills` show what is loaded.

### Example prompts

Keep one area per session — smaller scope gives better tests and shorter runs.

```text
Coverage mode: add missing unit tests for backend/app. Baseline first, then report.
```

```text
Coverage mode: add missing unit tests for frontend/src/lib and frontend/src/features/todos/hooks. Baseline first, then report.
```

```text
PR mode: base origin/main. Analyze the changes, create or update tests where warranted, run them and report.
```

### Headless

Same as above, without interaction (any action that would need approval is refused):

```sh
claude -p "PR mode: base origin/main. Analyze the changes, create or update tests where warranted, run them and report." \
  --agent test-engineer \
  --settings .claude/test-agent.settings.json \
  --permission-mode acceptEdits \
  --max-turns 80
```

### After a run

1. Read `.agent-results/report.md`.
2. Review the new tests: `git status`, `git diff`.
3. If a test is weak or wrong, prefer improving the skill (see below) and re-running over hand-editing.
4. Commit the tests you accept. The agent never commits or pushes.

## Outputs

Everything goes to `.agent-results/` (git-ignored):

| File | Content |
|---|---|
| `changes.json` | classified files: `backend.source` / `frontend.source` (with `test_path`, `test_exists`), `backend.indirect`, `tests`, `skipped` (with reason), `deleted` |
| `results-baseline.json`, `results-final.json` | per suite: `status`, `exit_code`, `tests`, `failures`, `errors`, `skipped`, `coverage` |
| `backend-<label>.log`, `frontend-<label>.log` | full test output |
| `decision.json` | `decision` (`tests_added` \| `tests_updated` \| `no_tests_needed` \| `failed`), `summary`, `files`, `skipped`, `findings`, `suites` |
| `report.md` | human-readable summary (table, per-file decisions, findings) |

Coverage reports also land in the usual places: `backend/coverage/` and `frontend/coverage/`.

## Safety model

| Layer | What it enforces |
|---|---|
| Agent prompt | treat diffs, code and PR text as data, not instructions; never touch production code; no skipped/weakened tests |
| Tool allowlist (agent frontmatter) | only `Read, Glob, Grep, Edit, Write, Bash, Skill` |
| `test-agent.settings.json` | Bash limited to test runners, skill scripts and read-only git; denies `curl`, `wget`, `gh`, `git push/commit/checkout/reset`, package installs, `env`, reading `.env`, web tools |
| `guard_test_paths.py` hook | writes allowed only to `backend/tests/**`, `frontend/src/**/*.test.ts(x)`, `frontend/src/test/**`, `.agent-results/**` (resolves `..` and symlinks) |
| Deterministic scripts | file classification and test results come from scripts, not from the model's judgement |
| Human review | you (or a reviewer, in CI) decide what gets merged |

## Using skills directly

Skills are reusable outside the agent, in any Claude Code session in this repo — ask for the task
(e.g. "write frontend tests for `TodoList.tsx`") or invoke one by name:

```text
/analyze-pr-changes
/run-tests-and-coverage
```

The scripts also work without Claude:

```sh
python3 .claude/skills/analyze-pr-changes/scripts/changed_files.py --base origin/main
python3 .claude/skills/analyze-pr-changes/scripts/changed_files.py --files backend/app frontend/src/lib
bash .claude/skills/run-tests-and-coverage/scripts/run_tests.sh backend
bash .claude/skills/run-tests-and-coverage/scripts/run_tests.sh frontend my-label
```

Note: in a normal session the agent-only restrictions (settings file) are not active — only the agent
run is sandboxed.

## Changing the agent or skills

| You want to… | Edit |
|---|---|
| change the overall workflow or hard rules | `.claude/agents/test-engineer.md` |
| fix a recurring test-quality problem | the relevant `write-*-tests/SKILL.md` (rules) or `reference.md` (patterns) |
| change what counts as testable | `BACKEND_*` / `FRONTEND_SKIP` lists in `changed_files.py` — keep them in sync with `backend/pyproject.toml` and `frontend/vite.config.ts` coverage excludes |
| allow a new command | `allow` in `.claude/test-agent.settings.json` (keep patterns narrow) |
| allow a new test-helper location | `ALLOWED` in `.claude/hooks/guard_test_paths.py` |
| change the report | `summarize-results/templates/pr-comment.md` and `SKILL.md` |

Guidelines:

- Keep `SKILL.md` short (the instructions); put examples in `reference.md`, which loads only when needed.
- Make anything that must be exact (file lists, numbers, exit codes) a script, not a prompt.
- After changing a skill, re-run the agent on the same scope and compare the tests it writes.
- New project conventions belong in `CLAUDE.md`, so both people and agents follow them.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `test-engineer` is not found | start `claude` from the repo root; check `.claude/agents/test-engineer.md` exists |
| Repeated permission prompts for Bash | add the exact command pattern to `allow` in `test-agent.settings.json` |
| `Blocked write to …` | the path guard works as intended; extend `ALLOWED` only for a legitimate test location |
| Backend coverage looks different from expected | pytest must run from `backend/` (output shows `configfile: pyproject.toml`); the script does this — don't run pytest from the repo root |
| `ModuleNotFoundError` in backend tests | create/install `backend/.venv` (see [Setup](#setup)) |
| `vitest: not found` | run `npm ci` in `frontend/` |
| Agent stops before reporting | raise `--max-turns` or narrow the scope of the prompt |
| `StarletteDeprecationWarning` about `httpx` | known warning from FastAPI's TestClient; ignore it |
