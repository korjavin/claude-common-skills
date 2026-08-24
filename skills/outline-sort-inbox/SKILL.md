---
name: outline-sort-inbox
description: Process unsorted notes from the user's Outline "Inbox" collection — fetch each linked URL, summarize, tag, set priority, file under a topical folder in the "SortedInbox" collection, then remove from "Inbox". Use when the user asks to sort/process/organize/triage their Outline inbox, e.g. "sort my inbox", "process the outline inbox", "clean up the inbox", "go through the inbox".
---

# outline-sort-inbox

Goal: turn raw bookmarks in the **Inbox** Outline collection into well-titled, summarized, tagged, prioritized documents filed under topical folders in the **SortedInbox** collection. After moving an item, it should no longer appear in Inbox (`move_document` to SortedInbox achieves this in one step).

The user reviews items in SortedInbox later and moves things he finished with elsewhere. Don't worry about that — focus on Inbox → SortedInbox.

## Tools

Use the Outline MCP tools throughout:

- `mcp__claude_ai_outline__list_collections` — find Inbox / SortedInbox IDs
- `mcp__claude_ai_outline__list_collection_documents` — enumerate Inbox docs and the current SortedInbox folder tree
- `mcp__claude_ai_outline__fetch` (resource=document) — read a single doc
- `mcp__claude_ai_outline__update_document` — rewrite title + body (use `editMode: "replace"`)
- `mcp__claude_ai_outline__move_document` — move to the chosen folder/collection
- `mcp__claude_ai_outline__create_document` — create a new topical folder doc when needed
- `mcp__claude_ai_outline__create_attachment` — upload an image (only when worth saving locally)
- `WebFetch` — fetch + summarize a URL's content. Prefer `gh` CLI for `github.com` URLs.

## Args

The user may pass a count or word after the slash command:

- no arg → process the **entire Inbox** in batches of 10, reporting progress after each batch and continuing automatically until the Inbox is empty (or only `#cant-fetch` items remain). Do not pause for confirmation between batches.
- `N` (a number) → process up to N items, then stop.
- `1` or `one` → process exactly one item, very useful for first-run sanity check.
- `B=K` (e.g. `B=5`, `B=20`) → override the default batch size for the no-arg flow.

Batch report format (after each batch): `Batch <i>: <n> items processed → <folders touched>. Remaining: <m>.` List newly created folders and any `#cant-fetch` items in the report. After the final batch (Inbox empty), print the same compact summary as `all` runs used to.

The pre-existing `all` keyword is still accepted as a synonym for the no-arg form.

## Step 0 — Discover the workspace

Always do this fresh, never hard-code IDs:

1. Call `list_collections` and locate the collections named exactly `Inbox` and `SortedInbox`. Save their IDs.
2. Call `list_collection_documents` on **SortedInbox** to learn the current folder tree. Note every existing top-level folder document and its children — these are the "topics" already in use. **Prefer existing folders over creating new ones.**
3. Call `list_collection_documents` on **Inbox** to get the list of items to process. Iterate oldest-first (top of the list as returned).

## Step 1 — Read one Inbox item

For each item:

1. `fetch` the document. The result has two parts: the JSON metadata (id, title, etc.) and the raw markdown body (separate output entry).
2. Classify the entry:
   - **Pure URL** — title and/or body are just a link.
   - **URL + user commentary** — title is a URL but body has user notes, or vice-versa.
   - **Pure text** — no URL at all (e.g., a quote, a thought, a German vocabulary list).
   - **OPML pair** — body has a parent line and a nested child URL (legacy Dynalist shape, e.g. `Title — URL` with the same URL again under it).
   - **Image / Telegram-saved** — body references a Telegram-cached image URL or attachment.

Always keep the user's original commentary verbatim in the final output — they wrote it for a reason. The summary you add is *in addition*, not a replacement.

## Step 2 — Fetch the URL (when applicable)

Try fetching for everything except auth-walled hosts (Confluence, Notion private, Google Docs without sharing) — those go straight to `#cant-fetch` (see below).

For `x.com` / `twitter.com` / `nitter.*`: WebFetch returns 402. Use the **fxtwitter JSON API** instead — it mirrors public tweets without auth and returns clean JSON (text, author, media, quoted tweet, reply chain). Extract the status ID from the URL and:

```
curl -s https://api.fxtwitter.com/status/<status_id>
```

(Username in the path is optional — `api.fxtwitter.com/status/<id>` works.) The response shape is `{ code: 200, tweet: { text, author: { name, screen_name }, media, quote, replying_to, replying_to_status, ... } }`. Use `tweet.text` as the source, `tweet.author.screen_name` for attribution. If `code` is non-200 (deleted, protected, NSFW-gated) → `#cant-fetch`.

Fallback before calling the API: if the bullet/title already contains the visible tweet text (markdown link-text often does), you have the source — skip the API call and process it normally. Only fetch fxtwitter when the URL is bare *or* when reply/thread/media context is needed (see the **Twitter / X — OPML bullet handling rules** section below).

If fxtwitter itself is unreachable (rare, third-party mirror) → `#cant-fetch`.

For `reddit.com`: Claude Code is currently blocked from `reddit.com`. Don't waste a fetch; mark `#cant-fetch` directly.

For everything else: `WebFetch` with a focused prompt like:

> "Summarize this in 3-5 sentences for a personal knowledge base. List the main topic, 2-3 takeaways, and any tools/people/projects mentioned by name."

For `github.com/<owner>/<repo>`: prefer `gh repo view <owner>/<repo>` via Bash — faster, no rate limit.

If WebFetch returns a redirect, follow it once.

### When fetch fails — `#cant-fetch` and keep in Inbox

If fetch fails (auth wall, 402/403, timeout, blocked host, no useful content), **do not create a SortedInbox stub doc**. Instead, leave the item in Inbox tagged `#cant-fetch` so the user can revisit it manually after authorizing or opening in a browser:

- **Collection-based Inbox** (one Outline doc per item): leave the doc in the Inbox collection. Append ` #cant-fetch` to the title (or add a `#cant-fetch` line at the top of the body if the title is locked). Don't `move_document` it.
- **Document-body Inbox** (one Outline doc whose body is a bulleted list of items, e.g. `dynalist/Inbox`): leave the line in place and append ` #cant-fetch` to the line via a `patch` edit. Don't remove the line.

Bare `reddit.com` URLs, YouTube videos that timed out, archive.is pages, FB/Confluence/Google-Docs auth walls — all `#cant-fetch`. (Bare X URLs are *not* in this list anymore — try fxtwitter first; only mark `#cant-fetch` if fxtwitter returns non-200.)

**Why this rule:** the user wants unfetched items to stay queued for manual review rather than become noise-stub docs in SortedInbox. Stub docs lose the "still TODO" signal; tagged-and-left-in-Inbox preserves it.

(The user explicitly opted into this behavior — "if something is unfetchable, maybe because i need to authorize there - just keep it in list, don't delete, mark #cant-fetch or similar.")

## Step 3 — Decide topic, tags, priority

### Topic (folder)

The user's existing taxonomy (visible in his other collections) suggests these natural top-level buckets. Use them as a *seed* — match the most specific existing folder first, only create a new one when an item doesn't fit:

- **Engineering** — Go, Python, Rust, Databases, Distributed Systems, Security & Crypto, DevOps & Kubernetes, System Design, Web Scraping
- **AI & ML** — Agents & MCP, RAG & Memory, LLMs & Prompts, AI Tooling
- **Career & Leadership** — Team Lead, Hiring, Books
- **Germany** — Taxes & Bureaucracy, Immigration, Banking, Housing, Cars & Mobility, Daily life
- **Languages** — German, English
- **Self-hosted & Tools**
- **Media** — Movies & Series, Books to read, YouTube & Podcasts
- **3D Printing**
- **Crypto / Web3**
- **Misc / To Triage** — only when nothing else fits

**Rule of thumb:** if 2+ existing items already live in a folder that fits, use it. Don't create a new folder for one-off items — put them in the closest broader folder. After a session, if any one folder has grown unwieldy or two folders overlap, fix it (see Step 6).

To create a folder: `create_document` with the folder name as title, a short description as body (e.g., `> Notes about Go programming, libraries, internals.`), and `collectionId` = SortedInbox (or `parentDocumentId` for sub-folders).

### Tags

Append `#tag` hashtags to the body. Lowercase, kebab-case for multi-word. Aim for 3–6 tags per item, mixing broad and specific:

- Broad: `#go`, `#rust`, `#python`, `#ai`, `#llm`, `#self-hosted`, `#germany`, `#leadership`
- Specific: `#mcp`, `#rag`, `#wegzugsteuer`, `#deutschlandticket`, `#sso`, `#crdt`

Reuse tags consistently — search `list_documents` with `query: "#mcp"` to see if the tag is already in use before introducing a near-duplicate.

### Priority

Best-effort guess; user can always change it. Use one of `high` / `medium` / `low`:

- **high** — actionable / time-sensitive (events, deadlines, security advisories about tools the user uses), or directly tied to current work themes (AI agents, RAG, MCP, leadership). Tweets/posts from people user follows often (e.g., recurring authors in his archive) lean higher.
- **medium** — interesting technical content, tools worth trying later, books to read.
- **low** — entertainment, fun facts, light reading, history trivia, memes.

If unsure, pick `medium`.

## Step 4 — Rewrite the document

Use `update_document` with `editMode: "replace"`. New title should be a **short descriptive title** (not the URL). Body template:

```markdown
> **Source:** [<original URL>](<original URL>)
> **Type:** article | repo | tweet | thread | video | gist | image | note
> **Priority:** high | medium | low
> **Tags:** #tag1 #tag2 #tag3

## Summary
<2–5 sentence summary in English. Preserve key proper nouns / project names verbatim.>

## Key takeaways
- <bullet>
- <bullet>

## Original note
<verbatim user commentary if there was any; omit this section if there was none>
```

### Always format URLs as clickable markdown links

**Critical:** Outline does **not** auto-link bare URLs in blockquotes or doc body — they render as plain text and the user has to copy-paste. Use markdown-link syntax `[label](url)` for *every* URL you write into a doc body. In particular:

- The `**Source:**` line — wrap the URL in `[url](url)` so the URL itself is the visible label *and* clickable. (Don't change "url" to a fancy title here — the user wants to recognize the host at a glance.)
- Cross-references to other docs / "open in browser" prompts → `[open in browser](url)` or `[t.co link](url)`.
- Any URL in `## Tools / projects mentioned`, in the body of `## Key takeaways`, or anywhere else → wrap it.
- Same rule applies when writing into folder description bodies.

If you're listing a tool/product where the natural label *is* the product name (e.g., "**Tools:** ChromaDB, LangChain, …"), and you want the names to be clickable, write each as `[ChromaDB](https://www.trychroma.com/)`. If you don't have/know the URL, leave the name as plain text — don't invent URLs.

The only place a bare URL is acceptable is inside a fenced code block where it represents config / CLI input, not a link to follow.

### Title

- Pick something a future-you would scan and recognize. Examples:
  - `https://github.com/topoteretes/cognee` → `cognee — open-source AI memory layer`
  - `https://x.com/Ildar_De/status/...` → `Ildar — DA-EU permanent residence explainer`
  - `https://blog.doyensec.com/...mcp-nightmare...` → `MCP security pitfalls (Doyensec)`
- If the source is in Russian/German and the title would naturally be in that language, keep it in the original language — don't translate just to translate.
- Don't invent facts. If WebFetch failed, summary should say `(URL not fetched — classified by title)` and you may infer cautiously from the URL slug only.

## Step 5 — Move to the chosen folder

`move_document` with `id` = the doc and `parentDocumentId` = the chosen folder's ID. The doc moves out of Inbox in the same call (Outline's move is atomic across collections).

If the chosen target is the SortedInbox root rather than a sub-folder, pass `collectionId` = SortedInbox and omit `parentDocumentId`.

## Step 5b — Merge duplicates instead of creating siblings

Before moving, check whether the destination folder (or the wider SortedInbox) already has a doc about the *same underlying thing*. If yes, merge — don't create a near-duplicate sibling.

**What counts as "the same thing":**
- Same canonical URL (any of: identical link, same `github.com/<owner>/<repo>`, same arxiv/youtube/imdb id, same root domain + same product/article).
- Different sources that point at the same concept (e.g., one tweet linking the cookbook + one article reviewing the cookbook → both are about *the cookbook*).
- Two posts about the same product/event/person where the second adds context rather than introducing a new topic.

**How to check:** `list_documents` with `query: "<distinguishing keyword>"` (product name, author, repo slug) scoped to `collectionId` = SortedInbox. If the existing doc title or body already names the URL/product, treat it as the canonical doc.

**How to merge:**
1. `update_document` on the existing canonical doc with `editMode: "append"`. Append a new section under a heading like `## Additional source <N>` containing:
   - the new URL (formatted as a clickable markdown link),
   - 1–3 sentence summary of what *this* source adds beyond the canonical doc,
   - the verbatim user commentary from the new Inbox item (under `### Original note`),
   - a `**Forwarded by:**` line if the new item was a Telegram forward.
2. `move_document` the now-redundant Inbox item to **Trash** is **not** allowed — instead, archive it: leave it in Inbox tagged `#merged-into-<short-slug>` so the user can verify and delete manually. Bias toward keeping evidence: if you're <80% sure it's a true duplicate, file as a normal sibling instead and add a cross-reference line ("See also: [canonical doc title](url).") in both bodies.

**Why this rule:** the user's archive already has cases like multiple Claude-Cert-prep posts arriving days apart, or several tweets about one product. Filing each as its own sibling fragments the topic and forces the user to reconcile them later. Merging at sort-time keeps the topical view clean and preserves every source link inside one doc.

(If the only difference between two siblings is *commentary tone*, still merge — the original commentary is preserved verbatim under each `## Additional source` block.)

## Step 6 — Light refactoring (allowed, encouraged when obvious)

Refactor *during* a session if any of these are clearly true:

- Two existing folders overlap (e.g., `RAG` and `Memory` accumulating siblings) → merge by moving children into one and either repurposing or removing the empty folder.
- A folder has grown past ~15 children with internal sub-themes → split into sub-folders (`AI & ML/RAG`, `AI & ML/Agents`).
- An item placed earlier in the session would fit a folder that didn't exist yet → re-`move_document` it.

Do **not** do large reorganizations without checking in with the user first. "Light" = at most 2-3 moves per session beyond the new items.

## Step 7 — Reporting

After **each batch of 10** in the no-arg / `all` flow, and once at the end of an `N`-item run:

- Print a compact summary: `Batch <i>: <n> items processed → <folders touched>. Remaining: <m>.`
- List any newly created folders in this batch.
- List any items where you fell back to URL-only classification or that were tagged `#cant-fetch` (so the user knows which need a human eye).
- In the no-arg / `all` flow, **continue automatically** to the next batch without asking — only stop when the Inbox is empty (or only `#cant-fetch` items remain). For `N` runs, stop after N items and ask whether to continue.

When the Inbox is fully drained (or only `#cant-fetch` items remain), print a final session summary: total items processed, any newly created folders across the run, and the count of `#cant-fetch` items left behind for manual review.

## Patterns to watch for (from the user's archives)

- Very common URL hosts: `x.com`/`twitter.com`, `github.com`, `habr.com`, `vas3k.club`, `livejournal.com`, `reddit.com`, `youtube.com`, `latent.space`, `clickhouse.com`, `news.ycombinator.com`, `medium.com`.
- Frequent recurring topics in this user's stream: **MCP, RAG, AI agents, LLM memory systems, prompt engineering, Go internals, Postgres/ClickHouse/DuckDB, system design, Kubernetes, security/crypto (E2EE, passkeys, RSA), team leadership, self-hosted tools (Immich, Paperless, Frigate, Home Assistant), Germany expat life (taxes, immigration, ETF/Wegzugsteuer, mortgages, cars), German language learning, books on management.**
- Multilingual content (Russian / German / English) — keep the original wording in quotes; write the summary in English by default unless the source is German *and* the user keeps a German-only collection (use the original then).
- "OPML-pair" entries (`Tweet: <text>` followed by nested `URL: <link>`) — treat the parent text as the user's note, the child URL as the source.
- Pure quotes/thoughts (no URL) — these are notes-to-self. File under a `Notes/Quotes` folder; don't try to fetch anything.

## Twitter / X — OPML bullet handling rules

The `dynalist/twitter saved` export shape is one bullet per saved tweet:
- Parent line: `Tweet: <visible tweet text>`
- Child line: `URL: https://twitter.com/<user>/status/<id>`

The parent line contains the tweet text *as the user saw it*, so the API call is usually unnecessary for the body summary. But these specific patterns require fxtwitter:

### Replies (`@<handle>` at start of tweet text) — find the original or `#cant-fetch`

Reply tweets only make sense alongside their parent. Don't file them alone, and don't guess at the missing context.

1. fxtwitter the saved status. The response includes `replying_to` (parent's `screen_name`) and `replying_to_status` (parent's status ID).
2. If `replying_to_status` is non-null, fxtwitter the parent: `curl -s https://api.fxtwitter.com/status/<replying_to_status>`. You now have the conversation context.
3. Title and summarise the *combined* parent + reply as a single doc (treat as a 2-tweet thread; preserve both `tweet.text` blocks verbatim under `## Original note`).
4. If the parent is non-200 (deleted/protected/walked-back), or fxtwitter itself fails on either status, mark the saved reply `#cant-fetch (orphan reply — parent unavailable)` and **leave it in the source list**. Do not file a context-less reply as a SortedInbox doc.

### Throwaway one-liners and link-only tweets — fetch what they point to

Some bullets are nearly content-free — `Вот тут <link>`, one-word reactions, "this guy is paid $35,000…" with the real story in an embedded URL or image. The *real* content lives in what the tweet points to. In priority order:

1. **External link in the tweet text or via fxtwitter `tweet.facets[].url`** → fetch that target (WebFetch / fxtwitter for inner-tweet / `gh repo view` if GitHub) and process the saved tweet as a wrapper around the linked content. The tweet quote becomes the user's commentary; the linked content becomes the summary.
2. **Image (no link)** → use the image-capture path in the **Image handling** section below — the image *is* the content.
3. **Part of a longer thread by the same author** → fxtwitter the saved status to check `replying_to_status`; walk backwards to the thread root and file the whole thread (see thread rules below).
4. **None of the above (pure mood / joke / meta-comment)** → still file as a low-priority Notes-folder entry, preserving the original quote verbatim. The user wants the joke / mood preserved as evidence of who he was reading and when, not deleted.

### Threads — group by *thread*, not by author; long threads get their own doc

The user keeps multiple bullets that belong to one tweet thread. Detect a thread *via the reply chain* (`replying_to_status`), not by guessing from author + topical proximity.

1. For any saved tweet that is part of a thread, fxtwitter both the saved status and (recursively, up to ~5 hops) any `replying_to_status` parents — and any directly-linked `quote` tweets. Stop walking when you hit a status whose author differs from the thread's primary author or whose `replying_to_status` is null.
2. **Short threads (2–4 tweets)** — merge into one SortedInbox doc, with each tweet under its own `### Tweet N — <date>` sub-section. File under the topic folder that fits the thread's content.
3. **Long threads (≥5 tweets)** — give the thread its own dedicated SortedInbox document. Title it after the thread's lede / topic, *not* the author handle. Each tweet still gets its own `### Tweet N` sub-section so the user can scan. The dedicated doc still lives under a topic folder; "long thread" doesn't change the folder choice, only the doc-vs-section choice.
4. If two saved bullets from the same author are *not* connected by `replying_to_status` (different topics, different days), they are **not** a thread — file as separate docs. Same-author proximity in the saved list is not enough.

### Why these rules

The user explicitly opted into them after a sanity-check run on `dynalist/twitter saved`:

- "we should find original, if not, leave it as unprocess with mark #cant-fetch or similar" → reply rule.
- "we should go by provided link, or look at the twitter thread, or maybe image attached" → throwaway-tweet rule.
- "i'd capture image" → image rule (see below; default is *capture* for tweets, opposite of the article default).
- "group not by author but thread, if thread is long put it into document" → thread rule.

## Image handling

Only download and re-attach an image if it is the *primary* content (e.g., a screenshot the user saved with no useful URL, or an infographic that would be lost if the host went down). Otherwise, leave as a markdown image link.

To save: `curl -L -o /tmp/<name>.<ext> <url>` → `create_attachment` with the file size + content type → upload to the returned uploadUrl with `curl -F` → embed the returned attachment URL in the document body.

Skip this for normal article hero images.

### Tweet images — default to capturing

For tweets saved in `dynalist/twitter saved` (and any other `x.com`/`twitter.com`/`nitter.*` source), **invert the default**: capture every attached image unless it's clearly a marketing preview the tweet text already describes.

1. fxtwitter the status; iterate `tweet.media.photos[]` (and `tweet.media.videos[]` for thumbnails — videos themselves can't be embedded, but the thumbnail anchors the doc).
2. Each `photo.url` already points at the original-resolution image; no `?name=orig` rewrite needed.
3. `curl -L -o /tmp/tweet-<status_id>-<n>.<ext> <photo_url>` → `create_attachment` → `curl -F` upload → embed the returned attachment URL in the doc.
4. If `tweet.media` is null/empty, no capture — text-only tweet.

Reason for the inversion: a lot of saved tweets (burnout bingo, supernova animations, 3D-printed gadgets, screenshots of articles) carry their meaning entirely in the image. The bullet text is "look at this" and the link goes to a dead/rate-limited tweet host. Capturing locally guarantees the doc remains useful even if the tweet is later deleted.

## Failure modes

- **Outline 5xx / 404** — retry once after a short pause; if still failing, skip the item and note it in the final report.
- **WebFetch can't reach the URL** (auth wall, 402/403, timeout, blocked host, redirected to login, no useful content) — do **not** create a stub doc; tag the item `#cant-fetch` and leave it in Inbox per Step 2. Surface the count in the final report.
- **Doc can't be moved (permission error)** — leave it in Inbox, add a note in the report.
- **Stale memory of folder IDs** — folder IDs don't change once created, but if a previous run's folder was deleted by the user, recreate it on demand.

Never delete an Inbox document; only move it. The user's source of truth is the move action — if a doc is still in Inbox (or its line is still in the doc-body Inbox), it wasn't processed. `#cant-fetch` items are *intentionally* still in Inbox awaiting manual review — they're not "missed", they're queued.
