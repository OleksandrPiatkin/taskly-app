## 🧪 Test agent report

**Decision:** {{decision}} — {{summary}}

| Suite | Result | Tests | Coverage before → after |
|---|---|---|---|
| Backend (pytest) | {{backend_status}} | {{backend_tests}} | {{backend_cov_before}}% → {{backend_cov_after}}% |
| Frontend (Vitest) | {{frontend_status}} | {{frontend_tests}} | lines {{fe_lines_before}}% → {{fe_lines_after}}%, branches {{fe_branches_before}}% → {{fe_branches_after}}% |

### Changed files
<!-- one line per analyzed file -->
- `{{path}}` → **{{test|update|skip}}** — {{reason}}

### Tests written
<!-- one line per created/updated test file -->
- `{{test_path}}` ({{added|updated}}) — covers {{what}}

### Findings
<!-- omit the section if empty -->
- `{{path}}:{{line}}` — {{issue}}
