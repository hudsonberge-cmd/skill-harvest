---
name: skill-harvest
description: Spot reusable know-how from the current session (workflows that worked, gotchas that cost time, tool/API quirks, the user's corrections) and turn it into new skills or upgrades to existing ones. Use when the user says "harvest", "skill that", "make a skill out of this", "save this workflow", "/skill-harvest", or proactively at the end of any substantial task where a multi-step process was figured out the hard way.
---

# /skill-harvest

Goal: next time the user asks for something similar, Claude already knows the playbook instead of
rediscovering it. Skills live in `~/.claude/skills/<name>/SKILL.md`. Ledger of every harvest
(accepted + rejected) lives next to this file in `LEDGER.md` — read it first so nothing gets
re-proposed or duplicated.

## 1. Scan the session

Go back through the conversation and pull out candidates. Good ones:

- **Workflows** — a multi-step procedure that ended up working (commands, order, flags, file paths,
  which tool for which step). Especially if it took retries to get right.
- **Gotchas** — something that failed and the fix (error text → cause → fix). These are gold.
- **Tool / API / site quirks** — rate limits, selectors, auth flows, model/param settings that matter.
- **User corrections** — "no, do it like X", "never Y". Workflow-shaped ones go in a skill;
  general preferences go to memory instead (see routing).
- **Quality bars** — what the user accepted vs. sent back, and why.

Skip: one-off facts, anything the code/repo/git history already records, things any competent
engineer knows, and anything containing secrets/tokens/passwords.

## 2. Route each candidate

| It's a… | Goes to |
|---|---|
| Repeatable procedure with steps, commands, or checks | **New skill** |
| Fix/gotcha/refinement for a workflow that already has a skill | **Update that skill** (add to its gotchas / steps) |
| Preference, fact about the user, project status, pointer to a resource | **Memory** (e.g. `~/.claude/projects/<project>/memory/`) — not a skill |
| Too thin / used once / obvious | **Drop** (still log it in the ledger as rejected) |

Bar for a *new* skill: it would plausibly be reused, and it saves real steps or prevents a real
mistake. When in doubt, prefer updating an existing skill over spawning a new one —
`ls ~/.claude/skills/` and grep their descriptions before deciding.

## 3. Propose — don't just write

Skills change how future sessions behave, so show the user the plan first, short:

```
Harvest from this session:
1. NEW  /veo-retry-loop — retry + QA loop for failed Veo clips (why: took 4 tries to nail today)
2. UPD  /tiktok-post — add: Studio scheduler rejects slots <20 min out
3. MEM  prefers 9:16 previews before full renders
4. DROP ffmpeg concat flag — one-off
Want all, some, or none?
```

Exception: if the user explicitly said "make a skill out of this", skip the proposal and build it.

## 4. Write the skill

Directory `~/.claude/skills/<kebab-name>/SKILL.md` (+ helper scripts/reference files in the same
dir if they genuinely help). Match the house style of the existing skills:

```markdown
---
name: <kebab-name>
description: <what it does, concretely> Use when the user says "<trigger phrases>", or <situation>.
---

# /<kebab-name>

<1–3 lines: what it's for, where the toolkit/files live.>

## Steps
1. … exact commands, paths, flags — copy what actually worked this session

## Gotchas
- <symptom> → <cause> → <fix>

## Done when
- <concrete check that the output is right>
```

Rules:
- The **description** is what makes it trigger — put real trigger phrases and situations in it.
- Write from what *actually happened*, not a generic tutorial. Exact commands > prose.
- Keep it tight (under ~150 lines). Link to a reference file rather than bloating SKILL.md.
- No secrets. Reference env var names / keychain entries instead.
- Never overwrite an existing skill wholesale — Read it, then Edit the specific section.
- If the workflow already has a memory file, link the skill from the memory (or vice versa)
  instead of duplicating content.

## 5. Log it

Append to `LEDGER.md`:

```
## YYYY-MM-DD — <session topic>
- NEW /name — one-line why
- UPD /name — what was added
- MEM name — what was saved
- DROP — what and why
```

Then tell the user in one line per item what got created/updated, with the path.

## Proactive mode

At the end of a substantial task (multi-step build, debugging session, new pipeline, anything that
took retries), quickly run steps 1–2 in your head. If there's at least one solid NEW or UPD
candidate, add a single line at the end of the reply: "Harvestable: <name> — want me to skill it?"
Don't interrupt mid-task, and don't nag on small tasks.
