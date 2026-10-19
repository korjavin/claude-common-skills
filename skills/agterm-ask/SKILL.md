---
name: agterm-ask
description: Ask the owner questions as an HTML page in their agterm terminal — each question with its context, evidence and options, answered with buttons and comments and returned as JSON. Use INSTEAD of AskUserQuestion whenever AGTERM_ENABLED=1 — for approvals, picking among options, sign-off on findings or plans, any decision you would otherwise put to AskUserQuestion. Opens in the session the owner is actually watching, including from a background job. Trigger also on "ask me in agterm", "show the question as a page", "дай кнопки", "нарисуй вопрос в HTML".
---

# agterm-ask — questions as a page, answers as JSON

When you need a decision from the owner and `AGTERM_ENABLED=1`, don't call `AskUserQuestion`. Write a spec, run `ask.py`, read the JSON. Outside agterm (`AGTERM_ENABLED` unset), or when `ask.py` exits 1, fall back to `AskUserQuestion`.

```bash
<skill-dir>/ask.py /path/spec.json        # Bash run_in_background: true — the page blocks until answered
```

Run it in the background and wait for the completion notice. The owner may take minutes, and a foreground Bash call times out. Exit 0 prints the answers. Exit 2 means the owner closed the page without answering: ask in chat what they want instead, and don't reopen the page. Exit 1 prints the reason.

## Which session it opens in

`ask.py` puts the page in the agterm session that shows **this** conversation, and switches the owner to it (`--no-follow` opens it quietly instead).
- A foreground Claude uses `$AGTERM_SESSION_ID`.
- A background job (`$CLAUDE_JOB_DIR` set) ignores `$AGTERM_SESSION_ID`, because it belongs to whatever pane started the daemon. It finds the session whose foreground is `claude` and whose title carries the job's name from `$CLAUDE_JOB_DIR/state.json`. If several match, it takes the selected one.
- If nothing matches, it exits 1 with "pass --target". Find the id in `agtermctl tree --json --socket "$AGTERM_SOCKET"`; never guess.
- `--dry-run` prints `{target, page}` without opening anything.

## Spec

Write it to a temp file, `$CLAUDE_JOB_DIR/tmp/` in a background job. All text is escaped; inside text, only `` `code` ``, `**bold**` and line breaks render.

```json
{
  "title": "Curator: что применить",
  "intro": "Первый аудит проекта. Отчёт: `~/…/audit/2026-10-16.md`",
  "lang": "ru",
  "questions": [
    {
      "id": "risky",
      "title": "Auth-PR мёржатся без кросс-ревью",
      "tag": "P1",
      "context": [["Что было", "0 из 5 PR …"], ["Почему", "…"], ["Метрика", "…"]],
      "code": "+ (8) risk — …\n- Exception, …",
      "options": [
        {"id": "accept", "label": "Принять", "recommended": true},
        {"id": "reject", "label": "Отклонить", "description": "оставить как есть"}
      ],
      "multi": false,
      "allow_other": false,
      "note": true
    }
  ]
}
```

- `context` rows carry what the owner needs to decide without opening anything else: what happened, evidence with numbers, the exact change, the cost of each option. One card per decision.
- Phrase each option label as what happens if it is picked ("Apply the diff", "Keep as is"), never as a state the owner could read as a description of the page ("Code example needed").
- `code` / `preview` show a diff, a config or a mockup verbatim.
- `multi: true` gives checkboxes. `allow_other` adds a free-text answer. `note: false` drops the comment box. `lang` is `ru` (default) or `en`.
- When any option is `recommended`, the page shows an "accept recommended" button.

Answer: `{"<id>": {"choice": "accept" | ["a","b"] | null, "other": "", "note": ""}}`. A `null` choice with empty `other` means the owner skipped that question; treat it as no decision. Act on each note. A note on an accepted item changes how you apply it.
