#!/usr/bin/env python3
"""Ask the owner questions as an HTML page in an agterm overlay and print the answers as JSON.

Usage: ask.py SPEC.json [--target SESSION] [--no-follow] [--dry-run]
Exit: 0 answered (JSON on stdout), 2 dismissed, 1 error. See SKILL.md for the spec format.
"""
import argparse, html, json, os, re, subprocess, sys, tempfile

UI = {
    "ru": dict(answered="{n} из {t} отвечено", submit="Отправить ответы", recommended="Принять рекомендованные",
               note="комментарий (необязательно)", other="свой вариант…", rec="рекомендую"),
    "en": dict(answered="{n} of {t} answered", submit="Send answers", recommended="Accept recommended",
               note="comment (optional)", other="other…", rec="recommended"),
}


def ctl(*args):
    cmd = ["agtermctl", *args, "--json"] + (["--socket", os.environ["AGTERM_SOCKET"]] if os.environ.get("AGTERM_SOCKET") else [])
    return subprocess.run(cmd, capture_output=True, text=True)


def sessions():
    t = json.loads(ctl("tree").stdout or "{}")
    out = []
    def walk(o):
        if isinstance(o, dict):
            if "sessions" in o and isinstance(o["sessions"], list):
                out.extend(s for s in o["sessions"] if isinstance(s, dict))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(t)
    return out


def resolve_target():
    """The agterm session the owner is actually watching this conversation in."""
    job = os.environ.get("CLAUDE_JOB_DIR")
    if not job:
        # a foreground claude runs in the pane that spawned it, so its env is right
        return os.environ.get("AGTERM_SESSION_ID")
    # a background job inherits AGTERM_* from whichever pane started the daemon: wrong pane.
    # The viewer pane runs `claude` and carries the job's name as its terminal title.
    try:
        name = json.load(open(os.path.join(job, "state.json"))).get("name", "")
    except (OSError, ValueError):
        name = ""
    if not name:
        return None
    hits = [s for s in sessions() if name in (s.get("name") or "") + " " + (s.get("title") or "")
            and os.path.basename((s.get("foreground") or [""])[0]) == "claude"]
    if len(hits) > 1:  # same job name twice: prefer the one the owner has selected
        hits = [s for s in hits if s.get("active")] or hits[:0]
    return hits[0]["id"] if len(hits) == 1 else None


def fmt(text):
    """Escape, then allow `code`, **bold** and line breaks — nothing else reaches the page as markup."""
    s = html.escape(str(text))
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    return s.replace("\n", "<br>")


def render(spec):
    ui = UI.get(spec.get("lang", "ru"), UI["ru"])
    qs = spec["questions"]
    parts, ids = [], []
    for i, q in enumerate(qs):
        ids.append(q.get("id") or f"q{i + 1}")
        qid = html.escape(ids[-1])
        kind = "checkbox" if q.get("multi") else "radio"
        rows = "".join(f"<dt>{fmt(k)}</dt><dd>{fmt(v)}</dd>" for k, v in q.get("context", []))
        code = f"<pre>{html.escape(q['code'])}</pre>" if q.get("code") else ""
        opts = []
        for o in q.get("options", []):
            oid = html.escape(o["id"])
            rec = f' <span class="rec">{ui["rec"]}</span>' if o.get("recommended") else ""
            desc = f'<small>{fmt(o["description"])}</small>' if o.get("description") else ""
            prev = f"<pre>{html.escape(o['preview'])}</pre>" if o.get("preview") else ""
            opts.append(f'<label class="opt"><input type="{kind}" name="{qid}" value="{oid}"'
                        f'{" data-rec" if o.get("recommended") else ""}><span><b>{fmt(o["label"])}</b>{rec}{desc}{prev}</span></label>')
        other = f'<input class="other" data-other="{qid}" placeholder="{ui["other"]}">' if q.get("allow_other") else ""
        note = "" if q.get("note") is False else f'<textarea data-note="{qid}" placeholder="{ui["note"]}"></textarea>'
        tag = f'<span class="tag">{fmt(q["tag"])}</span>' if q.get("tag") else ""
        parts.append(f'<section class="card" data-q="{qid}"><div class="head"><h2>{fmt(q["title"])}</h2>{tag}</div>'
                     f'{"<dl>" + rows + "</dl>" if rows else ""}{code}<div class="opts">{"".join(opts)}</div>'
                     f'<div class="extra">{other}{note}</div></section>')
    has_rec = any(o.get("recommended") for q in qs for o in q.get("options", []))
    intro = f'<p class="sub">{fmt(spec["intro"])}</p>' if spec.get("intro") else ""
    return TEMPLATE.format(title=html.escape(spec.get("title", "Questions")), intro=intro, body="".join(parts), ids=json.dumps(ids).replace("</", "<\\/"),
                           rec_btn=f'<button type="button" class="ghost" id="rec">{ui["recommended"]}</button>' if has_rec else "",
                           submit=ui["submit"], answered=json.dumps(ui["answered"]), lang=spec.get("lang", "ru"))


TEMPLATE = """<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>{title}</title><style>
body {{ background: var(--agterm-background, Canvas); color: var(--agterm-foreground, CanvasText);
  font: 14px/1.5 -apple-system, system-ui, sans-serif; margin: 0; padding: 20px 24px 90px; }}
.page {{ --ok: var(--agterm-color-2, green); --accent: var(--agterm-color-4, blue); --warn: var(--agterm-color-3, orange);
  --dim: color-mix(in srgb, var(--agterm-foreground, CanvasText) 60%, transparent);
  --line: color-mix(in srgb, var(--agterm-foreground, CanvasText) 16%, transparent);
  --fill: color-mix(in srgb, var(--agterm-foreground, CanvasText) 6%, transparent); max-width: 980px; margin: 0 auto; }}
h1 {{ font-size: 20px; margin: 0 0 4px; text-wrap: balance; }} .sub {{ color: var(--dim); margin: 0 0 18px; }}
.card {{ border: 1px solid var(--line); border-radius: 8px; padding: 14px 16px; margin-bottom: 14px; }}
.card.done {{ border-color: var(--ok); }}
.head {{ display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }} .head h2 {{ font-size: 16px; margin: 0; flex: 1; min-width: 240px; }}
.tag {{ font-size: 11px; text-transform: uppercase; letter-spacing: .05em; padding: 2px 7px; border-radius: 4px; border: 1px solid currentColor; color: var(--warn); }}
dl {{ display: grid; grid-template-columns: 120px 1fr; gap: 4px 12px; margin: 10px 0; }} dt {{ color: var(--dim); }} dd {{ margin: 0; min-width: 0; }}
pre {{ margin: 6px 0 0; padding: 8px 10px; border-radius: 6px; overflow-x: auto; font: 12px/1.45 ui-monospace, Menlo, monospace; background: var(--fill); white-space: pre-wrap; }}
code {{ font: 12px ui-monospace, Menlo, monospace; background: var(--fill); padding: 1px 4px; border-radius: 3px; }}
.opts {{ display: grid; gap: 6px; margin-top: 10px; }}
.opt {{ display: flex; gap: 10px; align-items: flex-start; padding: 8px 12px; border: 1px solid var(--line); border-radius: 6px; cursor: pointer; }}
.opt:has(input:checked) {{ border-color: var(--accent); background: var(--fill); }}
.opt input {{ margin-top: 3px; }} .opt span {{ min-width: 0; }} .opt small {{ display: block; color: var(--dim); }}
.rec {{ font-size: 11px; color: var(--ok); margin-left: 6px; }}
.extra {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }}
.extra input, .extra textarea {{ flex: 1; min-width: 220px; height: 32px; font: inherit; padding: 5px 8px; border-radius: 6px; resize: vertical;
  background: transparent; color: inherit; border: 1px solid var(--line); box-sizing: border-box; }}
.bar {{ position: fixed; left: 0; right: 0; bottom: 0; margin: 0; padding: 12px 24px; display: flex; gap: 12px; align-items: center; justify-content: center;
  background: var(--agterm-background, Canvas); border-top: 1px solid var(--line); }}
.bar button {{ font: inherit; padding: 8px 18px; border-radius: 6px; cursor: pointer; border: 1px solid var(--accent); background: var(--accent);
  color: var(--agterm-background, Canvas); font-weight: 600; }}
.bar button.ghost {{ background: transparent; color: inherit; border-color: var(--line); font-weight: 400; }}
#count {{ color: var(--dim); font-variant-numeric: tabular-nums; }}
:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
</style></head><body><div class="page"><h1>{title}</h1>{intro}{body}
<form class="bar" data-agterm="session.overlay.submit"><input type="hidden" name="value" id="value" value="{{}}">
<span id="count"></span>{rec_btn}<button type="submit">{submit}</button></form></div>
<script>
const ids = {ids}, answered = {answered};
const q = s => document.querySelector(s), qa = s => [...document.querySelectorAll(s)];
function sync() {{
  const out = {{}}; let n = 0;
  for (const id of ids) {{
    const sel = CSS.escape(id), picked = qa(`input[name="${{sel}}"]:checked`).map(i => i.value);
    const other = q(`[data-other="${{sel}}"]`)?.value.trim() || "", note = q(`[data-note="${{sel}}"]`)?.value.trim() || "";
    const multi = q(`input[name="${{sel}}"]`)?.type === "checkbox";
    const choice = multi ? picked : (picked[0] ?? null), ok = picked.length > 0 || other !== "";
    q(`section[data-q="${{sel}}"]`).classList.toggle("done", ok); if (ok) n++;
    out[id] = {{ choice, other, note }};
  }}
  q("#value").value = JSON.stringify(out);
  q("#count").textContent = answered.replace("{{n}}", n).replace("{{t}}", ids.length);
}}
document.addEventListener("input", sync); document.addEventListener("change", sync);
q("#rec")?.addEventListener("click", () => {{ qa("input[data-rec]").forEach(i => i.checked = true); sync(); }});
sync();
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--target", help="agterm session id (default: resolved, see SKILL.md)")
    ap.add_argument("--no-follow", action="store_true", help="don't switch the owner to that session")
    ap.add_argument("--dry-run", action="store_true", help="print the resolved session and the page path, open nothing")
    a = ap.parse_args()
    if os.environ.get("AGTERM_ENABLED") != "1":
        sys.exit("not inside agterm: use AskUserQuestion instead")
    spec = json.load(open(a.spec))
    target = a.target or resolve_target()
    if not target:
        sys.exit("cannot tell which agterm session shows this conversation: pass --target <session id>")
    page = os.path.join(os.environ.get("CLAUDE_JOB_DIR", tempfile.gettempdir()), "tmp" if os.environ.get("CLAUDE_JOB_DIR") else "",
                        f"ask-{os.getpid()}.html")
    open(page, "w").write(render(spec))
    if a.dry_run:
        print(json.dumps({"target": target, "page": page}))
        return
    args = ["session", "overlay", "open", "--html", page, "--js", "--block", "--target", target] + ([] if a.no_follow else ["--follow"])
    r = ctl(*args)
    if r.returncode == 2:
        sys.exit(2)
    if r.returncode != 0:
        sys.exit(f"agtermctl failed: {(r.stderr or r.stdout).strip()}")
    res = json.loads(r.stdout)
    res = res.get("result", res)
    res = res.get("pageOutcome", res)
    if res.get("outcome") == "dismissed":
        sys.exit(2)
    print(res["value"])


if __name__ == "__main__":
    main()
