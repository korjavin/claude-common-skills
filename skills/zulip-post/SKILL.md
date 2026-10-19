---
name: zulip-post
description: Draft and publish a message (announcement, release note, demo update) to a Zulip channel/topic as the Claude bot, with screenshots that render as inline thumbnails. Use when the owner asks to "post to zulip", "announce in zulip", "write a release note for zulip", or to fix a bot post whose image shows only a loading spinner. Bot credentials live in the local stash.
---

# Zulip post as the bot

## Rules

- **Draft first, publish only on an explicit "ok"/"publish".** Write the draft to a scratch file and show it (revdiff, or inline in chat if revdiff can't open). Silence or an empty revdiff exit is not approval.
- **Owner's voice:** short, casual, plain sentences, first person, no emoji, no marketing tour. Match the previous posts in the target topic (read the last few first when asked to "do it as usual").
- **1-2 focused screenshots**, never full pages. No emails, hostnames, URL bars, keys or tokens in the image or text.
- **Privacy:** never write server URLs, channel/stream names or ids, or message ids into skills, repos, beads or PRs. They come from the owner's request or the stash at run time.
- **Asking someone to test:** numbered steps, each with what they should see; the build number from the finished CI run, never predicted; link docs instead of pasting them.
- The post shows the bot as author. If the owner wants it under their own name, hand them the text and image to paste instead.

## Credentials

From stash (see the `stash` skill): `kv get secrets/zulip-claude-bot-site`, `secrets/zulip-claude-bot-email`, `secrets/zulip-claude-bot-key`. Load them into shell variables inside the command; never echo them.

## Publish

```bash
<skill-dir>/scripts/post.sh "<channel name or id>" "<topic>" msg.md [image ...]
```

In `msg.md` put `<upload:file.png>` where each image's link goes, e.g. `[file.png](<upload:file.png>)` on the first line. The script uploads the images, **waits until each thumbnail exists**, substitutes the links, posts, and prints the message id plus whether the rendered message has real thumbnails.

## Why the wait: the spinner bug

Zulip (9+, seen on 12.2) generates image thumbnails in a background worker. A message sent before the thumbnail exists is rendered with `<img class="image-loading-placeholder" ...>` and is supposed to be re-rendered once the thumbnail is done. A bot posts within milliseconds of uploading, lands in that gap, and the re-render doesn't happen: readers see a permanent loading spinner, and the image opens only on click. Humans rarely hit it because typing takes longer than thumbnailing.

The fix is to poll `GET <site>/user_uploads/thumbnail/<path-after-/user_uploads/>/840x560.webp` until it returns 200 `image/webp`, then post.

**Repairing an already-broken post:** force a re-render with a change-and-revert edit. `GET /api/v1/messages/<id>?apply_markdown=false` for the raw text, `PATCH /api/v1/messages/<id>` with that text plus `\n\n.`, then `PATCH` again with the original text. A PATCH with identical content does NOT re-render (it returns success but the placeholder stays). Both edits must fall inside the realm's message-edit time limit (often 10 minutes); past it Zulip answers "The time limit for editing this message has passed". The org owner/admin can lift it under Organization settings → Organization permissions → Message editing → "Time limit for editing messages", then restore it after the repair.

**Checking a post:** `GET /api/v1/messages/<id>` and look at the `<img>` in `content`: `src="/user_uploads/thumbnail/..."` is good, `image-loading-placeholder` is the bug.
