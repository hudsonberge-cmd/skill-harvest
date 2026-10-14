#!/usr/bin/env python3
"""Lint Claude Code skills.

  lint.py                 lint every skill in ~/.claude/skills
  lint.py <dir|SKILL.md>  lint one skill

Checks: frontmatter + name matches folder, description has triggers and a sane length, size,
leaked secrets, ~/ and /Users paths that no longer exist, and description overlap between skills.
Exit 1 if any ERROR.
"""
import os, re, sys, glob

SKILLS = os.path.expanduser("~/.claude/skills")
SECRET = re.compile(r"(sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
                    r"xox[abp]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY|"
                    r"(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9/+_-]{16,})", re.I)
STOP = set("the a an and or to of for in on with use when says any it is be as by from this that you your "
           "into at user make get run".split())


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None, text
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"')
    return fm, text[m.end():]


def lint(path):
    issues = []
    folder = os.path.basename(os.path.dirname(path))
    text = open(path, encoding="utf-8", errors="replace").read()
    fm, body = frontmatter(text)
    if fm is None:
        return [("ERROR", "no YAML frontmatter")], ""
    name, desc = fm.get("name", ""), fm.get("description", "")
    if not name:
        issues.append(("ERROR", "frontmatter missing name"))
    elif name != folder:
        issues.append(("WARN", f"name '{name}' != folder '{folder}'"))
    if not desc:
        issues.append(("ERROR", "frontmatter missing description"))
    else:
        if len(desc) < 60:
            issues.append(("WARN", f"description is short ({len(desc)} chars) — it's what makes the skill trigger"))
        if len(desc) > 1024:
            issues.append(("WARN", f"description is long ({len(desc)} chars)"))
        if not re.search(r"\buse (this )?(when|for|whenever)\b|\btrigger", desc, re.I):
            issues.append(("WARN", "description has no 'Use when …' trigger clause"))
    lines = text.count("\n")
    if lines > 300:
        issues.append(("WARN", f"{lines} lines — move detail into a reference file"))
    for m in SECRET.finditer(text):
        issues.append(("ERROR", f"possible secret: {m.group(0)[:12]}…"))
    for m in re.finditer(r"(?<![\w/])(~/[\w.@-][\w./@-]*|/Users/[\w.-]+/[\w./@-]+)", body):
        p = m.group(1).rstrip(".,)`'\"")
        if "<" in p or "*" in p or p.startswith("~/.cache"):
            continue
        # paths with spaces ("~/Desktop/Peptide Content") get cut at the space — try extending
        tail = re.match(r"((?: [\w.@()&-]+)+)", body[m.end():m.end() + 80])
        cands = [p]
        if tail:
            words_ = tail.group(1).split(" ")[1:]
            cands += [p + " " + " ".join(words_[:k]).rstrip(".,)`'\"") for k in range(1, len(words_) + 1)]
        if not any(os.path.exists(os.path.expanduser(c)) for c in cands):
            issues.append(("WARN", f"path not found: {p}"))
    return issues, desc


def words(s):
    return {w for w in re.findall(r"[a-z][a-z0-9+-]{2,}", s.lower()) if w not in STOP}


def main():
    targets = sys.argv[1:]
    if targets:
        paths = [t if t.endswith(".md") else os.path.join(t, "SKILL.md") for t in targets]
    else:
        paths = sorted(glob.glob(os.path.join(SKILLS, "*", "SKILL.md")))
    bad, descs = 0, {}
    for p in paths:
        if not os.path.exists(p):
            print(f"✗ {p}: missing")
            bad += 1
            continue
        issues, desc = lint(p)
        descs[os.path.basename(os.path.dirname(p))] = words(desc)
        tag = "✗" if any(l == "ERROR" for l, _ in issues) else ("!" if issues else "✓")
        bad += tag == "✗"
        print(f"{tag} {os.path.basename(os.path.dirname(p))}")
        for level, msg in issues:
            print(f"    {level}: {msg}")
    if not targets:
        names = sorted(descs)
        pairs = []
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                A, B = descs[a], descs[b]
                if A and B:
                    j = len(A & B) / len(A | B)
                    if j >= 0.35:
                        pairs.append((j, a, b))
        if pairs:
            print("\nOverlapping descriptions (may trigger on each other's requests):")
            for j, a, b in sorted(pairs, reverse=True)[:15]:
                print(f"  {j:.2f}  {a} ↔ {b}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
