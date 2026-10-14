#!/usr/bin/env python3
"""Add (or with --remove, strip) the skill-harvest hooks in ~/.claude/settings.json.

SessionEnd   -> mine.py hook-end    scores the finished session (pure Python, no LLM), queues it if juicy
SessionStart -> mine.py hook-start  one-line nudge into context when the queue is non-empty

Idempotent; backs up settings.json to settings.json.bak first.
"""
import json, os, shutil, sys

SETTINGS = os.path.expanduser("~/.claude/settings.json")
MINE = os.path.expanduser("~/.claude/skills/skill-harvest/scripts/mine.py")
HOOKS = {"SessionEnd": f'python3 "{MINE}" hook-end', "SessionStart": f'python3 "{MINE}" hook-start'}


def main():
    remove = "--remove" in sys.argv
    if not remove and not os.path.exists(MINE):
        sys.exit(f"install the skill first: {MINE} not found")
    s = json.load(open(SETTINGS)) if os.path.exists(SETTINGS) else {}
    if os.path.exists(SETTINGS):
        shutil.copy(SETTINGS, SETTINGS + ".bak")
    hooks = s.setdefault("hooks", {})
    for event, cmd in HOOKS.items():
        groups = hooks.get(event, [])
        for g in groups:  # strip any previous skill-harvest entry
            g["hooks"] = [h for h in g.get("hooks", []) if "skill-harvest" not in h.get("command", "")]
        groups = [g for g in groups if g.get("hooks")]
        if not remove:
            groups.append({"hooks": [{"type": "command", "command": cmd, "timeout": 30}]})
        if groups:
            hooks[event] = groups
        else:
            hooks.pop(event, None)
    if not hooks:
        s.pop("hooks")
    with open(SETTINGS, "w") as fh:
        json.dump(s, fh, indent=2)
        fh.write("\n")
    print(("removed" if remove else "installed") + f" skill-harvest hooks in {SETTINGS}")


if __name__ == "__main__":
    main()
