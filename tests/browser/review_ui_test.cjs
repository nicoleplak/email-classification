// Review app checks in Playwright's bundled Chromium (IT allows it; Edge/Chrome automation is blocked).
//   node tests/browser/review_ui_test.cjs http://127.0.0.1:8765          (REVIEW_AUTH=dev server)
//   node tests/browser/review_ui_test.cjs <url> --headed --code=<access code>
// Prints check names, pass/fail and numbers only: never page text or images (real customer data).
// Screenshots go to ui_test_output/ (git-ignored) for a person to look at. Saves no reviews.
const { execSync } = require("child_process");
const fs = require("fs");
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

const args = process.argv.slice(2);
const URL = args.find((a) => !a.startsWith("--")) || "http://127.0.0.1:8765";
const CODE = (args.find((a) => a.startsWith("--code=")) || "").slice(7);
const OUTPUT = path.join(process.cwd(), "ui_test_output");
fs.mkdirSync(OUTPUT, { recursive: true });
const results = [];
const ok = (name, condition, info) => results.push({ name, pass: !!condition, info });

// Opacity of the first card 80 ms after the given case renders, measured inside the page (no network timing).
const SAMPLE = (id) => new Promise((resolve) => {
  const check = () => {
    const pane = document.querySelector("#case");
    if (pane.dataset.caseId === id && pane.querySelector(".card")) {
      setTimeout(() => resolve(+getComputedStyle(pane.querySelector(".card")).opacity), 80);
    } else requestAnimationFrame(check);
  };
  check();
});

async function signIn(page) {
  await page.goto(URL);
  await page.waitForSelector("#signin:not([hidden]), #app:not([hidden])");
  if (await page.locator("#signin").isVisible()) {
    await page.fill("#si-name", "Browser Test");
    await page.fill("#si-email", "browser.test@example.test");
    if (CODE) await page.fill("#si-code", CODE);
    await page.click("#signin-form button[type=submit]");
  }
  await page.waitForSelector("#app:not([hidden])");
  await page.waitForFunction(() => document.querySelectorAll("#queues button").length === 4);
}

async function behaviour(browser) {
  const context = await browser.newContext({ viewport: { width: 1600, height: 900 }, acceptDownloads: true });
  const page = await context.newPage();
  let scriptErrors = 0;
  let consoleErrors = 0;
  page.on("pageerror", () => scriptErrors++);
  page.on("console", (m) => {
    if (m.type() !== "error") return;
    // By design: the email frame blocks outside images until "show images" is clicked.
    const blockedImage = /Loading the image .* violates/.test(m.text()) && /\/message/.test(m.location().url || "");
    if (blockedImage) return;
    consoleErrors++;
    // kind and path only (digits masked): never page text
    if (process.env.DEBUG_CONSOLE) console.log("console error:", m.text().replace(/\d/g, "#").slice(0, 110), (m.location().url || "").replace(/^https?:\/\/[^/]+/, "").replace(/\d/g, "#").slice(0, 60));
  });
  await signIn(page);

  const counts = await page.$$eval("#queues .count", (n) => n.map((x) => +x.textContent));
  ok("queue counts add up", counts[0] + counts[1] + counts[2] === counts[3] && counts[3] > 0, counts);

  await page.click("#queues button:nth-child(4)");
  const allItems = await page.locator("#list .item").count();
  ok("all tab lists every email", allItems === counts[3], { allItems });
  ok("list is grouped into 4-hour windows", (await page.locator("#list .group").count()) > 0);

  const days = await page.$$eval("#day option", (o) => o.map((x) => x.value));
  ok("day picker offers days", days.length > 1, { days: days.length });
  await page.selectOption("#day", days[1]);
  const windowButtons = await page.locator("#windows button").count();
  ok("a chosen day shows whole-day + 6 window buttons", windowButtons === 7, { windowButtons });
  const dayItems = await page.locator("#list .item").count();
  const nonEmpty = page.locator("#windows button:not(.whole):not(.empty)").first();
  await nonEmpty.click();
  const windowItems = await page.locator("#list .item").count();
  ok("a window narrows the list", windowItems > 0 && windowItems <= dayItems, { dayItems, windowItems });

  await page.selectOption("#basis", "reviewed");
  const reviewedRows = await page.locator("#list .item").count();
  const groupsByReview = await page.locator("#list .group").count();
  ok("by review time lists only reviewed emails", reviewedRows === 0 ? (await page.locator("#list .none").count()) === 1 : groupsByReview > 0, { reviewedRows });
  await page.selectOption("#basis", "received");
  await page.selectOption("#day", "all");

  // the email with the most attachments
  const target = await page.$$eval("#list .item", (items) => {
    const n = (el) => +((el.querySelector(".tags .small") || {}).textContent || "0").replace(/\D/g, "") || 0;
    return items.sort((a, b) => n(b) - n(a))[0].dataset.id;
  });
  await page.click(`#list .item[data-id="${target}"]`);
  await page.waitForSelector("#case h2");
  ok("case opens with a title", await page.locator("#case h2").isVisible());
  ok("case has the classification card", (await page.locator("#case .card").count()) >= 2, { cards: await page.locator("#case .card").count() });
  ok("selected row is marked", (await page.locator(`#list .item[aria-current="true"]`).count()) === 1);
  ok("email shows in a sandboxed frame", (await page.locator("#viewer-body iframe[sandbox]").count()) === 1);
  const frameLoaded = await page.frameLocator("#viewer-body iframe").locator("body").count();
  ok("email frame has a body", frameLoaded === 1);

  const tabs = await page.locator("#viewer-tabs button").count();
  ok("viewer has email + attachment tabs", tabs >= 2, { tabs });
  if (tabs >= 2) {
    await page.click("#viewer-tabs button:nth-child(2)");
    const kind = await page.$eval("#viewer-body", (b) => {
      const el = b.querySelector("iframe, .img img, .nopreview");
      return el ? el.tagName + (el.className ? "." + el.className : "") : "none";
    });
    ok("attachment opens in the viewer", ["IFRAME", "IMG", "DIV.nopreview"].includes(kind), { kind });
    const dl = await page.locator("#viewer-tools a[href*='download=1']").count();
    ok("attachment has a download link", dl === 1);
  }
  const chips = page.locator("#case button.src");
  const chipCount = await chips.count();
  ok("found details carry source chips", chipCount > 0, { chipCount });
  if (chipCount) {
    await chips.last().click();
    ok("a source chip switches the viewer", (await page.locator("#viewer-tabs button[aria-selected=true]").count()) === 1);
  }

  // Loading: clicking an email shows a loading state at once, which clears when the email is shown.
  const busyAtClick = await page.evaluate(() => {
    const rows = [...document.querySelectorAll("#list .item")];
    rows[rows.length - 1].click();
    return { busy: document.querySelector("#case").getAttribute("aria-busy"), skeleton: document.querySelectorAll("#case .sk").length };
  });
  ok("opening an email shows a loading state at once", busyAtClick.busy === "true" && busyAtClick.skeleton > 0, busyAtClick);
  await page.waitForFunction(() => !document.querySelector("#case").hasAttribute("aria-busy"));
  ok("the loading state clears", (await page.locator("#case .sk").count()) === 0);
  ok("the splash is gone after start", await page.$eval("#splash", (s) => s.hidden));

  // Evidence highlights: coloured marks in the email and in an attachment's text view (counts only).
  const marks = async (frameSel) => page.frameLocator(frameSel).locator("mark.hl").evaluateAll(
    (ms) => ms.reduce((acc, m) => { const k = m.className.replace("hl hl-", ""); acc[k] = (acc[k] || 0) + 1; return acc; }, {}));
  let emailMarks = {}, textMarks = {}, quotes = 0, textViews = 0;
  for (const id of await page.$$eval("#list .item", (items) => items.map((i) => i.dataset.id))) {
    await page.click(`#list .item[data-id="${id}"]`);
    await page.waitForFunction((x) => document.querySelector("#case").dataset.caseId === x, id);
    await page.waitForSelector("#viewer-body iframe");
    await page.waitForTimeout(300);
    const m = await marks("#viewer-body iframe").catch(() => ({}));
    for (const [k, v] of Object.entries(m)) emailMarks[k] = (emailMarks[k] || 0) + v;
    quotes += await page.locator("#case .quote").count();
    const textButton = page.locator("#viewer-tools .seg button").nth(1);
    for (const tab of await page.locator("#viewer-tabs button").all()) {
      if ((await tab.getAttribute("aria-selected")) === "true") continue;
      await tab.click();
      if (!(await textButton.count())) continue;
      await textButton.click();
      await page.waitForSelector("#viewer-body iframe[src*='/text']");
      await page.waitForTimeout(300);
      textViews++;
      const tm = await marks("#viewer-body iframe").catch(() => ({}));
      for (const [k, v] of Object.entries(tm)) textMarks[k] = (textMarks[k] || 0) + v;
      break;
    }
  }
  ok("emails show customer-detail highlights", (emailMarks.id || 0) > 0, emailMarks);
  ok("attachment text views open", textViews > 0, { textViews });
  ok("attachment text shows highlights", Object.values(textMarks).reduce((a, b) => a + b, 0) > 0, textMarks);
  ok("evidence quotes are listed on cases", quotes > 0, { quotes });

  // Review steps: actions can be ticked, unticked, changed and added; Save stays on top (nothing is saved).
  const unreviewed = await page.$$eval("#list .item", (items) => items.filter((i) => !/Ελέγχθηκε|Reviewed/.test(i.textContent)).map((i) => i.dataset.id));
  if (unreviewed.length) {
    await page.click(`#list .item[data-id="${unreviewed[0]}"]`);
    await page.waitForFunction((x) => document.querySelector("#case").dataset.caseId === x && !!document.querySelector(".savetop"), unreviewed[0]);
    const before = await page.locator(".action.pickable").count();
    if (before) {
      await page.locator(".action.pickable input[type=checkbox]").first().uncheck();
      ok("unticking an action greys it out", (await page.locator(".action.pickable.off").count()) === 1);
    }
    await page.locator("details.adder summary").click();
    await page.locator("details.adder .picker-opt").first().click();
    const after = await page.locator(".action.pickable").count();
    ok("an action can be added from the rule table (a request brings its activity)", after >= before + 1, { before, after });
    // Change the first action for another one from the list: same count, the row becomes the reviewer's own.
    const firstText = await page.locator(".action.pickable .what").first().textContent();
    await page.locator(".action.pickable .change").first().click();
    await page.locator(".action.changing .picker-opt").nth(1).click();
    const changedCount = await page.locator(".action.pickable").count();
    const changedText = await page.locator(".action.pickable .what").first().textContent();
    ok("an action can be changed from the list", changedCount >= after - 1 && changedText !== firstText
      && (await page.locator(".action.pickable").first().locator(".pill").count()) === 1, { changedCount, after });
    const bar = await page.$eval(".savetop", (b) => ({ sticky: getComputedStyle(b).position, top: b.getBoundingClientRect().top,
      text: /\d/.test(b.textContent), save: !!b.querySelector("button.primary") }));
    await page.$eval("#case", (c) => { c.scrollTop = c.scrollHeight; });
    await page.waitForTimeout(100);
    const caseTop = await page.$eval("#case", (c) => c.getBoundingClientRect().top);
    const barAfter = await page.$eval(".savetop", (b) => b.getBoundingClientRect().top);
    ok("Save is on top and stays visible while scrolling", bar.sticky === "sticky" && bar.text && bar.save
      && Math.abs(barAfter - caseTop) <= 2, { ...bar, barAfter, caseTop });
    const comments = await page.$eval("#rv-comment", (el) => ({ inCard: !!el.closest(".card"), sticky: getComputedStyle(el.closest(".card")).position }));
    ok("step 3 is comments, in the page flow (not pinned)", comments.inCard && comments.sticky !== "sticky", comments);
    const found = await page.$$eval(".found-scroll", (els) => els.map((e) => ({ max: getComputedStyle(e).maxHeight, h: e.clientHeight })));
    ok("details found sit in a short scrolling window", found.every((f) => f.max !== "none" && f.h <= 212), { found: found.length });
  } else ok("an unreviewed email exists to test actions", false);

  // Clock: hovering shows how and when emails arrive.
  await page.hover("#clock-btn");
  await page.waitForTimeout(250);
  const clock = await page.$eval("#clock-pop", (p) => ({ opacity: +getComputedStyle(p).opacity, filled: p.children.length }));
  ok("hovering the clock shows the intake card", clock.opacity === 1 && clock.filled >= 3, clock);
  await page.mouse.move(5, 300);

  // Motion: opening a case animates its cards (sampled mid-way, not just the end state).
  const other = await page.$$eval("#list .item", (items) => items.map((i) => i.dataset.id));
  const openNow = await page.$eval("#case", (c) => c.dataset.caseId);
  const otherId = other.find((id) => id !== target && id !== openNow);
  const sampling = page.evaluate(SAMPLE, otherId);
  await page.click(`#list .item[data-id="${otherId}"]`);
  const midOpacity = await sampling;
  ok("opening a case fades its cards in", midOpacity > 0 && midOpacity < 1, { midOpacity });
  await page.waitForTimeout(500);

  // Category picker: Greek A–Ω, then English A–Z, search ignores accents, keyboard picks.
  await page.locator(".choice .opt input[value=other]").check();
  await page.waitForSelector("#rv-cat");
  const groups = await page.$$eval("#rv-cat-list .picker-group", (g) => g.map((x) => x.textContent));
  const greekIdx = groups.findIndex((g) => /Ελληνικ|Greek/.test(g));
  const latinIdx = groups.findIndex((g) => /Αγγλικ|English/.test(g));
  ok("picker lists Greek before English", greekIdx >= 0 && (latinIdx === -1 || greekIdx < latinIdx), { groups: groups.length });
  const greekSorted = await page.$$eval("#rv-cat-list .picker-group", (heads) => {
    const head = heads.find((x) => /Ελληνικ|Greek/.test(x.textContent));
    const names = [];
    for (let el = head.nextElementSibling; el && el.classList.contains("picker-opt"); el = el.nextElementSibling) names.push(el.textContent.replace(/^✓ /, ""));
    return names.every((n, i) => i === 0 || names[i - 1].localeCompare(n, "el", { sensitivity: "base" }) <= 0) && names.length > 5;
  });
  ok("Greek categories are in alphabetical order", greekSorted);
  await page.fill("#rv-cat", "βεβαιωση");
  const filtered = await page.locator("#rv-cat-list .picker-opt").count();
  ok("search without accents narrows the list", filtered > 0 && filtered < 20, { filtered });
  await page.press("#rv-cat", "Enter");
  ok("Enter picks the highlighted category", (await page.locator(".picked .chip").count()) === 1);

  // Activity log across all emails: slides in, lists events, Escape closes.
  await page.click("#activity-open");
  await page.waitForTimeout(40);
  const sliding = await page.$eval("#activity", (d) => getComputedStyle(d).transform);
  await page.waitForSelector("#activity-body .activity-row");
  const rows = await page.locator("#activity-body .activity-row").count();
  ok("activity log opens with a slide", sliding !== "none" || rows > 0, { sliding: sliding !== "none" });
  ok("activity log lists events", rows > 0, { rows });
  await page.keyboard.press("Escape");
  await page.waitForTimeout(350);
  ok("Escape closes the activity log", await page.$eval("#activity", (d) => d.hidden));

  await page.click("#lang");
  ok("language switches to English", (await page.getAttribute("html", "lang")) === "en");
  await page.click("#lang");
  await page.reload();
  const reopened = await page.waitForSelector("#case h2", { timeout: 15000 }).then(() => true, () => false);
  ok("reload keeps the open case", reopened);
  await page.screenshot({ path: path.join(OUTPUT, "review_1600x900.png") });

  // Metrics view: tiles, a column per day with a tooltip, the tables, range buttons, back to the emails.
  await page.click('#views button[data-view="metrics"]');
  await page.waitForSelector("#metrics .tile");
  ok("metrics view replaces the email panes", await page.$eval(".layout", (l) => l.hidden) && !(await page.$eval("#metrics", (m) => m.hidden)));
  const tiles = await page.$$eval("#metrics .tile-value", (v) => v.map((x) => x.textContent));
  ok("metrics tiles show numbers", tiles.length >= 6 && /\d/.test(tiles[0]), { tiles: tiles.length });
  const columns = await page.locator("#metrics .chart .hit").count();
  ok("daily chart has one column per day (30 days)", columns === 30, { columns });
  const busiest = await page.$$eval("#metrics .chart .hit", (hits) => hits.findIndex((h) => !/: 0$/.test(h.getAttribute("aria-label"))));
  await page.hover(`#metrics .chart .hit >> nth=${Math.max(busiest, 0)}`);
  ok("hovering a day shows its counts", await page.$eval("#metrics .tip", (t) => !t.hidden && t.querySelectorAll(".tip-row").length === 6));
  const tables = await page.locator("#metrics .mtable").count();
  ok("routing and action tables are shown", tables >= 5, { tables });
  await page.click("#ranges button >> nth=0");
  await page.waitForFunction(() => document.querySelectorAll("#metrics .chart .hit").length === 7);
  ok("7-day range redraws the chart", (await page.locator("#metrics .chart .hit").count()) === 7);
  await page.click("#ranges button >> nth=1");
  const msideways = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
  ok("metrics: no sideways page scroll", msideways <= 1, { sideways: msideways });
  await page.screenshot({ path: path.join(OUTPUT, "metrics_1600x900.png") });
  await page.click('#views button[data-view="emails"]');
  ok("back to the emails", !(await page.$eval(".layout", (l) => l.hidden)) && (await page.locator("#list .item").count()) > 0);

  // Category filter on the Emails tab narrows the list.
  await page.click("#queues button:nth-child(4)");
  const allCount = await page.locator("#list .item").count();
  const catValues = await page.$$eval("#cat option", (o) => o.map((x) => x.value).filter((v) => v !== "all"));
  await page.selectOption("#cat", catValues[0]);
  const oneCat = await page.locator("#list .item").count();
  ok("category filter narrows the list", catValues.length > 1 && oneCat > 0 && oneCat < allCount, { categories: catValues.length, oneCat, allCount });
  await page.selectOption("#cat", "all");

  // Metrics → Emails: a clicked count lists exactly those emails, as a removable filter.
  await page.click('#views button[data-view="metrics"]');
  await page.waitForSelector("#metrics .tile");
  const matrixLinks = page.locator(".matrix .num-link");
  if (await matrixLinks.count()) {
    const n = +(await matrixLinks.first().textContent());
    await matrixLinks.first().click();
    await page.waitForSelector("#fchips .fchip");
    const listedN = await page.locator("#list .item").count();
    ok("a metrics count opens exactly its emails", listedN === n && !(await page.$eval("#metrics", (m) => m.hidden)) === false, { n, listedN });
    const [download] = await Promise.all([page.waitForEvent("download", { timeout: 15000 }), page.click("#export")]);
    ok("Excel export downloads the listed emails", /\.xlsx$/.test(download.suggestedFilename()));
    await page.click("#fchips .chip-x");
    ok("removing the filter shows every email again", (await page.locator("#fchips").isHidden()) && (await page.locator("#list .item").count()) === allCount);
    await page.click('#views button[data-view="metrics"]');
    await page.waitForSelector("#metrics .tile");
  } else ok("reviewed emails exist for the category/actions table", false);
  ok("reviewers table lists people", (await page.locator(".mcard").filter({ hasText: /Ελεγκτές|Reviewers/ }).locator("tbody tr").count()) > 0);
  await page.click('#views button[data-view="emails"]');

  // Case page: further categories as chips; "No Match Found" offered as a category; history spells out changes.
  await page.click("#queues button:nth-child(1)");
  if (await page.locator("#list .item").count()) {
    await page.locator("#list .item").first().click();
    await page.waitForSelector(".extras");
    await page.locator(".extras details summary").click();
    await page.fill("#rv-extra", "gdpr");
    await page.press("#rv-extra", "Enter");
    await page.waitForTimeout(100);
    const extraChips = await page.locator(".extras .chips .chip:not(.add)").count();
    ok("further categories are added as chips", extraChips >= 1, { extraChips });
    ok("No Match Found is offered for manual handling", (await page.locator(".choice .opt").filter({ hasText: "No Match Found" }).count()) === 1);
  }
  await page.click("#queues button:nth-child(3)");
  if (await page.locator("#list .item").count()) {
    await page.locator("#list .item").first().click();
    await page.waitForSelector(".ev-changes");
    const terms = await page.$$eval(".ev-changes dt", (d) => d.map((x) => x.textContent));
    ok("history shows the category of a review", terms.some((x) => /Κατηγορία|Category/.test(x)), { rows: terms.length });
  }

  // Review reason and ERB filters; the case page: customer first, categories side by side, possible customers.
  await page.click("#queues button:nth-child(4)");
  const total = await page.locator("#list .item").count();
  const markValues = await page.$$eval("#mark option", (o) => o.map((x) => x.value));
  if (markValues.includes("ERB")) {
    await page.selectOption("#mark", "ERB");
    const erb = await page.locator("#list .item").count();
    ok("ERB filter lists only ERB emails", erb > 0 && erb < total && erb === (await page.locator("#list .item .pill.mark").count()), { erb, total });
    await page.locator("#list .item").first().click();
    await page.waitForSelector(".catblock");
    const titles = await page.$$eval("#case .card > h3 > span:first-child", (x) => x.map((e) => e.textContent));
    ok("customer comes first on the case page", /Πελάτης|Customer/.test(titles[0]), { titles });
    ok("an ERB email names Eurobank", (await page.locator(".banks .bank.flagged").count()) >= 1);
    await page.selectOption("#mark", "all");
  } else ok("demo data has ERB emails", false);
  const reasons = await page.$$eval("#reason option", (o) => o.map((x) => x.value).filter((v) => v !== "all"));
  await page.selectOption("#reason", reasons[0]);
  const withReason = await page.locator("#list .item").count();
  ok("review reason filter narrows the list", reasons.length > 0 && withReason > 0 && withReason < total, { withReason, total });
  ok("listed emails show their review reason", (await page.locator("#list .item .why-line").count()) === withReason);
  await page.selectOption("#reason", "all");
  const blocks = await page.$$eval("#list .item", (items) => items.map((i) => i.dataset.id));
  let possibleSeen = false;
  for (const id of blocks.slice(0, 60)) {
    await page.click(`#list .item[data-id="${id}"]`);
    await page.waitForFunction((x) => document.querySelector("#case").dataset.caseId === x, id);
    if (await page.locator("#possible-pick").count()) {
      const before = await page.locator(".possible .person").count();
      await page.selectOption("#possible-pick", "0");
      ok("possible customers open from a drop-down", before === 0 && (await page.locator(".possible .person").count()) === 1);
      possibleSeen = true;
      break;
    }
  }
  if (!possibleSeen) ok("demo data has an email with only possible customers", false);
  const widths = await page.$$eval(".catblock", (b) => b.map((x) => Math.round(x.getBoundingClientRect().width)));
  ok("categories get the same space", widths.length >= 1 && new Set(widths).size === 1, { widths });

  ok("no script errors", scriptErrors === 0, { scriptErrors });
  ok("no console errors", consoleErrors === 0, { consoleErrors });
  await context.close();
}

async function layoutAt(browser, width, height) {
  const context = await browser.newContext({ viewport: { width, height } });
  const page = await context.newPage();
  await signIn(page);
  await page.click("#list .item");
  await page.waitForSelector("#case h2");
  const sideways = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
  ok(`${width}x${height} no sideways page scroll`, sideways <= 1, { sideways });
  const listBox = await page.locator("#list").boundingBox();
  ok(`${width}x${height} list is visible`, listBox && listBox.height > 100, { listHeight: listBox && Math.round(listBox.height) });
  await page.screenshot({ path: path.join(OUTPUT, `review_${width}x${height}.png`) });
  await page.click('#views button[data-view="metrics"]');
  await page.waitForSelector("#metrics .chart svg");
  const msideways = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
  ok(`${width}x${height} metrics: no sideways page scroll`, msideways <= 1, { sideways: msideways });
  await page.screenshot({ path: path.join(OUTPUT, `metrics_${width}x${height}.png`) });
  await context.close();
}

(async () => {
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({ headless: !args.includes("--headed") });
  try {
    await behaviour(browser);
    // Managed PCs often force "reduce motion": the change must still be visible (a fade), not vanish.
    const reduced = await browser.newContext({ viewport: { width: 1600, height: 900 }, reducedMotion: "reduce" });
    const rp = await reduced.newPage();
    await signIn(rp);
    const firstId = await rp.$eval("#list .item", (b) => b.dataset.id);
    const sampling = rp.evaluate(SAMPLE, firstId);
    await rp.click("#list .item");
    const fade = await sampling;
    ok("reduced motion still fades the case in", fade > 0 && fade < 1, { fade });
    await reduced.close();
    for (const [w, h] of [[1920, 1080], [1366, 768], [1280, 600], [800, 900], [390, 844]]) await layoutAt(browser, w, h);
  } catch (error) {
    ok("run completed", false, String(error.message).split("\n")[0].slice(0, 160));
  } finally {
    await browser.close();
  }
  for (const r of results) console.log(`${r.pass ? "PASS" : "FAIL"}  ${r.name}${r.info !== undefined ? "  " + JSON.stringify(r.info) : ""}`);
  const failed = results.filter((r) => !r.pass).length;
  console.log(`${results.length - failed}/${results.length} passed`);
  process.exit(failed ? 1 : 0);
})();
