# Manual checks (copy into ACCESSIBILITY.md)

Automated scanning covers roughly a third of WCAG AA. Tick what was verified and how; leave the rest for a person.

## Keyboard (no mouse)
- [ ] Every link, button, field, menu, modal reachable with Tab / Shift+Tab, in a logical order (2.1.1, 2.4.3)
- [ ] Focus always visible and never hidden under a sticky header, cookie banner or chat widget (2.4.7, 2.4.11)
- [ ] Menus/dropdowns open with Enter/Space; Esc closes overlays and focus returns to the trigger; no traps (2.1.2)
- [ ] Skip link appears on first Tab and jumps to main content (2.4.1)

## Screen reader (VoiceOver: Cmd+F5 on macOS / NVDA on Windows)
- [ ] Headings list (VO rotor) reads as a sensible outline; landmarks present (1.3.1)
- [ ] Every image read with a meaningful description or skipped if decorative (1.1.1)
- [ ] Buttons/links announce their purpose; icon buttons are not "button" alone (2.4.4, 4.1.2)
- [ ] Form fields announce label, required state, and errors; success/status messages are announced (3.3.1, 4.1.3)

## Visual
- [ ] Zoom to 200%: nothing cut off or overlapping (1.4.4); 400% / 320px wide: no horizontal scroll except tables/maps (1.4.10)
- [ ] Text-spacing override (line-height 1.5, letter 0.12em, word 0.16em, paragraph 2em) does not clip text (1.4.12)
- [ ] Contrast on images/gradients/hover/focus states that axe reported as "incomplete" (1.4.3, 1.4.11)
- [ ] Information not conveyed by colour alone (links in text distinguishable, error states) (1.4.1)
- [ ] Tooltips/popovers on hover: dismissible with Esc, hoverable, don't vanish on their own (1.4.13)

## Content and behaviour
- [ ] Video has captions; audio has transcript; audio description where visuals carry info (1.2.x)
- [ ] Auto-moving content (carousels, autoplay) can be paused; nothing flashes >3×/s (2.2.2, 2.3.1)
- [ ] Time limits can be extended or are absent (2.2.1)
- [ ] Drag interactions (sliders, sortable lists) have a click alternative (2.5.7)
- [ ] Help/contact link in the same place on every page (3.2.6); nav consistent across pages (3.2.3)
- [ ] Login: paste and password managers work; no puzzle-only CAPTCHA (3.3.8)
- [ ] Forms don't ask twice for info already given in the same flow (3.3.7)
- [ ] Third-party embeds (maps, booking, chat, video) checked or listed as known limitations

## Statement

Generate with the [W3C WAI statement generator](https://www.w3.org/WAI/planning/statements/generator/) or write `accessibility.html` with:
1. Target + method, never a status: "We aim to meet WCAG 2.2 Level AA" plus how the site is tested (automated scan, which manual checks). Never write "partially/fully conformant" or "compliant" on the page; it is public and legally exposed.
2. Measures taken: date of last review, automated scan + which manual checks.
3. Known limitations: third-party content and anything in Owner TODO, with an alternative route (email/phone).
4. Feedback contact (owner-provided email/phone) and response time (e.g. 2 business days).
5. Date the statement was last updated.

Link it from the footer of every page.
