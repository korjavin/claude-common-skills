---
name: ada-compliance
description: Bring a website repo to ADA-grade web accessibility (WCAG 2.2 AA, which covers 2.1 AA) — scan the rendered site with axe-core in real Chromium plus reflow/keyboard checks, fix the causes in source (vanilla HTML/CSS/JS first, any framework), re-scan, and leave a report with the manual checks a human still owes. Use when the user says "ADA", "make this site accessible", "WCAG", "a11y audit/fix", "accessibility compliance", or runs /ada-compliance in a site repo.
---

# ADA compliance for a website repo

**Goal:** the site meets WCAG 2.2 AA as far as code can prove it, the fixes are in source, and the human gets a short list of what only a person can confirm.

**Legal frame (why WCAG):** ADA Title III (private business) names no technical standard; courts and settlements use WCAG 2.1 AA. Title II (state/local government) requires WCAG 2.1 AA by DOJ rule — Apr 26 2027 (≥50k population) / Apr 26 2028 (smaller). We target **2.2 AA**: it is a superset of 2.1 AA minus removed 4.1.1, so it satisfies both and EU EAA. Never tell the owner the site "is ADA compliant" — say what was tested and what passed. Sources and dates: `references/sources.md`.

## Hard rules

- **Fix source, never add an overlay** (accessiBe, UserWay, AudioEye widgets). Overlays don't defend lawsuits and attract them. If one is installed, recommend removing it.
- **No a11y deps in the site's package.json.** The scanner keeps its own deps in `~/.cache/ada-scan`.
- **A clean axe run is a floor, not a conformance claim.** axe catches ~a third of AA failures.
- **Preserve the design.** Change colours/sizes only as far as the criterion needs; pick the nearest compliant shade, not a new palette. Show the owner every visible change in the report.
- **Never invent content.** Alt text, captions, transcripts, link purpose need meaning. Write alt text only when the image's purpose is obvious from context (logo → "<Brand> logo", product photo with caption); otherwise mark `TODO(a11y)` in the report for the owner. Decorative images get `alt=""`.
- **Semantic HTML before ARIA.** `<button>` not `<div role=button>`; ARIA only where no native element fits, and then follow the [APG pattern](https://www.w3.org/WAI/ARIA/apg/patterns/) including keyboard behaviour.
- Work on a branch `a11y/wcag-aa`. Commit per fix group. Push/PR only when the owner says so.

## 1. Recon

- Read README / package.json / build config. Classify: **static** (HTML files served as-is), **built static** (SSG → output folder), **server/SPA** (needs a running server).
- Get a URL to scan:
  - static → `--dir <folder>` (the scanner serves it itself);
  - built → run the build, then `--dir <output>`;
  - server/SPA → start the dev/preview server in the background, `--url http://localhost:PORT`.
- Find shared pieces: common header/footer/nav (includes, partials, copy-pasted blocks across HTML files), global CSS, design tokens/variables. Most fixes belong there.
- Note third-party embeds (maps, video players, forms, chat widgets, cookie banners) — their insides are not ours to fix; list them for the statement.

## 2. Scan (baseline)

```bash
SCAN=~/.claude/skills/ada-compliance/scripts/scan.mjs
node $SCAN --selftest                       # once per machine/session: harness must report planted bugs
node $SCAN --dir public --out /tmp/a11y-before.json      # or --url http://localhost:3000
```

Options: `--max N` pages (default 200; output says if truncated), `--no-crawl` to scan only given `--url`s, repeated `--url` for pages not linked from anywhere. It crawls same-origin links + `/sitemap.xml`.

Output JSON: `rules[]` grouped across pages (id, impact, WCAG tags, total nodes, pages, sample selectors/HTML) — **work from this, it points at shared causes**; `reflowFailures[]` (1.4.10 at 320px); `keyboardReview[]` per page: `trap` (2.1.2), `obscured` (2.4.11, focus hidden under sticky header/banner), `noVisibleFocus` (2.4.7 suspects — focus may be shown by background/border, verify); `pages{}` with `incomplete[]` = axe couldn't decide (often contrast on images/gradients) → check by hand.

Keep scan JSON out of the repo (`/tmp`), it's raw.

## 3. Fix

Order: blockers first (keyboard, names/labels, alt, contrast of body text), then the rest. Fix the shared template/stylesheet once, not each page. For vanilla sites with copy-pasted headers, fix all copies in one sweep (`rg` for the snippet) and say so in the commit.

Common fixes:

| Issue (axe id) | Fix |
|---|---|
| `html-has-lang`, `document-title` | `<html lang="en">`, unique meaningful `<title>` per page |
| `image-alt`, `role-img-alt`, `input-image-alt` | meaningful alt, or `alt=""` if decorative; SVG icons: `aria-hidden="true"` + text on the control |
| `link-name`, `button-name` | visible text, or `aria-label` on icon-only controls (label must contain any visible text — 2.5.3) |
| `label`, `select-name` | `<label for>`; placeholder is not a label; group radios with `<fieldset><legend>` |
| `color-contrast` | darken/lighten the token: 4.5:1 text, 3:1 large text (≥24px or ≥18.66px bold) and UI/focus indicators (1.4.11) |
| `heading-order`, `page-has-heading-one`, `region`, `landmark-*` | one `<h1>`, no skipped levels; wrap in `<header> <nav> <main> <footer>` |
| `target-size` (2.5.8) | ≥24×24 CSS px or enough spacing; inline text links are exempt |
| `list`, `listitem`, `definition-list` | `<li>` only inside `<ul>/<ol>` |
| `frame-title` | `<iframe title="...">` |
| `duplicate-id-aria`, `aria-*` | unique ids; valid roles/attrs; don't `aria-hidden` focusable things |
| `meta-viewport` | remove `user-scalable=no` / `maximum-scale=1` |
| reflow | flexible widths, `max-width:100%` on media, wrap long words, avoid fixed px containers; tables may scroll inside a wrapper |
| obscured focus | `scroll-padding-top: <header height>` on `html` for sticky headers; cookie banner must not cover focus |
| no focus ring | never bare `outline:none`; add `:focus-visible { outline: 2px solid <3:1 colour>; outline-offset: 2px }` |
| trap | Esc closes modals and returns focus to the trigger; modals trap focus only while open |

Always add, if missing (cheap, not always caught by axe):
- **Skip link** first in `<body>`: `<a class="skip-link" href="#main">Skip to content</a>` + `<main id="main">`, visible on focus (2.4.1).
- **`prefers-reduced-motion`** guard around non-essential animation/autoplay; autoplaying media/carousels >5s need pause (2.2.2).
- **Forms:** `autocomplete` on personal-data fields (1.3.5), errors as text tied with `aria-describedby`, status messages in `role="status"` (4.1.3), never block paste in password fields (3.3.8).

## 4. Verify

Re-run the scan to `/tmp/a11y-after.json`. Target: `rules` empty, or each remainder explained (third-party, needs owner content). Diff before/after counts for the report. Re-check every `incomplete` and `keyboardReview` entry yourself: open the page with `agent-browser` (screenshot at 1280 and 320, Tab through, look at focus) and resolve it as pass / fixed / owner-check.

The scanner counts any box-shadow as visible focus: check focus-ring contrast (3:1) in the CSS by hand. Pages reachable only by POST/redirect (thanks, error pages) aren't crawled; pass them with `--url`.

If the project has tests or a build, run them — fixes must not break the site.

## 5. Report and hand-off

Write `ACCESSIBILITY.md` in the repo root (committed):

1. Date, standard (WCAG 2.2 AA), tool versions, pages scanned (count, truncated?).
2. Before → after: violations by rule.
3. What changed, grouped (with any visible design changes called out).
4. **Owner TODO** — content only a person can supply: `TODO(a11y)` alt texts, captions/transcripts for video/audio, third-party embeds to replace or vendor-fix.
5. **Manual checks still owed** — copy `references/manual-checklist.md`, tick what you verified, leave the rest.

Accessibility statement page: offer it; create it only with the owner's contact email (ask — never invent one). Template and contents: `references/manual-checklist.md` § Statement.

Optional regression guard, if the owner wants it: a CI step running this scanner (or `pa11y-ci`) on the built site, failing on new violations.

Finish with a short summary to the owner: before/after numbers, the TODO list, the manual checks, and the branch name.

## Improving this skill

This skill is meant to evolve site by site. After each site, if something was missing or wrong (a fix pattern, a false positive, a scanner gap, a stack quirk), update this file or the scanner in `~/Projects/claude-common-skills/skills/ada-compliance/` and add one line to the **Site log** in `references/sources.md`.
