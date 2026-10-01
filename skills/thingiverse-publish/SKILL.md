---
name: thingiverse-publish
description: Publish a 3D-printable model (STL + photos) from the current repo to Thingiverse under the owner's account, link the bought part (e.g. Amazon), put the Thingiverse link in the README, and make the GitHub repo public. Use when the user says "publish on thingiverse", "upload to thingiverse", "share this model so people can print it", or similar.
---

# Publish a model to Thingiverse

Browser automation via `agent-browser` (load `agent-browser skills get core` if unsure of a command).
Credentials live in stash: `kv get secrets/thingverse-email`, `kv get secrets/thingverse-password`
(note the "thingverse" spelling). Never echo them.

## 1. Prepare the repo

- Read README; collect: printable files (`*.stl`, `*.3mf`), images (`preview*.png`, photos), print notes, dimensions.
- If the user gave a product link, strip tracking: `https://www.amazon.com/dp/<ASIN>`. Add a short
  "Sensor"/"Part" section with it to README.
- Add a `## License` section (default CC BY 4.0 unless the user says otherwise — must match Thingiverse license).
- Commit, push. Make public only if asked:
  `gh repo edit <owner>/<repo> --visibility public --accept-visibility-change-consequences`

## 2. Log in (headed — headless is stopped by Cloudflare)

Headless gets a Cloudflare "verify you are human" wall. Headed passes on its own. Do NOT click the
challenge checkbox yourself; if headed still shows it, ask the user to click it in the window.

```bash
export AGENT_BROWSER_SESSION=thingiverse AGENT_BROWSER_HEADED=1   # set in every Bash call
agent-browser --idle-timeout 0 open https://www.thingiverse.com/login
agent-browser wait 5000; agent-browser snapshot -i -c
# click "Use email and password", then:
agent-browser fill <email-ref> "$(kv get secrets/thingverse-email)" >/dev/null
agent-browser fill <pw-ref> "$(kv get secrets/thingverse-password)" >/dev/null
agent-browser click <"Log in"-ref>
```

Landing on `/membership?...` (supporter upsell) means login succeeded — ignore it.

## 3. Fill the upload form

Open `https://www.thingiverse.com/thing:0/edit` (`/upload` is a 404).

- **Files:** `agent-browser upload <"Choose Files"-ref> $PWD/model.stl $PWD/preview.png ...` (absolute paths),
  then `wait 15000`. First image becomes the cover — put the best render first.
- **Name:** `fill` the "Enter a name for your Thing" textbox.
- **Summary** (markdown): `fill` the description textbox. Include: what it is, part link, GitHub
  source link, `## How it works`, `## Printing` (orientation, supports, material, size), `## Tuning`.
- **Category:** click top category, then a subcategory (e.g. Household → Office).
- **AI Generated Content:** check it when the model/generator script was made with Claude.
- **Tags:** for each tag: `fill <combobox-ref> "tag"`, `wait 1200`, `press Enter`. (Typing without the
  wait concatenates everything into one tag.) `press Escape` after.
- **License:** click the license combobox, pick the option matching README (CC BY = "Creative Commons - Attribution").
- **Terms & Conditions** checkbox: must be checked to publish.

Ads and sticky banners often cover elements ("Element is covered by ..."). Fall back to JS, wrapped
in an IIFE (top-level `const` collides across evals):

```bash
agent-browser eval '(()=>{[...document.querySelectorAll("button")].find(b=>b.textContent.trim()=="Office").click()})()'
agent-browser eval '(()=>{const x=[...document.querySelectorAll("input[type=checkbox]")].at(-1); if(!x.checked) x.click(); return x.checked})()'  # last checkbox = Terms
```

Before publishing, take `agent-browser screenshot --full <scratchpad>/form.png` and Read it to verify.

## 4. Publish and link back

```bash
agent-browser eval '(()=>{[...document.querySelectorAll("button")].find(b=>b.textContent.trim()=="Publish").click()})()'
agent-browser wait 8000; agent-browser get url     # -> https://www.thingiverse.com/thing:<id>
agent-browser read | grep -i -E "license|<part-id>"   # sanity check
agent-browser close
```

Add `On Thingiverse: <url>` under the README title, commit, push.

## Report

Thing URL, repo URL, and any choices made on the user's behalf (license, AI flag, terms accepted, category).
