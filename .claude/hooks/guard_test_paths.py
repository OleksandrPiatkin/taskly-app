#!/usr/bin/env python3
"""PreToolUse hook: allow file writes only to test paths and the agent results folder.

Exit code 2 blocks the tool call and shows stderr to Claude.
"""

import json
import os
import sys
from fnmatch import fnmatch
from pathlib import Path

ALLOWED = [
    "backend/tests/*.py",
    "frontend/src/*.test.ts",
    "frontend/src/*.test.tsx",
    "frontend/src/test/*",
    ".agent-results/*",
]

event = json.load(sys.stdin)
tool_input = event.get("tool_input", {})
raw = tool_input.get("file_path") or tool_input.get("notebook_path")
if not raw:
    sys.exit(0)

root = Path(os.environ.get("CLAUDE_PROJECT_DIR", event.get("cwd", "."))).resolve()
target = (root / raw).resolve()  # absolute paths stay absolute; '..' and symlinks are resolved

if target.is_relative_to(root):
    rel = target.relative_to(root).as_posix()
    if any(fnmatch(rel, pattern) for pattern in ALLOWED):
        sys.exit(0)

print(
    f"Blocked write to {raw}: the test agent may only write test files "
    f"({', '.join(ALLOWED)}). Report production-code issues as findings instead.",
    file=sys.stderr,
)
sys.exit(2)
