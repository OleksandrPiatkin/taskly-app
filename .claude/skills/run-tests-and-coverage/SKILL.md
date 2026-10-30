---
name: run-tests-and-coverage
description: Run the Taskly backend (pytest) and/or frontend (Vitest + typecheck) test suites with coverage in the correct working directories and produce a machine-readable results file. Use to get a baseline, to verify new or updated tests, and before reporting.
---

# Run tests and coverage

Always use the script — it runs each suite from its package directory (so the right coverage config
is used), never stops at the first failing suite, and records real exit codes and numbers.

```sh
bash .claude/skills/run-tests-and-coverage/scripts/run_tests.sh all        # or: backend | frontend
bash .claude/skills/run-tests-and-coverage/scripts/run_tests.sh all baseline   # label the run
```

Output: `.agent-results/results-<label>.json` (default label `final`) plus per-suite logs
`.agent-results/<suite>-<label>.log`. Schema:

```json
{
  "label": "final",
  "backend":  {"status": "passed|failed|not_run", "exit_code": 0, "tests": 34, "failures": 0,
               "errors": 0, "skipped": 0, "coverage": {"total": 91.2}},
  "frontend": {"status": "passed", "exit_code": 0, "typecheck_exit_code": 0, "tests": 40,
               "failures": 0, "errors": 0, "skipped": 0, "coverage": {"lines": 88.1, "branches": 80.3}}
}
```

## How to use the results

- `status: failed` → read the suite log, find the failing test names, fix **tests you wrote**.
  Failures that also exist in the `baseline` run are pre-existing: report them, don't touch them.
- Compare `baseline` vs `final` coverage for the report; quote numbers exactly as written.
- Run a single file while iterating (commands in `CLAUDE.md`), but always finish with a full
  `all` run labelled `final` — that is the run the report and the CI workflow trust.
