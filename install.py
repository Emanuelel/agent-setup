#!/usr/bin/env python3
"""Install (or update / remove) the shared agent setup for Codex AND Claude Code.

    python3 install.py              install or update (safe to run again any time)
    python3 install.py --uninstall  remove everything this installer added

What it does, in plain words:
  - Global rules have ONE home: ~/.codex/AGENTS.md (Codex reads it directly).
    If that file is empty or missing, it is seeded from rules/starter-rules.md; after that
    the installer never overwrites it. Edit it directly, any time.
  - Claude Code's ~/.claude/CLAUDE.md gets one import line, @~/.codex/AGENTS.md, so it
    reads the same file. Anything else you keep in CLAUDE.md stays.
  - Creates the `explorer` and `reviewer` helper agents in both tools' formats.
  - Installs the checkpoint hook (one script, used by both tools).
  - Installs the `project-docs` skill for both tools.
  - Before changing any existing file, saves a copy in ~/.agents/backups/<date-time>/.
"""
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
MARK = "agent-setup"
BLOCK_START = f"<!-- {MARK}:start (global rules live in ~/.codex/AGENTS.md: edit that file) -->"
CLAUDE_IMPORT = "@~/.codex/AGENTS.md"
BLOCK_END = f"<!-- {MARK}:end -->"
FILE_MARKER = f"Managed by {MARK}"
HOOK_DEST = os.path.join(HOME, ".agents", "hooks", "agent_gate.py")
HOOK_COMMAND = 'python3 "$HOME/.agents/hooks/agent_gate.py"'
HOOK_TIMEOUT = 300

P = {
    "codex_rules": os.path.join(HOME, ".codex", "AGENTS.md"),
    "claude_rules": os.path.join(HOME, ".claude", "CLAUDE.md"),
    "codex_agents": os.path.join(HOME, ".codex", "agents"),
    "claude_agents": os.path.join(HOME, ".claude", "agents"),
    "codex_hooks": os.path.join(HOME, ".codex", "hooks.json"),
    "claude_settings": os.path.join(HOME, ".claude", "settings.json"),
    "codex_skills": os.path.join(HOME, ".agents", "skills"),
    "claude_skills": os.path.join(HOME, ".claude", "skills"),
}

BACKUP_DIR = os.path.join(HOME, ".agents", "backups", time.strftime("%Y%m%d-%H%M%S"))
changes = []
backed_up = []


def say(msg):
    changes.append(msg)
    print("  • " + msg)


def backup(path):
    if not os.path.exists(path):
        return
    backed_up.append(path)
    rel = os.path.relpath(path, HOME)
    dest = os.path.join(BACKUP_DIR, rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.isdir(path):
        if not os.path.exists(dest):
            shutil.copytree(path, dest)
    elif not os.path.exists(dest):
        shutil.copy2(path, dest)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


# ---------- rules ----------

BLOCK_PREFIX = f"<!-- {MARK}:start"


def strip_block(text):
    """Remove the managed block (any older marker wording) and return what's outside it."""
    if BLOCK_PREFIX in text and BLOCK_END in text:
        start = text.index(BLOCK_PREFIX)
        end = text.index(BLOCK_END) + len(BLOCK_END)
        return (text[:start].rstrip() + "\n\n" + text[end:].lstrip()).strip() + "\n"
    return text


def already_included(old, rules):
    """True if every non-heading line of the old text appears, in order, in the shared rules."""
    def lines(t):
        return [l.strip() for l in t.splitlines() if l.strip() and not l.startswith("# ")]
    want, have = lines(old), lines(rules)
    if not want:
        return True
    i = 0
    for line in have:
        if line == want[i]:
            i += 1
            if i == len(want):
                return True
    return False


def block_inner(text):
    if BLOCK_PREFIX in text and BLOCK_END in text:
        start = text.index(BLOCK_PREFIX)
        inner_start = text.index("-->", start) + 3
        return text[inner_start:text.index(BLOCK_END)].strip()
    return None


def own_codex_rules(remove=False):
    """Make ~/.codex/AGENTS.md the single, plain source of the global rules."""
    path = P["codex_rules"]
    if remove:
        return  # it's your file now; uninstall leaves it alone
    existing = read(path) if os.path.exists(path) else ""
    inner = block_inner(existing)
    if inner is not None:
        outside = strip_block(existing).strip()
        plain = inner + "\n" + (("\n" + outside + "\n") if outside else "")
        backup(path)
        write(path, plain)
        say(f"{short(path)} is now a plain file and the single source of your global rules")
    elif not existing.strip():
        write(path, read(os.path.join(HERE, "rules", "starter-rules.md")))
        say(f"Global rules created at {short(path)} from rules/starter-rules.md")


def set_rules(path, rules, remove=False, dedupe_against=""):
    existing = read(path) if os.path.exists(path) else ""
    base = strip_block(existing).strip() if block_inner(existing) is not None else existing.strip()
    if remove:
        if existing and existing != (base + "\n" if base else ""):
            backup(path)
            if base:
                write(path, base + "\n")
            else:
                os.remove(path)
            say(f"Removed shared rules from {short(path)}")
        return
    new = f"{BLOCK_START}\n{rules.strip()}\n{BLOCK_END}\n"
    if base and dedupe_against and already_included(base, dedupe_against):
        say(f"Old rules in {short(path)} are already part of the shared rules: removed the duplicate (backup kept)")
        base = ""
    if base:
        new = new + "\n" + base + "\n"
    if new != existing:
        backup(path)
        write(path, new)
        say(f"{short(path)} now imports {CLAUDE_IMPORT} (same rules as Codex)")


# ---------- agents ----------

def parse_agent(path):
    text = read(path)
    _, front, body = text.split("---", 2)
    meta = {}
    for line in front.strip().splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta, body.strip() + "\n"


def codex_toml(meta, body):
    if "'''" in body:
        raise ValueError("agent instructions may not contain three single quotes")
    lines = [f"# {FILE_MARKER}. Edit agents/{meta['name']}.md in the setup folder and re-run install.py."]
    if not meta.get("codex_model"):
        lines.append("# No model set: uses the same model as your main chat. To use a cheaper model,")
        lines.append("# set codex_model in agents/<name>.md to a name from Codex's model picker.")
    lines.append(f"name = {json.dumps(meta['name'])}")
    lines.append(f"description = {json.dumps(meta['description'])}")
    if meta.get("codex_model"):
        lines.append(f"model = {json.dumps(meta['codex_model'])}")
    if meta.get("codex_reasoning_effort"):
        lines.append(f"model_reasoning_effort = {json.dumps(meta['codex_reasoning_effort'])}")
    if meta.get("codex_sandbox"):
        lines.append(f"sandbox_mode = {json.dumps(meta['codex_sandbox'])}")
    lines.append("developer_instructions = '''")
    lines.append(body.rstrip())
    lines.append("'''")
    return "\n".join(lines) + "\n"


def claude_md(meta, body):
    front = [f"name: {meta['name']}", f"description: {json.dumps(meta['description'])}"]
    if meta.get("claude_tools"):
        front.append(f"tools: {meta['claude_tools']}")
    if meta.get("claude_model"):
        front.append(f"model: {meta['claude_model']}")
    return ("---\n" + "\n".join(front) + "\n---\n"
            + f"<!-- {FILE_MARKER}. Edit agents/{meta['name']}.md in the setup folder and re-run install.py. -->\n\n"
            + body)


def put_managed_file(path, content, remove=False):
    exists = os.path.exists(path)
    ours = exists and FILE_MARKER in read(path)
    if remove:
        if ours:
            backup(path)
            os.remove(path)
            say(f"Removed {short(path)}")
        return
    if exists and read(path) == content:
        return
    if exists and not ours:
        backup(path)
        say(f"{short(path)} existed and wasn't ours: saved a backup before replacing it")
    write(path, content)
    say(f"Agent file written: {short(path)}")


def install_agents(remove=False):
    src = os.path.join(HERE, "agents")
    for name in sorted(os.listdir(src)):
        if not name.endswith(".md"):
            continue
        meta, body = parse_agent(os.path.join(src, name))
        stem = meta["name"]
        put_managed_file(os.path.join(P["codex_agents"], f"{stem}.toml"), codex_toml(meta, body), remove)
        put_managed_file(os.path.join(P["claude_agents"], f"{stem}.md"), claude_md(meta, body), remove)


# ---------- hook ----------

def merge_stop_hook(path, remove=False):
    data = {}
    if os.path.exists(path):
        try:
            data = json.loads(read(path) or "{}")
        except ValueError:
            print(f"  ! {short(path)} isn't valid JSON, so I left it alone. Fix it and re-run.")
            return
    before = json.dumps(data, sort_keys=True)
    hooks = data.setdefault("hooks", {})
    stop = hooks.get("Stop", [])
    # drop any previous copy of our hook
    cleaned = []
    for group in stop:
        handlers = [h for h in group.get("hooks", []) if "agent_gate.py" not in str(h.get("command", ""))]
        if handlers:
            group = dict(group, hooks=handlers)
            cleaned.append(group)
    if not remove:
        cleaned.append({"hooks": [{"type": "command", "command": HOOK_COMMAND, "timeout": HOOK_TIMEOUT}]})
    if cleaned:
        hooks["Stop"] = cleaned
    else:
        hooks.pop("Stop", None)
    if not hooks:
        data.pop("hooks", None)
    if json.dumps(data, sort_keys=True) == before:
        return
    backup(path)
    if remove and not data and os.path.exists(path) and path.endswith("hooks.json"):
        os.remove(path)
    else:
        write(path, json.dumps(data, indent=2) + "\n")
    say(("Removed checkpoint hook from " if remove else "Checkpoint hook registered in ") + short(path))


def install_hook_script(remove=False):
    if remove:
        if os.path.exists(HOOK_DEST):
            os.remove(HOOK_DEST)
            say(f"Removed {short(HOOK_DEST)}")
        return
    src = os.path.join(HERE, "hooks", "agent_gate.py")
    if os.path.exists(HOOK_DEST) and read(HOOK_DEST) == read(src):
        return
    os.makedirs(os.path.dirname(HOOK_DEST), exist_ok=True)
    shutil.copy2(src, HOOK_DEST)
    os.chmod(HOOK_DEST, 0o755)
    say(f"Hook script installed: {short(HOOK_DEST)}")


# ---------- skill ----------

def install_skill(parent, remove=False):
    src = os.path.join(HERE, "skills", "project-docs")
    dest = os.path.join(parent, "project-docs")
    marker = os.path.join(dest, ".installed-by-agent-setup")
    if remove:
        if os.path.exists(marker):
            shutil.rmtree(dest)
            say(f"Removed skill {short(dest)}")
        return
    if os.path.exists(marker) and tree_digest(src) == tree_digest(dest):
        return  # already up to date
    if os.path.exists(dest) and not os.path.exists(marker):
        backup(dest)
        say(f"{short(dest)} existed and wasn't ours: saved a backup before replacing it")
    # Update in place: overwrite our files, then tidy up files the repo no longer has.
    shutil.copytree(src, dest, dirs_exist_ok=True)
    wanted = {os.path.relpath(os.path.join(b, f), src) for b, _, fs in os.walk(src) for f in fs}
    for base, _, files in os.walk(dest):
        for name in files:
            rel = os.path.relpath(os.path.join(base, name), dest)
            if rel not in wanted and name != ".installed-by-agent-setup":
                try:
                    os.remove(os.path.join(base, name))
                except OSError:
                    pass
    vs = os.path.join(dest, "templates", "scripts", "verify.sh")
    if os.path.exists(vs):
        os.chmod(vs, 0o755)
    write(marker, "Installed by agent-setup/install.py. Re-run it to update.\n")
    say(f"Skill installed: {short(dest)}")


def tree_digest(root):
    import hashlib
    h = hashlib.sha256()
    for base, dirs, files in sorted(os.walk(root)):
        dirs.sort()
        for name in sorted(files):
            if name == ".installed-by-agent-setup":
                continue
            full = os.path.join(base, name)
            h.update(os.path.relpath(full, root).encode())
            with open(full, "rb") as f:
                h.update(f.read())
    return h.hexdigest()


def short(path):
    return path.replace(HOME, "~", 1)


def main():
    remove = "--uninstall" in sys.argv
    if sys.version_info < (3, 8):
        sys.exit("Python 3.8 or newer is needed.")
    print("Removing agent setup..." if remove else "Installing agent setup for Codex + Claude Code...")
    own_codex_rules(remove)
    codex_text = read(P["codex_rules"]) if os.path.exists(P["codex_rules"]) else ""
    set_rules(P["claude_rules"], CLAUDE_IMPORT, remove, dedupe_against=codex_text)
    install_agents(remove)
    install_hook_script(remove)
    merge_stop_hook(P["codex_hooks"], remove)
    merge_stop_hook(P["claude_settings"], remove)
    install_skill(P["codex_skills"], remove)
    install_skill(P["claude_skills"], remove)
    if not changes:
        print("  Everything was already up to date. Nothing changed.")
    elif backed_up:
        print(f"\nBackups of anything I changed are in {short(BACKUP_DIR)}")
    print("\nDone." + ("" if remove else
          " Next: restart Codex and Claude Code, then approve the new hook when asked "
          "(Codex: Settings > Hooks, or 'Review hooks' in the composer)."))


if __name__ == "__main__":
    main()
