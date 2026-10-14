#!/usr/bin/env python3
"""Mine Claude Code transcripts for harvestable know-how.

  mine.py session [PATH|latest]   digest of one session (errors->fixes, corrections, skills used)
  mine.py backfill [--days N] [--all]  cross-session patterns: recurring commands/errors with no skill
  mine.py usage [--days N]        how often each installed skill was actually invoked
  mine.py queue [--clear]         sessions the SessionEnd hook flagged as worth harvesting
  mine.py hook-end                SessionEnd hook: score the session, queue it if it's juicy
  mine.py hook-start              SessionStart hook: one-line nudge if the queue is non-empty

Stdlib only. Never raises out of hook modes (a broken hook must not break a session).
"""
import json, os, re, sys, time, glob, shlex
from collections import Counter, defaultdict

HOME = os.path.expanduser("~")
PROJECTS = os.path.join(HOME, ".claude", "projects")
SKILLS = os.path.join(HOME, ".claude", "skills")
STATE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state")
QUEUE = os.path.join(STATE, "queue.jsonl")
THRESHOLD = 6  # session score needed to be queued

CORRECTION = re.compile(
    r"(^\s*(no|nope|nah|wrong|stop|wait)\b|\b(don'?t|do not|never|always|instead|"
    r"not what i|that'?s not|why did you|you should have|undo|revert|from now on|next time|wrong|"
    r"terrible|awful|ugly|try again|redo|scratch|still|doesn'?t (work|even)|not working|broken)\b)",
    re.I)
NOISE_PREFIX = ("<local-command", "<command-name", "<command-message", "<system-reminder",
                "<task-notification", "Base directory for this skill", "[Request interrupted")


def short(s, n=160):
    s = re.sub(r"\s+", " ", str(s)).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") if isinstance(b, dict) and b.get("type") == "text"
                        else (b.get("content") if isinstance(b, dict) and isinstance(b.get("content"), str) else "")
                        for b in content)
    return ""


def tool_desc(name, inp):
    if not isinstance(inp, dict):
        return name
    for k in ("command", "skill", "url", "file_path", "query", "pattern", "action"):
        if k in inp:
            return f"{name}: {short(inp[k], 140)}"
    return name


SHELL_NOISE = set("""cd echo ls cat head tail mkdir export sleep sed grep rg find wc printf true false set
for while if then do done fi case esac test rm cp mv ln touch chmod chown sort uniq cut tr awk xargs tee
which type command time date env pwd kill pkill killall lsof ps open read source exit wait diff du df
basename dirname realpath stat file less more jq
import from def class return print break continue pass try except with elif else const let var function""".split())


def cmd_signature(command):
    """'cd x && ffmpeg -y -i a.mp4 ...' -> 'ffmpeg'; 'gh repo create' -> 'gh repo'."""
    if "<<" in command:  # drop heredoc bodies
        command = command[: command.find("\n", command.find("<<")) if "\n" in command[command.find("<<"):] else len(command)]
    for part in re.split(r"&&|;|\|\|?|\n", command):
        try:
            toks = shlex.split(part, posix=True)
        except ValueError:
            toks = part.split()
        while toks and re.fullmatch(r"[A-Za-z_]\w*=.*", toks[0]):  # FOO=bar cmd
            toks = toks[1:]
        if not toks or not re.fullmatch(r"[\w./~+-]+", toks[0]) or toks[0].startswith("-"):
            continue
        prog = os.path.basename(toks[0])
        if prog in SHELL_NOISE or not re.fullmatch(r"[A-Za-z][\w.+-]+", prog):
            continue
        if prog in ("python3", "python", "node", "bash", "sh", "npx", "uv", "bun") and len(toks) > 1:
            if toks[1].startswith("-"):
                continue  # inline scripts (python3 -c / -) carry no reusable signal
            return f"{prog} {os.path.basename(toks[1])}"
        sub = toks[1] if len(toks) > 1 and re.fullmatch(r"[a-z][a-z0-9-]{1,20}", toks[1]) else ""
        return f"{prog} {sub}".strip()
    return ""


def parse(path):
    """Return a dict of signals for one transcript."""
    uses, prompts, corrections, errors, skills, sigs = {}, [], [], [], Counter(), Counter()
    order, title, cwd, first_ts, last_ts, entry = [], "", "", "", "", ""
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return None
    with fh:
        for line in fh:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            t = d.get("type")
            if t == "ai-title":
                title = d.get("aiTitle") or d.get("title") or title
            if t not in ("user", "assistant") or d.get("isSidechain"):
                continue
            cwd = cwd or d.get("cwd", "")
            entry = entry or d.get("entrypoint", "")
            ts = d.get("timestamp", "")
            first_ts = first_ts or ts
            last_ts = ts or last_ts
            content = (d.get("message") or {}).get("content")
            if t == "assistant" and isinstance(content, list):
                for b in content:
                    if b.get("type") == "tool_use" and b.get("name") != "StructuredOutput":
                        inp = b.get("input") or {}
                        uses[b.get("id")] = (b.get("name"), inp)
                        order.append(b.get("id"))
                        if b.get("name") == "Skill":
                            skills[str(inp.get("skill", "?"))] += 1
                        if b.get("name") == "Bash" and isinstance(inp.get("command"), str):
                            s = cmd_signature(inp["command"])
                            if s:
                                sigs[s] += 1
            elif t == "user":
                if isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("is_error"):
                            errors.append((b.get("tool_use_id"), short(text_of(b.get("content")) or b.get("content"), 220)))
                    continue
                if d.get("isMeta"):
                    continue
                txt = text_of(content).strip()
                m = re.search(r"<command-name>/?([\w:-]+)</command-name>", txt)
                if m and m.group(1) not in ("clear", "compact", "model", "config", "help", "resume", "exit"):
                    skills[m.group(1)] += 1
                if not txt or txt.startswith(NOISE_PREFIX):
                    continue
                txt = re.sub(r"<pasted_content[^>]*>.*?</pasted_content[^>]*>", "[paste]", txt, flags=re.S)
                prompts.append(txt)
                if len(prompts) > 1 and CORRECTION.search(txt[:300]):
                    corrections.append(short(txt, 240))

    pos = {u: i for i, u in enumerate(order)}
    fixed = []
    for uid, msg in errors:
        if uid not in uses:
            continue
        if "user doesn't want" in msg or "denied" in msg.lower() or "rejected" in msg.lower():
            continue  # permission denials aren't gotchas
        name, inp = uses[uid]
        later = [uses[u] for u in order[pos[uid] + 1: pos[uid] + 6] if uses[u][0] == name]
        fixed.append({"tool": name, "failed": tool_desc(name, inp), "error": msg,
                      "then": tool_desc(*later[0]) if later else None})
    tool_calls = len(order)
    score = (2 * sum(1 for f in fixed if f["then"]) + 3 * len(corrections)
             + min(tool_calls // 10, 6) + (2 if len(prompts) >= 6 else 0))
    return {"path": path, "session": os.path.basename(path).rsplit(".", 1)[0], "title": title,
            "cwd": cwd, "start": first_ts[:16], "end": last_ts[:16], "prompts": prompts,
            "corrections": corrections, "errors": fixed, "skills": skills, "sigs": sigs,
            "tool_calls": tool_calls, "score": score,
            "headless": entry.startswith("sdk")}


INCLUDE_HEADLESS = False  # `claude -p` / SDK runs are scripted, not real work sessions


def transcripts(days=None):
    files = glob.glob(os.path.join(PROJECTS, "*", "*.jsonl"))
    if days:
        cutoff = time.time() - days * 86400
        files = [f for f in files if os.path.getmtime(f) >= cutoff]
    return sorted(files, key=os.path.getmtime, reverse=True)


def installed_skills():
    out = {}
    for f in glob.glob(os.path.join(SKILLS, "*", "SKILL.md")):
        try:
            out[os.path.basename(os.path.dirname(f))] = open(f, encoding="utf-8", errors="replace").read().lower()
        except OSError:
            pass
    return out


# ---------------------------------------------------------------- commands

def cmd_session(arg):
    if not arg or arg == "latest":
        files = transcripts()
        if not files:
            sys.exit("no transcripts found")
        arg = files[0]
    s = parse(arg)
    if not s:
        sys.exit(f"can't read {arg}")
    print(f"# Session {s['session'][:8]} — {s['title'] or '(untitled)'}")
    print(f"{s['start']} → {s['end']} · {s['cwd']} · {s['tool_calls']} tool calls · "
          f"{len(s['prompts'])} prompts · score {s['score']}\n")
    print("## User prompts (in order)")
    for i, p in enumerate(s["prompts"][:40], 1):
        print(f"{i}. {short(p, 200)}")
    if s["corrections"]:
        print("\n## Likely corrections / standing instructions")
        for c in s["corrections"][:20]:
            print(f"- {c}")
    if s["errors"]:
        print("\n## Errors → what came next  (gotcha candidates)")
        for e in s["errors"][:25]:
            print(f"- FAILED {e['failed']}\n  ERROR  {e['error']}\n  NEXT   {e['then'] or '(gave up / different approach)'}")
    if s["skills"]:
        print("\n## Skills used: " + ", ".join(f"{k}×{v}" for k, v in s["skills"].most_common()))
    if s["sigs"]:
        print("## Top commands: " + ", ".join(f"{k}×{v}" for k, v in s["sigs"].most_common(12)))


def cmd_backfill(days):
    skills = installed_skills()
    blob = " ".join(skills.values())
    sig_sessions, err_sessions, n = defaultdict(set), defaultdict(set), 0
    titles = {}
    for f in transcripts(days):
        s = parse(f)
        if not s or (s["headless"] and not INCLUDE_HEADLESS):
            continue
        n += 1
        titles[s["session"]] = s["title"]
        for sig in s["sigs"]:
            sig_sessions[sig].add(s["session"])
        for e in s["errors"]:
            key = re.sub(r"[0-9a-f]{6,}|\d+|/[\w./-]+", "#", e["error"].lower())[:90]
            err_sessions[key].add((s["session"], e["failed"], e["then"] or ""))
    print(f"# Backfill — {n} sessions, last {days} days\n")
    print("## Recurring commands (≥3 sessions)  — ✗ = no installed skill mentions it")
    rows = sorted(((len(v), k) for k, v in sig_sessions.items() if len(v) >= 3), reverse=True)
    for cnt, sig in rows[:30]:
        prog = sig.split()[-1] if sig.split()[0] in ("python3", "python", "node", "bash", "npx", "uv") else sig.split()[0]
        mark = "✓" if prog.lower() in blob else "✗"
        eg = "; ".join(filter(None, (titles.get(x) for x in list(sig_sessions[sig])[:3])))
        print(f"- {mark} `{sig}` in {cnt} sessions  — e.g. {short(eg, 120)}")
    print("\n## Errors that recur across sessions (≥2)")
    rec = sorted(((len({x[0] for x in v}), k, v) for k, v in err_sessions.items()), reverse=True)
    for cnt, _, v in [r for r in rec if r[0] >= 2][:15]:
        sess, failed, then = next(iter(v))
        print(f"- ×{cnt} {failed}\n    next: {then or '?'}")
    print("\nTreat ✗ rows used in many sessions and recurring errors as the strongest NEW/UPD candidates.")


def cmd_usage(days):
    skills = installed_skills()
    used = Counter()
    for f in transcripts(days):
        s = parse(f)
        if s and (INCLUDE_HEADLESS or not s["headless"]):
            for k, v in s["skills"].items():
                used[k.split(":")[-1]] += v
    print(f"# Skill usage — last {days} days\n")
    for name in sorted(skills, key=lambda k: -used.get(k, 0)):
        print(f"- {used.get(name, 0):>4}  {name}")
    print("\n0-use skills are candidates to merge, sharpen (bad description/triggers), or delete — ask first.")


def load_queue():
    try:
        return [json.loads(l) for l in open(QUEUE) if l.strip()]
    except (OSError, ValueError):
        return []


def cmd_queue(clear):
    q = load_queue()
    if clear:
        open(QUEUE, "w").close() if os.path.exists(QUEUE) else None
        print(f"cleared {len(q)} queued sessions")
        return
    if not q:
        print("queue empty")
        return
    print(f"# {len(q)} queued sessions (highest score first)\n")
    for e in sorted(q, key=lambda e: -e["score"]):
        print(f"- score {e['score']:>2}  {e['end']}  {e['title'] or '(untitled)'}\n    {e['path']}\n    {e['why']}")
    print("\nDigest any of them with: mine.py session <path>")


def cmd_hook_end():
    try:
        data = json.load(sys.stdin)
        path = data.get("transcript_path")
        if not path or not os.path.exists(path):
            return
        s = parse(path)
        if not s or s["headless"] or s["score"] < THRESHOLD:
            return
        if any(e["path"] == path for e in load_queue()):
            return
        os.makedirs(STATE, exist_ok=True)
        why = f"{len(s['errors'])} errors ({sum(1 for e in s['errors'] if e['then'])} retried), " \
              f"{len(s['corrections'])} corrections, {s['tool_calls']} tool calls"
        with open(QUEUE, "a") as fh:
            fh.write(json.dumps({"path": path, "title": s["title"], "end": s["end"],
                                 "score": s["score"], "why": why}) + "\n")
    except Exception:
        pass


def cmd_hook_start():
    try:
        q = load_queue()
        if q:
            print(f"[skill-harvest] {len(q)} past session(s) were flagged as harvestable "
                  f"(run `/skill-harvest queue` to review). Mention this once, briefly, only if relevant.")
    except Exception:
        pass


def main():
    a = sys.argv[1:]
    days = 30
    if "--days" in a:
        i = a.index("--days")
        days = int(a[i + 1])
        del a[i:i + 2]
    global INCLUDE_HEADLESS
    if "--all" in a:
        INCLUDE_HEADLESS = True
        a.remove("--all")
    cmd = a[0] if a else "help"
    if cmd == "session":
        cmd_session(a[1] if len(a) > 1 else None)
    elif cmd == "backfill":
        cmd_backfill(days)
    elif cmd == "usage":
        cmd_usage(days)
    elif cmd == "queue":
        cmd_queue("--clear" in a)
    elif cmd == "hook-end":
        cmd_hook_end()
    elif cmd == "hook-start":
        cmd_hook_start()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
