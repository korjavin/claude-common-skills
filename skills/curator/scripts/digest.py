#!/usr/bin/env python3
"""Digest a project's recent Claude Code sessions into compact facts, so the curator never reads
raw transcripts. Usage: digest.py <project-path> [--days N] [--out FILE]

Writes one markdown block per session (main + its subagents) to --out (default
/private/tmp/curator-digest.md) and prints a one-line index per session to stdout.
"""
import argparse, collections, glob, json, os, re, time

ap = argparse.ArgumentParser()
ap.add_argument("project")
ap.add_argument("--days", type=float, default=7)
ap.add_argument("--out", default="/private/tmp/curator-digest.md")
a = ap.parse_args()

root = os.path.expanduser("~/.claude/projects")
proj = os.path.realpath(a.project)
slug = re.sub(r"[^A-Za-z0-9]", "-", proj)
base = re.sub(r"[^A-Za-z0-9]", "-", os.path.basename(proj))
# the project dir, its worktrees (<slug>--claude-worktrees-…), and tmp worktrees named after it
dirs = [d for d in glob.glob(f"{root}/*") if os.path.basename(d).startswith(slug)
        or (os.path.basename(d).startswith("-private-") and base in os.path.basename(d))]
cutoff = time.time() - a.days * 86400


def short(s, n=160):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[:n] + "…"


def scan(path):
    r = dict(title="", start="", end="", models=collections.Counter(), tok=collections.defaultdict(lambda: [0, 0, 0, 0]),
             skills=collections.Counter(), tools=collections.Counter(), errors=[], nerr=0, prompts=[], agents=[],
             compactions=0, cost=None, prs=set(), bash=collections.Counter())
    for line in open(path, errors="replace"):
        try:
            o = json.loads(line)
        except ValueError:
            continue
        t, ts = o.get("type"), o.get("timestamp", "")
        if ts:
            r["start"] = r["start"] or ts
            r["end"] = ts
        if t == "ai-title":
            r["title"] = o.get("aiTitle", "")
        elif t == "cost-state":
            r["cost"] = round(o.get("totalCostUSD") or 0, 2)
        elif t == "pr-link":
            r["prs"].add(o.get("prNumber"))
        elif t == "system" and o.get("subtype") == "compact_boundary":
            r["compactions"] += 1
        elif t == "assistant":
            m = o.get("message", {})
            model, u = m.get("model", "?"), m.get("usage") or {}
            k = r["tok"][model]
            k[0] += u.get("input_tokens", 0); k[1] += u.get("cache_creation_input_tokens", 0)
            k[2] += u.get("cache_read_input_tokens", 0); k[3] += u.get("output_tokens", 0)
            if o.get("attributionSkill"):
                r["skills"][o["attributionSkill"]] += u.get("output_tokens", 0) + u.get("cache_creation_input_tokens", 0)
            for c in m.get("content") or []:
                if c.get("type") != "tool_use":
                    continue
                name, inp = c.get("name"), c.get("input") or {}
                r["tools"][name] += 1
                if name == "Skill":
                    r["skills"]["/" + str(inp.get("skill"))] += 0
                elif name == "Agent":
                    r["agents"].append(f"{inp.get('subagent_type', 'general')}/{inp.get('model', 'inherit')}: {short(inp.get('description', ''), 60)}")
                elif name == "Bash":
                    w = [x for x in (inp.get("command") or "").replace("(", " ").split() if "=" not in x.split("/")[0]]
                    while w and w[0] in ("cd", "&&", "env", "time", "nohup") or (w and w[0].startswith("/") and len(w) > 1 and w[1] == "&&"):
                        w = w[w.index("&&") + 1:] if "&&" in w else w[1:]
                    if w:
                        r["bash"][" ".join(w[:2]) if w[0] in ("git", "gh", "bd", "revmux", "agtermctl", "codex") else w[0]] += 1
        elif t == "user":
            c = o.get("message", {}).get("content")
            if isinstance(c, str):
                if not c.startswith("<") and o.get("origin", {}).get("kind", "human") == "human":
                    r["prompts"].append(short(c, 200))
            else:
                for x in c or []:
                    if x.get("type") == "tool_result" and x.get("is_error"):
                        r["nerr"] += 1
                        if len(r["errors"]) < 5:
                            body = x.get("content")
                            body = body if isinstance(body, str) else " ".join(i.get("text", "") for i in body or [] if isinstance(i, dict))
                            r["errors"].append(short(body, 140))
                    elif x.get("type") == "text" and not x.get("text", "").startswith("<"):
                        r["prompts"].append(short(x["text"], 200))
    return r


def fmt_tok(tok):
    return "; ".join(f"{m}: in {v[0] + v[1] + v[2]:,} (cache-read {v[2]:,}) out {v[3]:,}" for m, v in tok.items() if m != "<synthetic>")


out, index = [], []
sessions = sorted((f for d in dirs for f in glob.glob(f"{d}/*.jsonl") if os.path.getmtime(f) >= cutoff), key=os.path.getmtime)
for f in sessions:
    sid = os.path.basename(f)[:-6]
    r = scan(f)
    subs = []
    for sf in sorted(glob.glob(f"{f[:-6]}/subagents/agent-*.jsonl")):
        meta = {}
        try:
            meta = json.load(open(sf[:-6] + ".meta.json"))
        except (OSError, ValueError):
            pass
        s = scan(sf)
        subs.append(f"  - {meta.get('agentType', '?')}/{meta.get('model', '?')} \"{short(meta.get('description', ''), 50)}\" "
                    f"{s['start'][11:16]}–{s['end'][11:16]} tools {sum(s['tools'].values())} err {s['nerr']} | {fmt_tok(s['tok'])} | {sf}")
    index.append(f"{sid} {r['start'][:16]} {short(r['title'] or (r['prompts'][:1] or ['-'])[0], 70)} | ${r['cost'] or '?'} "
                 f"tools {sum(r['tools'].values())} err {r['nerr']} subagents {len(subs)} compactions {r['compactions']}")
    out += [f"## {sid} — {r['title']}", f"- file: {f}", f"- span: {r['start'][:16]} → {r['end'][:16]}, cost ${r['cost'] or '?'}, compactions {r['compactions']}, PRs {sorted(p for p in r['prs'] if p)}",
            f"- tokens: {fmt_tok(r['tok'])}",
            f"- skills (attributed out+cache-write tokens): {dict(r['skills'].most_common(8))}",
            f"- tools: {dict(r['tools'].most_common(12))}", f"- bash: {dict(r['bash'].most_common(12))}",
            f"- errors ({r['nerr']}): " + " ‖ ".join(r["errors"]),
            f"- owner prompts ({len(r['prompts'])}): " + " ‖ ".join(r["prompts"][:12]),
            f"- agents spawned: " + " ‖ ".join(r["agents"][:20]), "- subagents:", *subs, ""]

open(a.out, "w").write("\n".join(out))
print(f"{len(sessions)} sessions in {len(dirs)} dirs, last {a.days:g}d → {a.out}")
print("\n".join(index))
