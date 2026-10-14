---
name: skill-harvest
description: Spot reusable know-how from Claude Code sessions (workflows that worked, gotchas that cost time, tool/API quirks, the user's corrections) and turn it into new skills or upgrades to existing ones. Also mines past transcripts for recurring patterns and audits existing skills. Use when the user says "harvest", "skill that", "make a skill out of this", "save this workflow", "audit my skills", "/skill-harvest", or proactively at the end of any substantial task where a multi-step process was figured out the hard way.
---

# /skill-harvest

Goal: next time the user asks for something similar, Claude already knows the playbook instead of
rediscovering it. Skills live in `~/.claude/skills/<name>/SKILL.md`. This skill's folder:
`~/.claude/skills/skill-harvest/` (`H` below).

**Before anything:** read `H/LEDGER.md` — every past harvest, accepted and rejected — so nothing
gets re-proposed or duplicated.

| Mode | Say | What runs |
|---|---|---|
| **now** (default) | "harvest", "skill that" | this session → candidates |
| **queue** | "harvest queue" | sessions the SessionEnd hook flagged |
| **backfill** | "backfill", "mine my history" | patterns across the last N days of sessions |
| **audit** | "audit my skills" | lint + usage + overlap across all installed skills |

Tools (stdlib Python, fast, no LLM calls):
- `python3 H/scripts/mine.py session [PATH|latest]` — digest of a session: every user prompt in order,
  likely corrections, **errors → what Claude tried next** (gotcha goldmine), skills used, top commands.
- `python3 H/scripts/mine.py backfill --days 30` — commands recurring across sessions with **✗ = no skill
  covers it**, and errors that keep recurring across sessions.
- `python3 H/scripts/mine.py usage --days 30` — invocation count per installed skill.
- `python3 H/scripts/mine.py queue [--clear]` — sessions flagged by the hook.
- `python3 H/scripts/lint.py [skill-dir]` — frontmatter, trigger clause, size, leaked secrets, dead
  paths, description overlap. Exit 1 on errors.

## 1. Gather evidence

- **now:** use the conversation in context. If it was compacted (or is long), also run
  `mine.py session latest` — it recovers prompts and errors the summary dropped.
- **queue:** `mine.py queue`, then `mine.py session <path>` for the top 1–3 by score. `--clear` once handled.
- **backfill:** `mine.py backfill`, then `mine.py session <path>` on sessions behind the strongest rows.
  A pattern seen in 3+ sessions with no skill is the strongest possible NEW candidate.
- **audit:** jump to section 6.

## 2. Pick candidates

Good ones:
- **Workflows** — a multi-step procedure that ended up working (commands, order, flags, paths,
  which tool for which step). Especially if it took retries.
- **Gotchas** — something failed, then the fix. Error text → cause → fix. The `errors → next` list
  is where these live; a NEXT that's the same call with a tweak = the tweak is the lesson.
- **Tool / API / site quirks** — rate limits, selectors, auth flows, model/param settings.
- **User corrections** — "no, do it like X", "bro this is terrible". Workflow-shaped → skill;
  general preferences → memory.
- **Quality bars** — what the user accepted vs. sent back, and why.

Skip: one-offs, anything the repo/git history already records, generic knowledge, secrets.

## 3. Route each one

| It's a… | Goes to |
|---|---|
| Repeatable procedure with steps, commands, or checks | **NEW skill** |
| Fix/gotcha for a workflow that already has a skill | **UPD that skill** (gotchas / steps) |
| Gotcha about a *tool* used across many workflows (e.g. Chrome MCP can't open `file://`) | **UPD** the tool's skill if one exists, else a small NEW `<tool>-gotchas` skill |
| Preference, fact about the user, project status, resource pointer | **MEM** (e.g. `~/.claude/projects/<project>/memory/`) |
| Too thin / used once / obvious | **DROP** (still logged) |

Before NEW: `grep -il "<keyword>" ~/.claude/skills/*/SKILL.md` — updating beats spawning.
Bar for NEW: plausibly reused, and saves real steps or prevents a real mistake.

## 4. Propose — don't just write

Skills change how future sessions behave, so show the plan first, short, with evidence:

```
Harvest from this session:
1. NEW  /chrome-local-files — Chrome MCP refuses file:// → serve with python3 -m http.server
        (evidence: failed 5× across 3 sessions)
2. UPD  /tiktok-post — add: Studio scheduler rejects slots <20 min out
3. MEM  prefers 9:16 previews before full renders
4. DROP ffmpeg concat flag — one-off
Want all, some, or none?
```

Exception: if the user explicitly said "make a skill out of this", skip the proposal and build it.

## 5. Write, verify, log

Write `~/.claude/skills/<kebab-name>/SKILL.md` (+ scripts/reference files in the same dir if they
genuinely help). House style:

```markdown
---
name: <kebab-name>
description: <what it does, concretely>. Use when the user says "<trigger phrases>", or <situation>.
---

# /<kebab-name>

<1–3 lines: what it's for, where the toolkit/files live.>

## Steps
1. exact commands, paths, flags — copied from what actually worked

## Gotchas
- <symptom / error text> → <cause> → <fix>

## Done when
- <concrete check that the output is right>

<!-- harvested YYYY-MM-DD from session <first 8 of session id> -->
```

Rules:
- The **description** is what makes it trigger — real phrases the user uses + situations. Include the
  literal error text in Gotchas so a future search for that error hits it.
- Exact commands > prose. Under ~150 lines; push detail into a `reference.md`.
- No secrets — name env vars / keychain entries instead.
- UPD = Read the skill, Edit the specific section. Never rewrite someone's skill wholesale.
- **Verify:** run `lint.py <dir>` and fix every ERROR. Spot-check that commands the skill names exist
  (`command -v <tool>`) and paths resolve.
- **Log:** append to `H/LEDGER.md`:
  ```
  ## YYYY-MM-DD — <session topic>
  - NEW /name — why (evidence)
  - UPD /name — what was added
  - MEM name — what was saved
  - DROP — what and why
  ```
- Report back one line per item with the path.

## 6. Audit mode

1. `lint.py` (all skills) and `mine.py usage --days 60`.
2. Report, grouped: **ERRORs** (fix now) · **dead paths** in the user's own skills (fix or flag the skill
   as stale) · **weak descriptions** (no trigger clause → propose a rewritten description) ·
   **overlaps** (merge or sharpen triggers) · **never used in 60 days** (sharpen, merge, or delete).
3. Propose fixes; apply only what the user approves. Never delete a skill without an explicit yes.
   Third-party/vendored skills — only flag, don't edit.

## Proactive mode

At the end of a substantial task (multi-step build, debugging, new pipeline, anything that took
retries), run steps 2–3 in your head. If there's at least one solid NEW or UPD candidate, add one
line at the end of the reply: "Harvestable: <name> — want me to skill it?" Don't interrupt
mid-task; don't nag on small tasks. If a SessionStart note says sessions are queued, mention it once.

## Auto-queue hooks (optional)

`python3 H/scripts/install_hooks.py` adds a SessionEnd hook (scores each finished session in ~0.1s,
queues it if score ≥ 6) and a SessionStart hook (one-line nudge when the queue is non-empty).
`--remove` undoes it. Run it yourself; Claude Code blocks Claude from editing its own hooks.
