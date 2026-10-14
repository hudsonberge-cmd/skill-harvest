# skill-harvest

A [Claude Code](https://claude.com/claude-code) skill that turns what Claude learns while you work into reusable skills, so it stops relearning the same lessons every session.

## What it does

| Mode | Say | What happens |
|---|---|---|
| **now** | `/skill-harvest`, "harvest", "make a skill out of this" | Pulls workflows, gotchas, tool quirks and your corrections from the current session |
| **queue** | "harvest queue" | Reviews past sessions the auto-hook flagged as worth harvesting |
| **backfill** | "mine my history" | Finds commands and errors that recur across past sessions with **no skill covering them** |
| **audit** | "audit my skills" | Lints every installed skill: weak trigger descriptions, dead paths, leaked secrets, overlaps, and skills you never use |

Each finding is labeled **NEW** skill / **UPD**ate an existing skill / **MEM**ory / **DROP**, shown to you with evidence, and only written after you approve. New skills get linted, and every harvest (rejected ones too) is logged in `LEDGER.md` so nothing gets pitched twice.

## The tools behind it

Stdlib Python 3. They read your local transcripts in `~/.claude/projects/` and make **no LLM calls and no network calls**.

```sh
H=~/.claude/skills/skill-harvest/scripts
python3 $H/mine.py session latest      # one session: prompts, corrections, errors → what was tried next
python3 $H/mine.py backfill --days 30  # cross-session patterns; ✗ = no skill covers it
python3 $H/mine.py usage --days 30     # how often each skill actually gets used
python3 $H/mine.py queue               # sessions flagged by the hook
python3 $H/lint.py                     # audit all installed skills
```

Headless `claude -p` / SDK sessions are skipped by default (`--all` includes them).

## Install

```sh
git clone https://github.com/hudsonberge-cmd/skill-harvest.git /tmp/skill-harvest
cp -r /tmp/skill-harvest/skill-harvest ~/.claude/skills/
```

### Optional: auto-queue hooks

```sh
python3 ~/.claude/skills/skill-harvest/scripts/install_hooks.py          # --remove to undo
```

This adds two hooks to `~/.claude/settings.json` (backed up first, existing hooks kept):
- **SessionEnd** scores the finished session in ~0.1s (errors that got retried, your corrections, session length) and queues it if it looks worth harvesting.
- **SessionStart** adds a one-line note when the queue isn't empty, so Claude can offer to harvest.

### Optional: proactive offers

Add this to your `CLAUDE.md` so Claude offers to harvest at the end of big tasks:

> After substantial multi-step tasks, run the /skill-harvest check and, if there's a solid candidate, end with one line: "Harvestable: <name> — want me to skill it?"
