#!/usr/bin/env node
// WCAG A/AA scan: axe-core in real Chromium (Playwright) + a 320px reflow check.
// Deps live in ~/.cache/ada-scan, never in the site's package.json.
//
//   node scan.mjs --dir ./public            serve a static folder and crawl it
//   node scan.mjs --url http://localhost:3000 [--url ...]   crawl a running site
//   node scan.mjs --selftest                prove the harness reports violations
//   options: --max 200 (pages)  --out a11y-scan.json  --no-crawl (only the given URLs)
import { createRequire } from 'node:module';
import { execSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync, statSync } from 'node:fs';
import { createServer } from 'node:http';
import { homedir } from 'node:os';
import { join, extname, resolve, normalize } from 'node:path';

const CACHE = join(homedir(), '.cache', 'ada-scan');
const DEPS = ['playwright@1.64.0', 'axe-core@4.14.0'];
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

function deps() {
  if (!existsSync(join(CACHE, 'node_modules', 'axe-core'))) {
    mkdirSync(CACHE, { recursive: true });
    console.error(`installing ${DEPS.join(' ')} into ${CACHE} ...`);
    execSync(`npm install --silent --prefix "${CACHE}" ${DEPS.join(' ')}`, { stdio: 'inherit' });
    execSync(`"${join(CACHE, 'node_modules', '.bin', 'playwright')}" install chromium`, { stdio: 'inherit' });
  }
  const req = createRequire(join(CACHE, 'package.json'));
  return { chromium: req('playwright').chromium, axeSrc: readFileSync(req.resolve('axe-core/axe.min.js'), 'utf8') };
}

const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const all = (k) => args.flatMap((a, i) => (a === k ? [args[i + 1]] : []));

const MIME = { '.html': 'text/html', '.htm': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.mjs': 'text/javascript',
  '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif',
  '.webp': 'image/webp', '.woff2': 'font/woff2', '.woff': 'font/woff', '.json': 'application/json', '.ico': 'image/x-icon' };

function serve(dir) {
  const root = resolve(dir);
  const srv = createServer((req, res) => {
    let p = normalize(join(root, decodeURIComponent(new URL(req.url, 'http://x').pathname)));
    if (!p.startsWith(root)) { res.writeHead(403).end(); return; }
    if (existsSync(p) && statSync(p).isDirectory()) p = join(p, 'index.html');
    if (!existsSync(p) && existsSync(p + '.html')) p += '.html';
    if (!existsSync(p)) { res.writeHead(404).end('not found'); return; }
    res.writeHead(200, { 'content-type': MIME[extname(p).toLowerCase()] || 'application/octet-stream' }).end(readFileSync(p));
  });
  return new Promise((ok) => srv.listen(0, '127.0.0.1', () => ok({ srv, url: `http://127.0.0.1:${srv.address().port}/` })));
}

// Settle before axe: contrast measured on a half-painted page invents findings (see references/sources.md, 84emllc).
async function settle(page) {
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.evaluate(() => document.fonts && document.fonts.ready).catch(() => {});
  await page.waitForTimeout(600);
}

async function axe(page, axeSrc) {
  await page.addScriptTag({ content: axeSrc });
  return page.evaluate(async (tags) => {
    const r = await window.axe.run(document, { runOnly: { type: 'tag', values: tags } });
    const slim = (v) => ({ id: v.id, impact: v.impact, help: v.help, helpUrl: v.helpUrl,
      wcag: v.tags.filter((t) => /^wcag\d{3,}$/.test(t)),
      nodes: v.nodes.slice(0, 10).map((n) => ({ target: n.target.join(' '), html: n.html.slice(0, 200), why: (n.failureSummary || '').slice(0, 300) })),
      count: v.nodes.length });
    return { violations: r.violations.map(slim), incomplete: r.incomplete.map(slim), passes: r.passes.length };
  }, TAGS);
}

// 1.4.10 Reflow: at 320 CSS px wide nothing but data tables/maps may force horizontal scroll.
async function reflow(page) {
  await page.setViewportSize({ width: 320, height: 800 });
  await page.waitForTimeout(300);
  const r = await page.evaluate(() => {
    const vw = document.documentElement.clientWidth;
    const wide = [...document.querySelectorAll('body *')].filter((e) => {
      const b = e.getBoundingClientRect();
      return b.width > 0 && b.right > vw + 1 && !e.closest('table, pre, code, [role=img], svg, video, iframe, canvas');
    }).slice(0, 5).map((e) => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (e.className && typeof e.className === 'string' ? '.' + e.className.trim().split(/\s+/).join('.') : ''));
    return { scrollWidth: document.documentElement.scrollWidth, viewport: vw, overflowing: wide };
  });
  await page.setViewportSize({ width: 1280, height: 900 });
  return { ...r, fail: r.scrollWidth > r.viewport + 1 };
}

// Tab walk: 2.1.2 trap, 2.4.11 focus obscured (elementFromPoint at the centre), 2.4.7 no outline/box-shadow on focus.
// Heuristics -> "needs-review", not verdicts: focus may be shown via background/border, overlap may be intended.
async function keyboard(page) {
  const focusable = await page.evaluate(() => document.querySelectorAll(
    'a[href], button, input:not([type=hidden]), select, textarea, [tabindex]:not([tabindex="-1"]), summary, [contenteditable=""], [contenteditable=true]').length);
  const steps = Math.min(Math.ceil(focusable * 1.5) + 5, 200);
  const seq = [], obscured = new Set(), noVisible = new Set();
  await page.evaluate(() => { document.activeElement?.blur(); window.scrollTo(0, 0); });
  for (let i = 0; i < steps; i++) {
    await page.keyboard.press('Tab');
    const s = await page.evaluate(() => {
      const el = document.activeElement;
      if (!el || el === document.body) return null;
      const name = el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + ((el.getAttribute('href') || el.getAttribute('name')) ? `[${el.getAttribute('href') || el.getAttribute('name')}]` : '');
      const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
      const top = r.width && r.height ? document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2) : null;
      return { name,
        obscured: !!top && !el.contains(top) && !top.contains(el) && !(el.labels && [...el.labels].includes(top)),
        noVisible: (cs.outlineStyle === 'none' || parseFloat(cs.outlineWidth) === 0) && cs.boxShadow === 'none' };
    });
    if (!s) { if (seq.length) break; continue; } // focus left the page = full cycle, no trap
    seq.push(s.name);
    if (s.obscured) obscured.add(s.name);
    if (s.noVisible) noVisible.add(s.name);
  }
  const tail = seq.slice(-20), uniq = new Set(seq).size;
  const trap = seq.length >= steps - 1 && new Set(tail).size <= 3 && uniq < focusable;
  return { focusable, reached: uniq, trap: trap ? [...new Set(tail)] : null,
    obscured: [...obscured].slice(0, 10), noVisibleFocus: [...noVisible].slice(0, 10) };
}

async function links(page, origin) {
  const hrefs = await page.$$eval('a[href]', (as) => as.map((a) => a.href));
  return hrefs.map((h) => { try { const u = new URL(h); u.hash = ''; return u; } catch { return null; } })
    .filter((u) => u && u.origin === origin && !/\.(pdf|zip|png|jpe?g|gif|svg|webp|mp4|mp3|docx?|xlsx?)$/i.test(u.pathname))
    .map((u) => u.href);
}

async function sitemap(base) {
  try {
    const t = await (await fetch(new URL('/sitemap.xml', base))).text();
    return [...t.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1].trim()).filter((u) => !u.endsWith('.xml'));
  } catch { return []; }
}

async function selftest(chromium, axeSrc) {
  const b = await chromium.launch();
  const page = await b.newPage();
  await page.setContent('<html><body><img src="x.png"><input type="text"><a href="#"></a>' +
    '<p style="color:#aaa;background:#fff">low contrast</p><div style="width:900px">wide</div></body></html>');
  await settle(page);
  const r = await axe(page, axeSrc);
  const ids = r.violations.map((v) => v.id);
  const rf = await reflow(page);
  await page.setContent('<html lang="en"><body style="margin:0">' +
    '<header style="position:fixed;top:0;left:0;right:0;height:60px;background:#000"></header>' +
    '<button id="hidden" style="margin-top:10px">under header</button>' +
    '<div style="margin-top:100px"><button id="a" style="outline:none">a</button><button id="b">b</button></div><a href="/x">after</a>' +
    '<script>b.addEventListener("keydown",e=>{if(e.key==="Tab"){e.preventDefault();a.focus()}})</script></body></html>');
  const k = await keyboard(page);
  await b.close();
  const want = ['image-alt', 'label', 'link-name', 'color-contrast', 'html-has-lang'];
  const missing = want.filter((w) => !ids.includes(w));
  const kOk = k.trap && k.obscured.includes('button#hidden') && k.noVisibleFocus.includes('button#a');
  if (missing.length || !rf.fail || !kOk) { console.error('SELFTEST FAIL, missing:', missing, 'reflow:', rf, 'keyboard:', k); process.exit(1); }
  console.log('selftest ok:', ids.join(', '), '+ reflow + trap + obscured + no-focus-ring');
}

async function main() {
  const { chromium, axeSrc } = deps();
  if (args.includes('--selftest')) return selftest(chromium, axeSrc);

  let server, starts = all('--url');
  if (opt('--dir')) { server = await serve(opt('--dir')); starts.push(server.url); }
  if (!starts.length) { console.error('need --dir <folder> or --url <http://...>'); process.exit(2); }
  const max = Number(opt('--max', 200));
  const crawl = !args.includes('--no-crawl');
  const origin = new URL(starts[0]).origin;

  const queue = [...starts, ...(crawl ? await sitemap(starts[0]) : [])];
  const seen = new Set(), pages = {};
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 } });
  while (queue.length && seen.size < max) {
    const url = queue.shift();
    if (seen.has(url)) continue;
    seen.add(url);
    const page = await ctx.newPage();
    try {
      const resp = await page.goto(url, { waitUntil: 'load', timeout: 30000 });
      if (!resp || resp.status() >= 400 || !(resp.headers()['content-type'] || '').includes('html')) { pages[url] = { skipped: resp ? resp.status() : 'no response' }; continue; }
      await settle(page);
      if (crawl) queue.push(...(await links(page, origin)));
      pages[url] = { title: await page.title(), ...(await axe(page, axeSrc)), reflow: await reflow(page), keyboard: await keyboard(page) };
      const v = pages[url].violations, k = pages[url].keyboard;
      console.error(`${v.length ? 'FAIL' : 'ok  '} ${url}  ${v.map((x) => `${x.id}×${x.count}`).join(' ')}${pages[url].reflow.fail ? ' reflow' : ''}` +
        `${k.trap ? ' TRAP' : ''}${k.obscured.length ? ` obscured×${k.obscured.length}` : ''}${k.noVisibleFocus.length ? ` no-focus-ring×${k.noVisibleFocus.length}` : ''}`);
    } catch (e) { pages[url] = { error: String(e).slice(0, 300) }; console.error(`ERR  ${url} ${e}`); }
    finally { await page.close(); }
  }
  await b.close();
  server?.srv.close();

  // Group by rule across pages: the fix usually lives in one shared template/stylesheet.
  const rules = {};
  for (const [url, p] of Object.entries(pages)) for (const v of p.violations || []) {
    const r = (rules[v.id] ||= { id: v.id, impact: v.impact, help: v.help, helpUrl: v.helpUrl, wcag: v.wcag, total: 0, pages: [], sample: v.nodes.slice(0, 3) });
    r.total += v.count; r.pages.push(url);
  }
  const out = { scannedAt: new Date().toISOString(), tags: TAGS, axe: DEPS[1], pageCount: Object.keys(pages).length,
    truncated: queue.some((u) => !seen.has(u)), rules: Object.values(rules).sort((a, b) => b.total - a.total),
    reflowFailures: Object.entries(pages).filter(([, p]) => p.reflow?.fail).map(([u, p]) => ({ url: u, ...p.reflow })),
    keyboardReview: Object.entries(pages).filter(([, p]) => p.keyboard && (p.keyboard.trap || p.keyboard.obscured.length || p.keyboard.noVisibleFocus.length))
      .map(([u, p]) => ({ url: u, ...p.keyboard })), pages };
  writeFileSync(opt('--out', 'a11y-scan.json'), JSON.stringify(out, null, 2));
  console.log(`pages ${out.pageCount}${out.truncated ? ' (truncated at --max)' : ''}, rules failing ${out.rules.length}, ` +
    `nodes ${out.rules.reduce((s, r) => s + r.total, 0)}, reflow failures ${out.reflowFailures.length} -> ${opt('--out', 'a11y-scan.json')}`);
}

main().catch((e) => { console.error(e); process.exit(1); });
