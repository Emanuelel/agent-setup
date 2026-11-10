#!/usr/bin/env bash
# Fast checks for this project: formatting, lint, types, tests, plus project-specific rules.
# The checkpoint hook runs this when an agent tries to finish; agents run it before saying "done".
# Keep the whole run under ~2 minutes. Slow suites (end-to-end, full builds) belong in CI.
#
# Section 1 finds the standard tools this project already has and runs them.
# Section 2 holds project-specific checks: when the same mistake happens twice, add one there.

set -uo pipefail
cd "$(dirname "$0")/.."

FAILED=0
RAN=0

step() {  # step "name" "how to fix" command...
  local name="$1" fix="$2"; shift 2
  RAN=$((RAN + 1))
  echo "==> $name"
  if "$@"; then
    echo "    ok"
  else
    echo "    FAIL: $name"
    echo "    How to fix: $fix"
    FAILED=1
  fi
}

forbid() {  # forbid "regex" "why it's wrong and what to do instead" path...
  local pattern="$1" fix="$2"; shift 2
  local hits
  hits=$(grep -rEn --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.venv \
    --exclude-dir=dist --exclude-dir=build -- "$pattern" "$@" 2>/dev/null || true)
  RAN=$((RAN + 1))
  if [ -n "$hits" ]; then
    echo "==> project rule: $fix"
    echo "$hits" | head -20 | sed 's/^/    /'
    echo "    FAIL: remove the matches above. $fix"
    FAILED=1
  fi
}

has() { command -v "$1" >/dev/null 2>&1; }

# ---------------------------------------------------------------- 1. standard checks

# JavaScript / TypeScript (web, Expo / React Native, Node)
if [ -f package.json ]; then
  if [ -f pnpm-lock.yaml ]; then PM="pnpm"
  elif [ -f yarn.lock ]; then PM="yarn"
  elif [ -f bun.lockb ] || [ -f bun.lock ]; then PM="bun"
  else PM="npm"; fi

  script_cmd() {  # prints the npm script's command, if it exists
    python3 -c 'import json,sys; print(json.load(open("package.json")).get("scripts",{}).get(sys.argv[1],""))' "$1" 2>/dev/null
  }

  if [ -n "$(script_cmd lint)" ]; then
    step "lint" "fix each reported problem in the code; don't disable the rule or add ignore comments" \
      $PM run -s lint
  fi

  if [ -n "$(script_cmd typecheck)" ]; then
    step "types" "fix the type errors; don't use 'any', '@ts-ignore' or casts to silence them" \
      $PM run -s typecheck
  elif [ -f tsconfig.json ] && [ -x node_modules/.bin/tsc ]; then
    step "types" "fix the type errors; don't use 'any', '@ts-ignore' or casts to silence them" \
      node_modules/.bin/tsc --noEmit
  fi

  TEST_SCRIPT="test"; [ -n "$(script_cmd test:ci)" ] && TEST_SCRIPT="test:ci"
  TEST_CMD="$(script_cmd "$TEST_SCRIPT")"
  if [ -n "$TEST_CMD" ] && ! echo "$TEST_CMD" | grep -q "no test specified"; then
    if echo "$TEST_CMD" | grep -qi "watch"; then
      echo "==> tests skipped: the '$TEST_SCRIPT' script runs in watch mode. Add a 'test:ci' script without it."
    else
      step "tests" "make the failing tests pass by fixing the code; don't delete or weaken tests" \
        env CI=1 $PM run -s "$TEST_SCRIPT"
    fi
  fi
fi

# Python
if [ -f pyproject.toml ] || [ -f setup.py ] || ls requirements*.txt >/dev/null 2>&1; then
  BIN=""; [ -d .venv/bin ] && BIN=".venv/bin/"
  tool() { if [ -x "${BIN}$1" ]; then echo "${BIN}$1"; elif has "$1"; then echo "$1"; fi; }

  RUFF="$(tool ruff)"
  if [ -n "$RUFF" ]; then
    step "lint" "fix each reported problem; don't add '# noqa' to silence it" "$RUFF" check .
    step "format" "run '$RUFF format .' and keep the result" "$RUFF" format --check .
  fi

  MYPY="$(tool mypy)"
  if [ -n "$MYPY" ] && { [ -f mypy.ini ] || grep -q "^\[tool.mypy\]" pyproject.toml 2>/dev/null; }; then
    step "types" "fix the type errors; don't add '# type: ignore' to silence them" "$MYPY" .
  fi

  PY="python3"; [ -x .venv/bin/python ] && PY=".venv/bin/python"
  if [ -d tests ] && "$PY" -c "import pytest" >/dev/null 2>&1; then
    step "tests" "make the failing tests pass by fixing the code; don't delete or weaken tests" \
      "$PY" -m pytest -q -x
  fi
fi

# ---------------------------------------------------------------- 2. project-specific checks
# One line per rule, written so the error message teaches the fix. Examples:
#
# forbid "console\.log\(" "Use the logger in src/lib/log.ts instead of console.log." src
# forbid "from ['\"]\.\./\.\./db" "UI code must not import the database; go through src/api." src/ui
# forbid "@ts-ignore" "Fix the type error instead of ignoring it." src

# ---------------------------------------------------------------- result
if [ "$RAN" -eq 0 ]; then
  echo "verify.sh: no checks found for this project yet (see the project-docs skill to add some)."
  exit 0
fi
if [ "$FAILED" -ne 0 ]; then
  echo "verify.sh: FAILED. Fix the problems above, then run scripts/verify.sh again."
  exit 1
fi
echo "verify.sh: all checks passed ($RAN)."
