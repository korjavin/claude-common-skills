# Sources and site log

Research done 2026-10-10 (Claude web search + AGY second pass). Re-check legal dates before quoting them to anyone.

## Law and standards
- DOJ Title II web rule: WCAG 2.1 AA; Apr 2026 interim final rule moved deadlines to Apr 26 2027 (≥50k population) / Apr 26 2028 (smaller, special districts). [ada.gov first steps](https://www.ada.gov/resources/web-rule-first-steps/), [accessible.org](https://accessible.org/news/doj-extends-ada-title-ii-web-compliance-deadline/), [Univ. of Arizona summary](https://accessibility.arizona.edu/news/doj-issues-interim-final-rule-title-ii-digital-accessibility-compliance-dates)
- Title III (private business): no DOJ technical standard; courts use WCAG 2.1 AA. [DOJ web guidance](https://www.ada.gov/resources/web-guidance/). ~3,100 federal web suits in 2025 (+27%, Seyfarth via vendors); California Unruh Act adds $4,000 statutory damages per visit; NY and CA are hot spots. Overlays don't stop suits. [accessiBe lawsuit guide](https://accessibe.com/ada-website-lawsuits), [Level Access](https://www.levelaccess.com/blog/web-accessibility-lawsuits) — vendor sources, numbers vary.
- HHS Section 504 recipients: WCAG 2.1 AA, May 11 2027 / May 10 2028 (from grant-atl legal-map).
- EU EAA in force since 2025-06-28, EN 301 549 ≈ WCAG 2.1 AA — relevant if sites sell to EU customers.
- [WCAG 2.2](https://www.w3.org/TR/WCAG22/) (W3C Rec, Dec 2024): 2.1 AA + 6 new A/AA criteria, 4.1.1 removed. [Understanding target size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html), [APG patterns](https://www.w3.org/WAI/ARIA/apg/patterns/), [W3C evaluation](https://www.w3.org/WAI/test-evaluate/), [statement generator](https://www.w3.org/WAI/planning/statements/generator/).

## Skills we borrowed from
| Source | Taken |
|---|---|
| [84emllc/claude-wcag-skill](https://github.com/84emllc/claude-wcag-skill) | Four-pass method (scan, keyboard, contrast/zoom, SR); never claim conformance on axe alone; axe `runOnly` WCAG tags; settle fonts ≥500ms before contrast (short settle invents findings); validate the harness with a planted bug; no scanner in project deps |
| [grant-atl/accessibility-audit-kit](https://github.com/grant-atl/accessibility-audit-kit) (MIT) | Fix the shared cause, preserve design, no overlays / rule-silencing; target-size and reflow measurement rules; coverage honesty (sample ≠ whole site); legal map |
| [alirezarezvani/claude-skills a11y-audit](https://github.com/alirezarezvani/claude-skills) (MIT) | Scan → Fix → Verify loop, severity ordering. Its scanner is static regex over source — we use rendered axe instead |
| [humbleteam/accessibility-audit](https://github.com/humbleteam/accessibility-audit) (MIT) | Separate "what this input can prove" from "not verifiable" in reports |
| AGY research | Playwright heuristics for 2.4.11 (elementFromPoint), 2.1.2 (Tab-cycle), reflow 320px; statement structure |

## Looked at, not used (revisit if needed)
- [afabrizi1/accessibility-audit-fix-agent](https://github.com/afabrizi1/accessibility-audit-fix-agent) — repo is a README pointing to a paid marketplace; Angular/React/Vue.
- [mrKanoh/claude-wcag-accessibility-skill](https://github.com/mrKanoh/claude-wcag-accessibility-skill) — prompt collection; has a legacy HTML/jQuery prompt.
- [Community-Access/accessibility-agents](https://github.com/Community-Access/accessibility-agents), [mastepanoski/claude-skills](https://github.com/mastepanoski/claude-skills), [qed42/ai-accessibility-checker](https://github.com/qed42/ai-accessibility-checker), [AccessLint](https://github.com/accesslint/accesslint) — AGY finds, not reviewed.
- MCP: [JustasMonkev/mcp-accessibility-scanner](https://github.com/JustasMonkev/mcp-accessibility-scanner) (axe + Playwright, active). Our script does the same without an MCP.
- Engines: [axe-core](https://github.com/dequelabs/axe-core) (used), [IBM equal-access](https://github.com/IBMa/equal-access) (second engine if axe misses things), [pa11y-ci](https://github.com/pa11y/pa11y-ci) (CI option), [markuplint](https://markuplint.dev/) (static HTML/ARIA lint), Lighthouse.
- accessiBe Code Agent (beta Sep 2026, PR review) — overlay vendor, skip.

## Site log
One line per site processed: date, site, stack, what the skill lacked or got wrong, what was changed.

- 2026-10-10 — skill created; scanner self-test + 3-page fixture pass.
- 2026-10-10 — backlayer-site (static HTML + Go server): scanner passed a focus ring drawn only as a pale box-shadow (~1.1:1) — noVisibleFocus counts any box-shadow as visible, so check focus-ring contrast by hand; crawl misses pages only reachable by form POST (thanks, server error pages) — pass them with --url. No skill change yet.
