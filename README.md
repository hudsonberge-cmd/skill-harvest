# skill-harvest

A [Claude Code](https://claude.com/claude-code) skill that turns what Claude learns while you work into reusable skills.

At the end of a session, or whenever you ask, it scans the conversation for workflows that eventually worked, gotchas that cost time, tool/API quirks, and your corrections. Then it sorts each one:

- **NEW**: a repeatable procedure becomes a new skill in `~/.claude/skills/<name>/SKILL.md`
- **UPD**: a fix for an existing skill gets added to that skill
- **MEM**: a preference or fact goes to memory, not a skill
- **DROP**: anything too thin to keep

It shows you the list and asks before writing anything. Every harvest, including rejected ones, is logged in `LEDGER.md` so nothing gets pitched twice.

## Install

```sh
git clone https://github.com/hudsonberge-cmd/skill-harvest.git /tmp/skill-harvest
cp -r /tmp/skill-harvest/skill-harvest ~/.claude/skills/
```

## Use

- `/skill-harvest`, "harvest", or "make a skill out of this" (the last one skips the approval step)
- Proactive: after a substantial task, Claude adds one line offering to turn the learnings into a skill. For this to happen reliably across sessions, add a note to your `CLAUDE.md` or memory telling Claude to run the skill-harvest check after big tasks.
