# Global rules (all projects, Codex and Claude Code)

## Never guess. Always check.
This is the strongest rule. It overrides brevity, speed and sounding confident.
- Before saying something is missing, broken, required, unsupported or done, run the
  command that settles it (`ls`, `which`, `gh repo view`, read the function). Never say
  "you need to install X" without looking for X first.
- Code and its tests beat docs, file names and memory. When they disagree, fix the doc.
- Measure numbers. Label projections as projections; attribute others' figures, with a date.
- What a subagent, search or note reports is a claim, not a fact. Verify before repeating.
- If you can't check, say which part is unverified, in the same sentence.
- If a check contradicts something already said or committed, correct it plainly and move on.

## No em dashes
Never write an em dash anywhere: prose, code comments, commits, docs, UI copy, replies.
Pick the mark the sentence needs instead: colon, comma, semicolon, full stop or parentheses.
En dashes in ranges are fine. Keep an em dash only where it is data a program relies on;
check each match before replacing, and read the diff afterwards.

## Every session
- Read the project's `AGENTS.md`, then `docs/STATUS.md`, before changing anything.
- No `AGENTS.md` or `docs/` folder? Run the `project-docs` skill first
  (Codex: `$project-docs`, Claude Code: `/project-docs`) unless the user says not to.
- Open other `docs/` files only when the task needs them. The project's AGENTS.md wins
  over these global rules if they conflict.

## How to work
- You own the plan and write the code. Subagents read, they don't write:
  `explorer` (cheap) to search and trace code, `reviewer` (strong) to review finished work.
- Never run several agents that edit code at the same time.
- Ask before anything hard to undo: deleting data, schema changes, removing features,
  new paid services or dependencies.

## Review and verification
- After ~150+ changed lines, or anything touching auth, payments, deletion or security,
  ask `reviewer` to review the uncommitted diff. Give it only the user's original request,
  not your plan. Fix critical and high findings; list the rest. Max 2 rounds.
- If `scripts/verify.sh` exists, run it before saying you're done. Never claim tests pass
  without running them. Never delete or weaken tests to make them pass.
- If the stop hook sends you back, follow it.

## Keep docs current
After any task that changed code: add a line to `docs/CHANGELOG.md`, update
`docs/STATUS.md`, and record real choices in `docs/DECISIONS.md`. Docs explain intent and
decisions, not code the agent can read. Keep each under ~100 lines.

## Talking to the user
Plain language, no jargon. When finishing: what changed, how it was checked, what's open.
