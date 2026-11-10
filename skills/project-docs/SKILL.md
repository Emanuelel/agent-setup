---
name: project-docs
description: Set up or repair the standard project documentation structure (AGENTS.md map, CLAUDE.md pointer, docs/ PRODUCT, DESIGN, ARCHITECTURE, DECISIONS, STATUS, CHANGELOG) and wire up automatic checks in scripts/verify.sh (lint, types, tests, project rules). Use when a project has no AGENTS.md or no docs/ folder, or when the user asks to set up or refresh project docs.
---

# Project docs setup

Goal: every project gets the same small, predictable set of files so any agent
(Codex, Claude Code, or another tool) can open the project and know where to look.

Templates live in the `templates/` folder next to this file. Use them as the starting
shape; replace every `<...>` placeholder with real content or delete the line.

## Steps

1. **Look before writing.** List the project root and `docs/`. Note which of these
   already exist: `AGENTS.md`, `CLAUDE.md`, `README.md`, `docs/PRODUCT.md`,
   `docs/DESIGN.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/STATUS.md`,
   `docs/CHANGELOG.md`, `scripts/verify.sh`.
   Never overwrite an existing file. For existing files, only add missing sections.

2. **Learn the project quickly.** Use the `explorer` agent (read-only) to find: what the
   project is, the language/framework, how to install, run, test, lint and build it,
   the main folders, and external services it talks to. If there is no code yet, skip this.

3. **Ask the user at most 5 short questions**, only about what the code can't tell you:
   - Who is this for and what problem does it solve?
   - What is in scope now, and what is explicitly out of scope?
   - Any look-and-feel or brand rules (colours, fonts, tone of voice)?
   - Any hard rules (e.g. "never touch the payments folder", "Spanish copy only")?
   - What are you working on right now?
   If the user isn't available, fill what you can and mark the rest `<TODO: ask user>`.

4. **Create the missing files** from the templates:
   - `AGENTS.md` (project root): the map. Keep it under ~80 lines.
   - `CLAUDE.md` (project root): exactly the content of `templates/CLAUDE.md`
     (a single `@AGENTS.md` import line), so Claude Code reads the same map.
     If a CLAUDE.md already exists without that line, add `@AGENTS.md` as its first line.
   - `docs/PRODUCT.md`, `docs/DESIGN.md`, `docs/ARCHITECTURE.md`,
     `docs/DECISIONS.md`, `docs/STATUS.md`, `docs/CHANGELOG.md`.
   - `scripts/verify.sh`: copy the template and make it executable
     (`chmod +x scripts/verify.sh`). It finds and runs the lint, format, type and test
     tools the project already has. Then follow step 5.

5. **Make the checks real.** Run `scripts/verify.sh` and read what it ran. The goal is
   that every project checks formatting, lint, types and tests automatically, because a
   check is enforced while a written rule is only advice. If something is missing for the
   stack, propose the standard tool, and ask the user before installing anything (new
   dependencies need their OK):

   | Stack | Lint and format | Types | Tests |
   |---|---|---|---|
   | Expo / React Native | `npx expo lint` (sets up ESLint) | TypeScript with `"strict": true` | `jest-expo` |
   | Web (TypeScript) | ESLint + Prettier, or Biome | `tsc --noEmit`, `"strict": true` | Vitest |
   | Python | Ruff (`ruff check`, `ruff format`) | mypy, or pyright | pytest |

   Add a `lint`, `typecheck` and `test` (or `test:ci`) script to `package.json` so
   `verify.sh` finds them. If a check fails on existing code, don't fix the whole codebase
   now: tell the user how much fails and ask how to proceed. If the project has hard rules
   from step 3 that a machine can check, add them as `forbid` lines in section 2 of
   `verify.sh`, each with a message that explains the fix.

6. **Fill content with care:**
   - Docs explain what the code can't: intent, decisions, conventions, current state.
   - Don't write a tour of the file tree; the AGENTS.md map lists only key places.
   - Keep each doc short (about 100 lines). If something grows, split it into a sub-file
     in `docs/` and link it from AGENTS.md.

7. **Finish:** list what `verify.sh` checks in the "Enforced by checks" section of
   AGENTS.md, add a CHANGELOG entry ("Set up project docs structure"), and tell the user in
   plain language which files were created, which checks run, which were left as TODO,
   and what you need from them.
