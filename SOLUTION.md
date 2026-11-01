# Solution

A Claude Code agent (`test-engineer`) with five reusable skills. It writes and updates unit tests for the frontend and backend, both for existing code and for code changed in a pull request. On every PR it analyzes the diff, writes tests where warranted, runs them, has CI re-verify them, opens a bot PR with the tests, and posts the results as a comment.

Coverage of the existing app:

| | Before | After |
|---|---|---|
| Backend (pytest) | 21 tests, 42.42% | 72 tests, 100% |
| Frontend (Vitest) | 18 tests, 47.68% lines, 43.79% branches | 108 tests, 98.67% lines, 98.54% branches |

## Technical decisions

| Decision | Rationale |
|---|---|
| Claude Code + `anthropics/claude-code-action` | Native skills and subagents. The action checks that the PR author has write access and loads `.claude/` and `CLAUDE.md` from `main`, so a PR cannot change its own agent. |
| One agent, five skills | The agent orchestrates; the skills hold the domain knowledge and can be used on their own. |
| Scripts for facts, model for judgement | Changed files, test results and coverage come from scripts. The model decides what to test and writes the tests. |
| The model's job has a read-only token | It gets `contents: read` and only the Claude secret. The jobs that write never run the model. |
| Independent verification | A job with no secrets checks that the patch touches only test files and matches `decision.json`, then re-runs the tests. |
| Trusted CI scripts | Every job runs `.github/scripts` and `run_tests.sh` from `main` (extracted with `git archive`, run with `python3 -I`), never the PR's copies. |
| Untrusted agent output | The comment builder strips HTML and images, neutralises `@mentions` and truncates the report before posting. |
| Bot PR, not commits to the author's branch | Generated tests go through human review. |
| Plain test job without AI | The PR's red or green status does not depend on the agent. |

## Running the PR workflow

Prerequisites:
- secret `CLAUDE_CODE_OAUTH_TOKEN` (create it with `claude setup-token`)
- Settings → Actions → General → Workflow permissions: "Read repository contents and packages
  permissions", with "Allow GitHub Actions to create and approve pull requests" turned on
  (check: `gh api repos/<owner>/<repo>/actions/permissions/workflow` returns
  `"default_workflow_permissions":"read","can_approve_pull_request_reviews":true`)
- `.claude/`, `CLAUDE.md` **and `.github/scripts/`** merged into `main` before the workflow runs:
  every job runs the base branch's copies, so a PR that adds them together with the workflow fails
  in its own run (this happened on the PR that introduced the workflow)

Trigger: a pull request into `main` from a branch in this repository; it runs again on every push. Drafts, forks and `agent/*` branches are skipped.

Output on the PR:
- one sticky comment with the decision per file, test results, coverage and findings
- a bot PR `agent/tests-pr-<N>`, when tests were added
- check statuses and a job summary
- an artifact with logs and `decision.json`

Local run (details in [`docs/TEST_AGENT.md`](docs/TEST_AGENT.md)):
```sh
claude --agent test-engineer --settings .claude/test-agent.settings.json --permission-mode acceptEdits
```

## Agent and skills

```
CLAUDE.md                            project commands and test rules
.claude/agents/test-engineer.md      agent: workflow, tools, preloaded skills, hooks
.claude/skills/analyze-pr-changes    classify changed files; decide test/update/skip (changed_files.py)
.claude/skills/write-backend-tests   pytest patterns
.claude/skills/write-frontend-tests  Vitest + Testing Library patterns
.claude/skills/run-tests-and-coverage run suites, write results JSON (run_tests.sh)
.claude/skills/summarize-results     write decision.json and report.md
.claude/hooks/guard_test_paths.py    block writes outside test files
.claude/test-agent.settings.json     command allow/deny list
.github/workflows/agent-tests.yml    PR workflow
.github/scripts/                     patch guard, decision check, comment builder
```

| Job | Does |
|---|---|
| `analyze` | runs `changed_files.py`; if nothing is testable, the AI step is skipped |
| `tests` | runs `run_tests.sh` on the PR, without AI |
| `generate` | runs the agent: analyze-pr-changes → run-tests-and-coverage (baseline) → write-backend/frontend-tests → run-tests-and-coverage (final) → summarize-results |
| `verify` | runs `guard_patch.py` and `check_decision.py`, then re-runs the tests with the patch applied |
| `publish` | commits the patch and opens or updates the bot PR |
| `report` | builds and posts the sticky comment |

## Example run

PR [#3](https://github.com/OleksandrPiatkin/taskly-app/pull/3) (`feature/demo-simple-components`) adds `GET /api/todos/count` and `ClearSearchButton`, with no tests.

| Job | Result |
|---|---|
| `analyze` | 3 files changed: `router.py` (source), `schemas.py` (indirect), `ClearSearchButton.tsx` (source, no test file) |
| `tests` | passed (the PR's own suites, without AI) |
| `generate` | `tests_added`, no findings |
| `verify` | patch guard and decision check passed; tests re-run and passed |
| `publish` | bot branch `agent/tests-pr-3`, bot PR into `feature/demo-simple-components` |
| `report` | sticky comment on PR #3 |

Agent decisions:

| File | Decision |
|---|---|
| `router.py` | update: new endpoint |
| `schemas.py` | skip: excluded from coverage, tested via the router |
| `ClearSearchButton.tsx` | add: new component |

Skills used: analyze-pr-changes → run-tests-and-coverage (baseline) → write-backend-tests, write-frontend-tests → run-tests-and-coverage (final) → summarize-results.

Tests written (+43 lines, 2 files):
- `test_router.py`: count with mixed tasks (`{"total": 3, "completed": 2}`), and with no tasks. It also asserts that `repository.get` is not called, so `/count` is not captured by `/{todo_id}`.
- `ClearSearchButton.test.tsx`: enabled and calls `onClear` when the search has text; disabled and inert for `''` and `'   '`.

| Suite | Result | Tests | Coverage |
|---|---|---|---|
| Backend | passed | 74 | 98.82% → 100% |
| Frontend | passed | 111 | lines 98.02% → 98.68%, branches 98.54% |

Links: [bot PR #7](https://github.com/OleksandrPiatkin/taskly-app/pull/7) · [sticky comment](https://github.com/OleksandrPiatkin/taskly-app/pull/3) · [workflow runs](https://github.com/OleksandrPiatkin/taskly-app/actions/workflows/agent-tests.yml?query=branch%3Afeature%2Fdemo-simple-components)

Found along the way:
- An earlier run on the same PR (before `main` was merged into it) caught the PR breaking `test_factory.py`, which asserted the exact route list. The agent fixed the test without saying so. Since then, every baseline failure must be reported as a finding, and the skills require membership assertions instead of exact lists.

## Assumptions

- PRs come from collaborators with write access to this repository.
- Unit tests only; both suites are fully mocked.
- Python 3.12 and Node 22.
- A person reviews every generated test before it is merged.

## Limitations

- Output is not deterministic. CI guarantees that the tests pass and touch only test files, not that they are optimal.
- The agent cannot rename or delete tests, or change product code. Suspected bugs are reported as findings.
- The bot PR triggers no CI, because GitHub runs no workflows for PRs created with `GITHUB_TOKEN`. Its tests were already re-run in `verify`.
- The agent's job runs PR code while holding the Claude token, which is why forks are excluded.
- The patch guard blocks known ways for generated tests to tamper with the test run (pytest hooks, `setup.ts`). Pattern rules can't be exhaustive; the bot-PR review and the agent-free `tests` job are the backstops.
- Tests for PRs that modify `.github/workflows/` are verified but not published: `GITHUB_TOKEN` cannot push workflow changes.
- `main` has no branch protection in this demo repository; the agent-free `tests` job is not yet a required check.
- The transcript is hidden, because the repository is public.
- Subscription rate limits apply, and the run is capped by turn and time limits.

## Production changes

- A GitHub App or workload identity federation instead of a personal token, with budgets and metrics.
- An ephemeral, sandboxed runner with an outbound network allowlist.
- Mutation testing, to check test quality beyond coverage.
- A set of fixture PRs that is run whenever a skill changes.
- Branch protection on `main` with the agent-free `tests` job as a required check.
- An `@test-agent` comment trigger, an opt-out label, CODEOWNERS and a required check for `agent/*` PRs, and signed commits.
- Fork support through a maintainer-approved `workflow_run` flow.
