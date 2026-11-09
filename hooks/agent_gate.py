#!/usr/bin/env python3
"""Checkpoint ("stop") hook shared by Codex and Claude Code.

Runs every time the agent tries to finish a turn. It can send the agent back once
(per turn) for three reasons, checked in this order:

  1. Checks are red: the project has scripts/verify.sh and it fails on the current changes.
  2. Big change not yet reviewed: ~150+ changed code lines since the last review.
  3. Docs not updated: code changed but docs/CHANGELOG.md wasn't touched.

Design rules (from common best practice):
  - Never loops: if the agent is already continuing because of this hook, let it stop.
  - Fails open: any error, missing git, or unclear situation lets the agent stop.
  - Only reacts to real code changes; a turn that only answered a question passes.
State is kept inside the project's .git folder, so it never adds files to your code.
"""
import hashlib
import json
import os
import subprocess
import sys

REVIEW_THRESHOLD = int(os.environ.get("AGENT_GATE_REVIEW_LINES", "150"))
CHANGELOG_THRESHOLD = int(os.environ.get("AGENT_GATE_CHANGELOG_LINES", "20"))
VERIFY_TIMEOUT = int(os.environ.get("AGENT_GATE_VERIFY_TIMEOUT", "180"))
VERIFY_SCRIPT = os.path.join("scripts", "verify.sh")

# Changes to these don't count as "code" for line counting.
NON_CODE_PREFIXES = ("docs/",)
NON_CODE_SUFFIXES = (".md", ".lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock")


def allow():
    print("{}")
    sys.exit(0)


def block(reason):
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


def git(root, *args, check=True):
    r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        return None
    return r.stdout


def is_code(path):
    return not (path.startswith(NON_CODE_PREFIXES) or path.endswith(NON_CODE_SUFFIXES))


def snapshot(root):
    """Return (fingerprint, changed_code_lines, changed_paths) for uncommitted work."""
    h = hashlib.sha256()
    lines = 0
    paths = set()

    numstat = git(root, "diff", "HEAD", "--numstat") or ""
    for row in numstat.splitlines():
        parts = row.split("\t")
        if len(parts) != 3:
            continue
        added, removed, path = parts
        paths.add(path)
        if is_code(path) and added.isdigit() and removed.isdigit():
            lines += int(added) + int(removed)
    h.update((git(root, "diff", "HEAD") or "").encode())

    untracked = git(root, "ls-files", "--others", "--exclude-standard") or ""
    for path in untracked.splitlines():
        paths.add(path)
        full = os.path.join(root, path)
        try:
            with open(full, "rb") as f:
                data = f.read(2_000_000)
        except OSError:
            continue
        h.update(path.encode() + b"\0" + data)
        if is_code(path):
            lines += data.count(b"\n")
    return h.hexdigest(), lines, paths


def load_state(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(path, state):
    try:
        with open(path, "w") as f:
            json.dump(state, f)
    except OSError:
        pass


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        allow()

    if event.get("stop_hook_active"):
        allow()  # already sent back once this turn: let it finish

    cwd = event.get("cwd") or os.getcwd()
    root = (git(cwd, "rev-parse", "--show-toplevel") or "").strip()
    git_dir = (git(cwd, "rev-parse", "--absolute-git-dir") or "").strip()
    if not root or not git_dir or git(root, "rev-parse", "--verify", "HEAD") is None:
        allow()  # not a git project, or no first commit yet

    fingerprint, lines, paths = snapshot(root)
    if lines == 0:
        allow()  # no code changes

    state_path = os.path.join(git_dir, "agent-gate.json")
    state = load_state(state_path)

    # 1. Fast checks
    verify = os.path.join(root, VERIFY_SCRIPT)
    if os.path.isfile(verify) and state.get("verified") != fingerprint:
        try:
            r = subprocess.run(["bash", verify], cwd=root, capture_output=True,
                               text=True, timeout=VERIFY_TIMEOUT)
            ok, output = r.returncode == 0, (r.stdout + r.stderr)
        except subprocess.TimeoutExpired:
            ok, output = True, ""  # too slow to judge here: fail open
        if not ok:
            tail = "\n".join(output.strip().splitlines()[-60:])
            block("Checkpoint: the project's fast checks (scripts/verify.sh) are failing on "
                  "your changes. Fix the cause (don't delete or weaken tests), run "
                  "scripts/verify.sh again, then finish.\n\nLast output:\n" + tail)
        state["verified"] = fingerprint

    reasons = []

    # 2. Independent review of big changes
    reviewed_lines = state.get("reviewed_lines", 0)
    if lines < reviewed_lines:
        reviewed_lines = 0  # work was committed or reverted since the last review
    if lines - reviewed_lines >= REVIEW_THRESHOLD:
        reasons.append(
            f"About {lines - reviewed_lines} lines of code changed since the last review. "
            "Ask the `reviewer` agent to review the uncommitted changes. Give it ONLY the "
            "user's original request (in their words) and tell it to review `git diff HEAD` "
            "plus new files; do not pass your plan. Fix critical/high findings, list the rest "
            "for the user, max 2 review rounds.")
        state["reviewed_lines"] = lines
    else:
        state["reviewed_lines"] = reviewed_lines

    # 3. Docs upkeep
    changelog = os.path.join(root, "docs", "CHANGELOG.md")
    if (os.path.isfile(changelog) and lines >= CHANGELOG_THRESHOLD
            and "docs/CHANGELOG.md" not in paths
            and state.get("doc_nudged") != fingerprint):
        reasons.append("Code changed but docs/CHANGELOG.md wasn't updated. Add a CHANGELOG "
                       "line and update docs/STATUS.md (and docs/DECISIONS.md if a real "
                       "choice was made).")
        state["doc_nudged"] = fingerprint

    save_state(state_path, state)
    if reasons:
        block("Checkpoint before finishing:\n- " + "\n- ".join(reasons))
    allow()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        allow()  # never wedge a session because of this hook
