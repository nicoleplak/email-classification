// Multi-user review server checks with Playwright's bundled Chromium. Run through run_server.py.
//   node server_test.cjs <base url> <screenshot dir>
// Invented emails only. Output is numbers and short labels.
const { execSync } = require("child_process");
const path = require("path");
const { createRequire } = require("module");

function loadPlaywright() {
  try {
    return require("@playwright/test");
  } catch {
    const root = execSync("npm root -g", { encoding: "utf8" }).trim();
    return createRequire(path.join(root, "x.js"))("@playwright/test");
  }
}

const [BASE, OUTPUT] = process.argv.slice(2);
const results = [];
const notes = {};
const ok = (name, condition, info) => results.push({ name, pass: !!condition, info });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function until(fn, timeout = 9000) {
  const t = Date.now();
  while (Date.now() - t < timeout) {
    try { if (await fn()) return true; } catch {}
    await sleep(150);
  }
  return false;
}
const shot = (page, name) => page.screenshot({ path: path.join(OUTPUT, `server_${name}.png`), fullPage: false });
const rowIds = (page) => page.$$eval("#rows .row[data-id]", (rows) => rows.map((r) => r.dataset.id));
const stat = (page, k) => page.$eval(`.stat[data-k="${k}"] .stat-v`, (e) => e.textContent.trim());
const hashId = (page) => page.evaluate(() => decodeURIComponent(location.hash.replace("#/email/", "")));

async function signIn(browser, name, options = {}) {
  const context = await browser.newContext({ viewport: { width: 1366, height: 768 }, ...options });
  const page = await context.newPage();
  page.errors = 0;
  page.on("pageerror", (e) => { page.errors++; notes[`script error (${name})`] = String(e.message).slice(0, 160); });
  const t0 = Date.now();
  await page.goto(BASE);
  await page.waitForSelector("#loginDlg[open]", { timeout: 6000 });
  if (name === "Άννα") ok("skeleton rows show while signed out and loading", (await page.locator("#rows .row.skel").count()) > 0);
  await page.fill("#loginName", name);
  await Promise.all([page.waitForNavigation(), page.click("#loginBtn")]);
  await page.waitForSelector("#rows .row[data-id]", { timeout: 8000 });
  notes[`first list after sign-in (${name}), ms`] = Date.now() - t0;
  return { context, page };
}

async function layout(page) {
  // Measure the resting layout, not a frame in the middle of an entry animation.
  await page.evaluate(() => Promise.all(document.getAnimations().filter((a) => a.effect && a.effect.getTiming().iterations !== Infinity).map((a) => a.finished.catch(() => {}))));
  return page.evaluate(() => {
    const W = document.documentElement.clientWidth;
    let outside = 0, cardOverflow = 0;
    for (const el of document.querySelectorAll("main *")) {
      if (!el.getClientRects().length) continue;
      const r = el.getBoundingClientRect();
      if (r.width && (r.right > W + 1 || r.left < -1)) outside++;
    }
    for (const c of document.querySelectorAll("main .card, main .sheet")) if (c.scrollWidth > c.clientWidth + 1) cardOverflow++;
    const dock = document.getElementById("dock");
    const d = dock && dock.getBoundingClientRect();
    return { sideways: document.documentElement.scrollWidth - document.documentElement.clientWidth, outside, cardOverflow,
      dockOnScreen: d ? d.bottom <= innerHeight + 1 && d.top < innerHeight && d.height > 0 : null };
  });
}

async function sizes(browser, cookie) {
  for (const [w, h] of [[1920, 1080], [1366, 768], [1280, 600], [1024, 700], [800, 600], [390, 800]]) {
    const context = await browser.newContext({ viewport: { width: w, height: h } });
    await context.addCookies([{ name: cookie.name, value: cookie.value, url: BASE }]);
    const page = await context.newPage();
    page.errors = 0; page.on("pageerror", () => page.errors++);
    await page.goto(BASE + "#/");
    await page.waitForSelector("#rows .row[data-id]");
    const q = await layout(page);
    ok(`${w}x${h} queue: no sideways scroll, nothing off screen`, q.sideways <= 0 && q.outside === 0 && q.cardOverflow === 0, q);
    if (w === 1366 || w === 390) await shot(page, `queue_${w}`);
    await page.goto(BASE + "#/email/syn001");
    await page.waitForSelector("#assess .hero");
    await sleep(500);
    const e = await layout(page);
    ok(`${w}x${h} email: no sideways scroll, cards fit, save bar on screen`, e.sideways <= 0 && e.outside === 0 && e.cardOverflow === 0 && e.dockOnScreen, e);
    if (w === 1366 || w === 390) await shot(page, `email_${w}`);
    ok(`${w}x${h}: no script errors`, page.errors === 0, page.errors);
    await context.close();
  }
}

async function behaviour(browser) {
  const { context: ca, page: A } = await signIn(browser, "Άννα");
  const { context: cb, page: B } = await signIn(browser, "Νίκος");

  // Queue states and filters
  const counts = { everything: await stat(A, "everything"), unclassified: await stat(A, "unclassified"), classified: await stat(A, "classified"), reviewed: await stat(A, "reviewed") };
  ok("counts: 60 emails, 9 unclassified, 51 to review, 0 reviewed", counts.everything === "60" && counts.unclassified === "9" && counts.classified === "51" && counts.reviewed === "0", counts);
  ok("rows animate in", (await A.$eval("#rows .row[data-id]", (r) => getComputedStyle(r).animationName)) === "rowIn");
  ok("first page shows 50 and a pager", (await rowIds(A)).length === 50 && (await A.locator("#pager .pages").count()) === 1);
  ok("rows are grouped by day", (await A.locator("#rows .day").count()) > 3);

  await A.route("**/api/emails?*", async (route) => { await sleep(700); await route.continue(); });
  await A.click('.stat[data-k="unclassified"]');
  await sleep(150);
  ok("filter change keeps rows and shows a progress line", (await A.locator("#table.busy").count()) === 1 && (await A.locator("#rows .row[data-id]").count()) > 0);
  await until(async () => (await A.locator("#table.busy").count()) === 0);
  await A.unroute("**/api/emails?*");
  const unclassifiedRows = await A.$$eval("#rows .row[data-id] .badge", (b) => b.map((x) => x.className));
  ok("unclassified card lists the 9 unclassified", unclassifiedRows.length === 9 && unclassifiedRows.every((c) => c.includes("b-unclassified")), unclassifiedRows.length);
  await A.click('.stat[data-k="classified"]');
  await until(async () => (await rowIds(A)).length === 50);

  await A.fill("#fQ", "ΣΥΝΘΕΤΙΚΟ ΑΙΤΗΜΑ 12");
  ok("search ignores case and accents", await until(async () => (await rowIds(A)).join() === "syn012"), await rowIds(A));
  await A.click("#clearF");
  await until(async () => (await rowIds(A)).length === 50);
  await A.click("#presetBtn");
  await A.click('#presetMenu button:has-text("Σήμερα")');
  const today = await until(async () => (await rowIds(A)).length === 3);
  ok("date preset 'today' shows today's 3", today, await rowIds(A));
  ok("date range is spelled out", (await A.textContent("#rangeNote")).includes("Παραλαβή"));
  await A.click("#presetBtn");
  await A.click('#presetMenu button:has-text("Όλες οι ημερομηνίες")');
  await until(async () => (await rowIds(A)).length === 50);
  await A.click("#moreF");
  await sleep(350);
  ok("more filters open", (await A.locator("#moreBox:not(.closed)").count()) === 1);
  await A.selectOption("#fLevel", "low");
  ok("certainty filter", await until(async () => { const n = (await rowIds(A)).length; return n > 0 && n < 50; }));
  await A.selectOption("#fLevel", "");
  await until(async () => (await rowIds(A)).length === 50);

  // Presence: Νίκος sees that Άννα has an email open
  const [x, y] = await rowIds(A);
  await A.route("**/api/emails/*", async (route) => { await sleep(600); await route.continue(); });
  await A.click(`#rows .row[data-id="${x}"]`);
  await sleep(200);
  ok("email shows a skeleton while loading", (await A.locator(".email-head.skel").count()) === 1);
  await A.waitForSelector("#assess .hero");
  await A.unroute("**/api/emails/*");
  ok("cards animate in", (await A.$eval("#assess", (a) => a.className)).includes("stagger"));
  ok("queue row shows who has it open", await until(async () => (await B.textContent(`#rows .row[data-id="${x}"] .live-slot`)).includes("Άννα")));
  ok("header shows two people online", await until(async () => (await B.locator("#online .av").count()) === 2));
  await shot(B, "queue_presence");
  await B.click(`#rows .row[data-id="${x}"]`);
  await B.waitForSelector("#assess .hero");
  ok("open email warns who else has it open", await until(async () => (await B.locator("#presenceBanner").textContent()).includes("Άννα")));
  await shot(B, "email_presence");

  // Accept, and the other reviewer updates without reloading
  await A.click("#accept");
  ok("accept saves", await until(async () => (await A.locator("#headBadge .b-reviewed").count()) === 1));
  ok("other reviewer's page updates by itself", await until(async () => (await B.locator(".hero-done").count()) === 1 && (await B.locator(".timeline .tl").count()) === 1));

  // Conflict: Νίκος has unsaved changes when Άννα saves again
  await B.click(".cand >> nth=1");
  ok("unsaved changes are flagged", (await B.locator("#dockState.dirty").count()) === 1);
  await A.click(".cand >> nth=1");
  await A.click("#save");
  ok("second save by Άννα", await until(async () => (await A.locator(".timeline .tl").count()) === 2));
  ok("Νίκος is told his draft is out of date", await until(async () => (await B.locator("#staleBanner").count()) === 1));
  await B.click("#save");
  ok("saving a stale draft asks which version to keep", await until(async () => (await B.locator("#cfDlg[open]").count()) === 1));
  await shot(B, "conflict");
  await B.click("#cfMine");
  ok("keeping my version saves it", await until(async () => (await B.locator("#cfDlg[open]").count()) === 0 && (await B.locator(".timeline .tl").count()) === 3));
  ok("Άννα sees Νίκος's version", await until(async () => (await A.locator(".timeline .tl").count()) === 3));

  // Next skips what someone else has open
  await B.goto(BASE + "#/");
  await B.waitForSelector("#rows .row[data-id]");
  const busy = await A.evaluate(async () => (await (await fetch("/api/next")).json()).id);
  await B.goto(BASE + "#/email/" + busy);
  await B.waitForSelector("#assess .hero");
  await sleep(400);
  const after = await A.evaluate(async () => (await (await fetch("/api/next")).json()).id);
  ok("'next' skips the email someone else has open", busy && after && after !== busy, { busy, after });
  await A.goto(BASE + "#/email/" + y);
  await A.waitForSelector("#assess .hero");
  await A.click("#acceptNext");
  ok("accept and next moves on to free work", await until(async () => { const id = await hashId(A); return id !== y && id !== busy && id.startsWith("syn"); }), await hashId(A));
  await A.waitForSelector("#assess .hero");

  // Keyboard
  await A.goto(BASE + "#/");
  await A.waitForSelector("#rows .row[data-id]");
  const order = await rowIds(A);
  await A.click(`#rows .row[data-id="${order[2]}"]`);
  await A.waitForSelector("#assess .hero");
  await A.keyboard.press("j");
  ok("j opens the next in the list", await until(async () => (await hashId(A)) === order[3]), { want: order[3], got: await hashId(A) });
  await A.waitForSelector("#assess .hero");
  await A.keyboard.press("Escape");
  ok("Esc returns to the queue", await until(async () => (await A.locator("#vQueue:not([hidden])").count()) === 1));

  // An email the model has not classified: a person picks the category
  await A.click('.stat[data-k="unclassified"]');
  await until(async () => (await rowIds(A)).length === 9);
  await A.click("#rows .row[data-id] >> nth=0");
  await A.waitForSelector("#assess .hero");
  ok("unclassified email says so", (await A.locator(".hero-cat.muted").count()) === 1);
  await A.click("#pickOpen");
  await A.fill("#pickQ", "gdpr");
  ok("category search in the picker", (await A.locator("#pickList .option").count()) === 1);
  await A.keyboard.press("Enter");
  await A.click("#pickDone");
  ok("picked category fills the first slot", (await A.locator(".slot.r1:not(.empty)").count()) === 1);
  await A.click("#save");
  ok("saved as reviewed", await until(async () => (await A.locator("#headBadge .b-reviewed").count()) === 1));
  await A.goto(BASE + "#/");
  ok("unclassified count drops to 8", await until(async () => (await stat(A, "unclassified")) === "8"));

  // Activity feed, live
  await A.goto(BASE + "#/activity");
  await until(async () => (await A.locator("#feed .ev:not(.skel)").count()) > 0);
  const before = await A.locator("#feed .ev").count();
  ok("activity lists the saves and the import", before >= 6, before);
  await B.click("#accept");
  ok("activity updates live", await until(async () => (await A.locator("#feed .ev").count()) === before + 1), { before, after: await A.locator("#feed .ev").count() });
  await shot(A, "activity");

  ok("Άννα: no script errors", A.errors === 0, A.errors);
  ok("Νίκος: no script errors", B.errors === 0, B.errors);
  const cookie = (await ca.cookies()).find((c) => c.name === "reviewer");
  await A.click("#logout");
  ok("sign out returns to sign-in", await until(async () => (await A.locator("#loginDlg[open]").count()) === 1));
  await ca.close();
  await cb.close();
  return cookie;
}

async function reducedMotion(browser, cookie) {
  const context = await browser.newContext({ viewport: { width: 1366, height: 768 }, reducedMotion: "reduce" });
  await context.addCookies([{ name: cookie.name, value: cookie.value, url: BASE }]);
  const page = await context.newPage();
  await page.goto(BASE + "#/");
  await page.waitForSelector("#rows .row[data-id]");
  const m = await page.evaluate(() => ({ speed: getComputedStyle(document.documentElement).getPropertyValue("--speed").trim(), view: getComputedStyle(document.getElementById("vQueue")).animationName }));
  ok("reduced motion shortens animations but keeps them", m.speed === ".14s" && m.view === "fadeUp", m);
  await context.close();
}

// Real emails: open every one and measure. Counts only, no screenshots, nothing saved.
async function realData(browser) {
  for (const [w, h] of [[1366, 768], [390, 800]]) {
    const context = await browser.newContext({ viewport: { width: w, height: h } });
    await context.addCookies([{ name: "reviewer", value: encodeURIComponent("Έλεγχος διάταξης"), url: BASE }]);
    const page = await context.newPage();
    page.errors = 0; page.on("pageerror", () => page.errors++);
    await page.goto(BASE + "#/");
    await page.waitForSelector("#rows .row[data-id]");
    const ids = await page.evaluate(async () => {
      const out = [];
      for (let o = 0; ; o += 200) {
        const d = await (await fetch(`/api/emails?status=all&limit=200&offset=${o}`)).json();
        out.push(...d.rows.map((r) => r.id));
        if (out.length >= d.total || !d.rows.length) return out;
      }
    });
    const q = await layout(page);
    ok(`real ${w}x${h} queue fits`, q.sideways <= 0 && q.outside === 0 && q.cardOverflow === 0, q);
    const bad = { sideways: 0, outside: 0, cardOverflow: 0, dockOff: 0, slowOver2s: 0 };
    for (const id of ids) {
      const t = Date.now();
      await page.goto(BASE + "#/email/" + encodeURIComponent(id));
      await page.waitForSelector("#assess .hero", { timeout: 8000 });
      if (Date.now() - t > 2000) bad.slowOver2s++;
      const e = await layout(page);
      if (e.sideways > 0) bad.sideways++;
      if (e.outside) bad.outside++;
      if (e.cardOverflow) bad.cardOverflow++;
      if (!e.dockOnScreen) { bad.dockOff++; notes[`dock off ${w} #${ids.indexOf(id)}`] = await page.evaluate(() => { const d = document.getElementById("dock"), r = d && d.getBoundingClientRect(); return r ? { top: Math.round(r.top), bottom: Math.round(r.bottom), h: Math.round(r.height), vh: innerHeight, scrollY: Math.round(scrollY), doc: document.documentElement.scrollHeight, btns: d.querySelectorAll("button").length } : "no dock" }); }
    }
    ok(`real ${w}x${h}: all ${ids.length} emails fit`, Object.values(bad).every((n) => n === 0), bad);
    ok(`real ${w}x${h}: no script errors`, page.errors === 0, page.errors);
    await context.close();
  }
}

(async () => {
  const browser = await loadPlaywright().chromium.launch();
  let error = null;
  try {
    if (process.argv[4] === "real") await realData(browser);
    else {
      const cookie = await behaviour(browser);
      await sizes(browser, cookie);
      await reducedMotion(browser, cookie);
    }
  } catch (e) {
    error = String(e.message || e).split("\n")[0].slice(0, 300);
  }
  await browser.close();
  const failed = results.filter((r) => !r.pass);
  console.log(`checks: ${results.length}, failed: ${failed.length}`);
  failed.forEach((r) => console.log("  FAIL", r.name, JSON.stringify(r.info)));
  for (const [k, v] of Object.entries(notes)) console.log(" ", k, JSON.stringify(v));
  if (error) console.log("ERROR:", error);
  process.exit(failed.length || error ? 1 : 0);
})();
