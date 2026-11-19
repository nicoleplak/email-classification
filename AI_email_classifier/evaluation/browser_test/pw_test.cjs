// Review-app checks with Playwright's bundled Chromium. Run through run.py.
//   node pw_test.cjs <synthetic url> <screenshot dir> [real url]
// Screenshots of invented emails go to disk for a person to look at. Output is numbers
// and short labels only, because it reaches the terminal and any AI assistant.
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

const [SYNTHETIC, OUTPUT, REAL] = process.argv.slice(2);
fs.mkdirSync(OUTPUT, { recursive: true });
const results = [];
const notes = {};
const ok = (name, condition, info) => results.push({ name, pass: !!condition, info });

const inside = (r, w, h) => r && r.x >= -1 && r.y >= -1 && r.x + r.width <= w + 1 && r.y + r.height <= h + 1 && r.width > 0 && r.height > 0;

async function open(context, url, keepHelp) {
  const page = await context.newPage();
  page.scriptErrors = 0;
  page.on("pageerror", () => page.scriptErrors++);
  await page.goto(url);
  await page.waitForTimeout(100);
  if (!keepHelp && (await page.locator("#helpDlg[open]").count())) await page.click("#helpClose");
  return page;
}

// Are all boxes the same size, with nothing cut off?
const tileReport = (page, selector) => page.$$eval(selector, (tiles) => {
  const box = tiles.map((t) => t.getBoundingClientRect());
  return {
    count: tiles.length,
    widths: new Set(box.map((b) => Math.round(b.width))).size,
    heights: new Set(box.map((b) => Math.round(b.height))).size,
    clipped: tiles.filter((t) => t.scrollWidth > t.clientWidth + 1 || t.scrollHeight > t.clientHeight + 1).length,
    tall: Math.round(Math.max(...box.map((b) => b.height))),
  };
});

async function layoutAt(browser, w, h) {
  const tag = `${w}x${h}`;
  const context = await browser.newContext({ viewport: { width: w, height: h } });
  const page = await open(context, SYNTHETIC, true);
  ok(`${tag} instructions open first`, await page.locator("#helpDlg[open]").count());
  await page.click("#helpClose");

  const m = await page.evaluate(() => {
    const de = document.documentElement;
    const inner = [...document.querySelectorAll(".assess,.reading,.panel,.sheet,.body,.why")]
      .filter((n) => ["auto", "scroll", "hidden"].includes(getComputedStyle(n).overflowY)).length;
    return { sw: de.scrollWidth, sh: de.scrollHeight, inner };
  });
  ok(`${tag} no sideways page scroll`, m.sw <= w + 1, m.sw);
  ok(`${tag} the page itself scrolls, long content is not boxed in`, m.sh > h && m.inner === 0, m);

  const a = await page.locator(".reading").boundingBox(), b = await page.locator(".assess").boundingBox();
  if (w > 1100) ok(`${tag} email beside assessment`, a.x + a.width <= b.x + 1 && Math.abs(a.y - b.y) <= 1 && a.width >= 300, [Math.round(a.width), Math.round(b.width)]);
  else ok(`${tag} email above assessment`, b.y >= a.y + a.height - 1, null);

  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  await page.waitForTimeout(30);
  const bar = await page.locator("#bar").boundingBox(), dock = await page.locator("#dock").boundingBox();
  ok(`${tag} top and bottom bars stay in view while scrolling`, Math.abs(bar.y) <= 1 && Math.abs(dock.y + dock.height - h) <= 1, [Math.round(bar.y), Math.round(dock.y + dock.height)]);
  ok(`${tag} next button in view`, inside(await page.locator("#nextBig").boundingBox(), w, h));
  if (w > 760) {
    const list = await page.locator("#list").boundingBox();
    ok(`${tag} email list stays beside the page`, Math.abs(list.y - bar.height) <= 1 && Math.abs(list.y + list.height - dock.y) <= 1, [Math.round(list.y), Math.round(list.height)]);
  }
  notes[`${tag} bars`] = { top: Math.round(bar.height), bottom: Math.round(dock.height), page: m.sh };
  await page.evaluate(() => window.scrollTo(0, 0));
  if (w === 1366 && h === 768) {
    await page.screenshot({ path: path.join(OUTPUT, `page_${tag}.png`) });
    await page.screenshot({ path: path.join(OUTPUT, `page_${tag}_full.png`), fullPage: true });
  }

  // The three panels
  await page.click("#other");
  let r = await tileReport(page, "#catTiles .tile");
  const n = await page.evaluate(() => JSON.parse(document.getElementById("data").textContent).categories.length);
  ok(`${tag} categories: every box the same size`, r.count === n && r.widths === 1 && r.heights === 1 && r.clipped === 0, r);
  const need = await page.$eval("#catDlg", (d) => d.scrollHeight - d.clientHeight);
  if (h >= 700 && w >= 1366) ok(`${tag} categories: all on the page without scrolling`, need <= 1, need);
  notes[`${tag} category panel`] = { boxHeight: r.tall, scrollNeeded: need };
  if (need > 1) {
    const dlg = await page.locator("#catDlg").boundingBox();
    const pageBefore = await page.evaluate(() => window.scrollY);
    await page.mouse.move(dlg.x + dlg.width / 2, dlg.y + dlg.height / 2);
    await page.mouse.wheel(0, 300);
    await page.waitForTimeout(80);
    const moved = await page.evaluate(() => ({ panel: document.getElementById("catDlg").scrollTop, page: window.scrollY }));
    ok(`${tag} a tall panel still scrolls, the page behind does not`, moved.panel > 0 && moved.page === pageBefore, { ...moved, pageBefore });
  }
  if (w === 1366 && h === 768) await page.screenshot({ path: path.join(OUTPUT, `panel_categories_${tag}.png`) });
  await page.click("#catDone");

  await page.click("#actOther");
  r = await tileReport(page, "#actTiles .tile");
  ok(`${tag} actions: every box the same size`, r.count === 9 && r.widths === 1 && r.heights === 1 && r.clipped === 0, r);
  if (w === 1366 && h === 768) await page.screenshot({ path: path.join(OUTPUT, `panel_actions_${tag}.png`) });
  await page.click("#actDone");

  await page.click("#filters");
  r = await tileReport(page, "#filterBody .tile:not(#filterCat)");
  ok(`${tag} filters: every box the same size`, r.widths === 1 && r.heights === 1 && r.clipped === 0, r);
  if (w === 1366 && h === 768) await page.screenshot({ path: path.join(OUTPUT, `panel_filters_${tag}.png`) });
  await page.click("#filterDone");
  ok(`${tag} no script errors`, page.scriptErrors === 0, page.scriptErrors);
  await context.close();
}

async function behaviour(browser) {
  const context = await browser.newContext({ viewport: { width: 1366, height: 768 }, acceptDownloads: true });
  const page = await open(context, SYNTHETIC);
  const slotNames = () => page.$$eval(".slot:not(.empty) .slot-name", (n) => n.map((x) => x.textContent));
  const stateText = () => page.textContent("#state");
  const box = (sel) => page.locator(sel).boundingBox();

  // Chain and its divider
  ok("chain shows three separate messages", (await page.locator("#reading .sheet:not(.attach)").count()) === 3);
  ok("one divider between each pair of messages", (await page.locator("#reading .seam").count()) === 2);
  const seam = await page.locator("#reading .seam").first().textContent();
  ok("divider gives the order", /Προηγούμενο μήνυμα 1 από 2/.test(seam));
  const oldHead = await page.locator("#reading .sheet.old .fold-head").first().textContent();
  ok("older message heading names sender, date and subject", oldHead.includes("Ομάδα") && oldHead.includes("Τρίτη") && oldHead.includes("RE: Βεβαίωση"));

  // Hiding emails and attachments
  const heads = page.locator("#reading .fold-head"), folds = page.locator("#reading .fold");
  ok("every email and attachment has a heading to hide it", (await heads.count()) === 5 && (await folds.count()) === 5, await heads.count());
  const tall = await page.evaluate(() => document.documentElement.scrollHeight);
  const full = (await folds.nth(0).boundingBox()).height;
  await heads.nth(0).click();
  const steps = new Set(), end = Date.now() + 450;
  while (Date.now() < end) { steps.add(Math.round((await folds.nth(0).boundingBox()).height)); await page.waitForTimeout(12); }
  ok("email hides with an animation", [...steps].some((v) => v > 5 && v < full - 5) && steps.has(0), { steps: steps.size, full: Math.round(full) });
  ok("the page gets shorter", (await page.evaluate(() => document.documentElement.scrollHeight)) < tall - 500);
  ok("heading says it is hidden", (await heads.nth(0).getAttribute("aria-expanded")) === "false" && (await heads.nth(0).getAttribute("title")) === "Εμφάνιση");
  ok("hidden text is really hidden", !(await page.locator("#reading .body").first().isVisible()));
  await page.locator(".cand button").first().click();
  ok("stays hidden while choosing a category", (await heads.nth(0).getAttribute("aria-expanded")) === "false");
  await page.click('[data-key="rm0"]');
  await page.click("#nextBig");
  ok("the next email starts open", (await page.locator("#reading .fold-head").first().getAttribute("aria-expanded")) === "true");
  await page.click("#prev");
  ok("still hidden when you come back", (await page.locator("#reading .fold-head").first().getAttribute("aria-expanded")) === "false");
  await page.locator("#reading .fold-head").first().click();
  const reopen = new Set(), until0 = Date.now() + 450;
  while (Date.now() < until0) { reopen.add(Math.round((await page.locator("#reading .fold").first().boundingBox()).height)); await page.waitForTimeout(12); }
  ok("email opens with an animation", [...reopen].some((v) => v > 5 && v < full - 5) && Math.abs(Math.max(...reopen) - full) <= 1, { steps: reopen.size });
  const attachHeads = page.locator("#reading .attach .fold-head");
  await attachHeads.nth(1).click();
  await page.waitForTimeout(320);
  ok("one attachment hides on its own", !(await page.locator("#reading .attach .why").first().isVisible()) && (await attachHeads.nth(0).isVisible()));
  await attachHeads.nth(1).click();
  await attachHeads.nth(0).click();
  await page.waitForTimeout(320);
  ok("all attachments hide together", !(await attachHeads.nth(1).isVisible()));
  await page.keyboard.press("Enter");
  await page.waitForTimeout(320);
  ok("keyboard opens them again", await attachHeads.nth(1).isVisible());

  // Look
  const look = await page.evaluate(() => {
    const rgb = (c) => c.match(/[\d.]+/g).map(Number), css = (s, p) => getComputedStyle(document.querySelector(s))[p];
    return { button: rgb(css("#export", "backgroundColor")), mark: rgb(css("#reading mark", "backgroundColor")), body: css("#reading .body", "fontFamily"), panel: css("#catPanel", "fontFamily"), page: rgb(css("body", "backgroundColor")) };
  });
  const blue = ([r, g, b]) => b > r && b > g;
  ok("buttons, highlights and page are blue, nothing yellow", blue(look.button) && blue(look.mark) && blue(look.page), look);
  ok("one standard font everywhere", /^Arial/.test(look.body) && /^Arial/.test(look.panel), [look.body, look.panel]);
  const yellow = await page.evaluate(() => [...document.querySelectorAll("body *")].filter((n) => { const [r, g, b] = getComputedStyle(n).backgroundColor.match(/[\d.]+/g).map(Number); return r > 200 && g > 180 && b < 170; }).length);
  ok("no yellow backgrounds on the page", yellow === 0, yellow);
  const seamStyle = await page.$eval("#reading .seam", (n) => getComputedStyle(n, "::before").backgroundImage);
  ok("divider is drawn, not a plain rule", seamStyle.includes("radial-gradient"), seamStyle.slice(0, 20));
  ok("older message set apart from the newest", await page.$$eval("#reading .sheet", (s) => getComputedStyle(s[0]).backgroundColor !== getComputedStyle(s[1]).backgroundColor && parseFloat(getComputedStyle(s[2]).marginLeft) > parseFloat(getComputedStyle(s[1]).marginLeft)));
  ok("highlighting kept", (await page.locator("#reading mark").count()) > 0);

  // Probabilities
  const pcts = await page.$$eval(".cand-pct", (n) => n.map((x) => parseInt(x.textContent)));
  ok("three independent probabilities, may pass 100 together", pcts.length === 3 && pcts.reduce((x, y) => x + y) > 100, pcts);
  const barWidth = await page.$eval(".cand .meter i", (i) => i.style.width);
  ok("the bar shows the probability itself", barWidth === `${pcts[0]}%`, barWidth);
  ok("reason shown under each category, in full", (await page.locator(".cand .why").count()) === 3);

  // Ranking
  ok("three empty places at first", (await page.locator(".slot.empty").count()) === 3);
  const slotHeights = () => page.$$eval(".slot", (n) => n.map((x) => Math.round(x.getBoundingClientRect().height)));
  const emptySlots = await slotHeights();
  ok("places are short", emptySlots.every((v) => v <= 40), emptySlots);
  await page.locator(".cand button").first().click();
  ok("first pick takes first place", (await slotNames()).length === 1, await slotNames());
  ok("a place keeps its height when filled", JSON.stringify(await slotHeights()) === JSON.stringify(emptySlots), await slotHeights());
  ok("focus stays on the button after choosing", await page.evaluate(() => document.activeElement && document.activeElement.dataset.key === "cand0"));
  ok("button says which place it holds", /1η επιλογή/.test(await page.locator(".cand button").first().textContent()));
  await page.locator(".cand button").nth(2).click();
  await page.locator(".cand button").nth(1).click();
  let names = await slotNames();
  ok("order follows the clicks", names.length === 3 && names[0] === "Βεβαιώσεις οφειλής" && names[1] === "GDPR" && names[2] === "Αντίγραφα συμβάσεων", names);
  await page.click('[data-key="up2"]');
  names = await slotNames();
  ok("arrow moves a choice up", names[1] === "Αντίγραφα συμβάσεων" && names[2] === "GDPR", names);
  await page.click('[data-key="rm0"]');
  names = await slotNames();
  ok("removing the first moves the rest up", names.length === 2 && names[0] === "Αντίγραφα συμβάσεων", names);
  ok("bottom bar confirms the save", /2 κατηγορίες/.test(await stateText()));

  // Categories panel
  await page.click("#other");
  const sorted = await page.$$eval("#catTiles .tile b", (n) => n.map((x) => x.textContent));
  ok("categories in Greek alphabetical order", JSON.stringify(sorted) === JSON.stringify([...sorted].sort(new Intl.Collator("el", { sensitivity: "base" }).compare)));
  ok("chosen boxes carry their place", (await page.$$eval("#catTiles .badge", (n) => n.map((x) => x.textContent))).sort().join() === "1η,2η");
  ok("each box shows its own probability", (await page.locator("#catTiles .tile small").count()) === sorted.length);
  await page.locator("#catTiles .tile", { hasText: "Παράπονα" }).first().click();
  ok("third choice from the panel", (await page.locator("#catTiles .badge").count()) === 3);
  ok("panel stays open for more choices", await page.locator("#catDlg[open]").count());
  ok("a fourth is not possible", (await page.locator("#catTiles .tile:disabled").count()) === sorted.length - 3);
  await page.keyboard.press("Escape");
  ok("Escape closes the panel", !(await page.locator("#catDlg[open]").count()));
  names = await slotNames();
  ok("panel choice lands in third place", names.length === 3 && names[2] === "Παράπονα", names);
  ok("reaching three disables other suggestions", await page.locator(".cand button").first().isDisabled());
  await page.click('[data-key="rm2"]'); await page.click('[data-key="rm1"]'); await page.click('[data-key="rm0"]');
  ok("clearing every pick empties the places", (await page.locator(".slot.empty").count()) === 3);
  await page.click("#accept");
  ok("accepting takes the model's first suggestion", (await slotNames()).join() === "Βεβαιώσεις οφειλής" && /Αποδεκτή/.test(await page.textContent("#accept")), await slotNames());
  const tags = await page.$$eval(".cand-foot", (n) => n.map((x) => x.firstChild.textContent));
  ok("second and third are labelled by likelihood", tags[0] === "Πρόταση μοντέλου" && tags[1] === "Επίσης πιθανή" && tags[2] === "Χαμηλότερη πιθανότητα", tags);

  // Actions
  const act = await page.textContent("#actPanel");
  ok("plain action name with its meaning", /Καταχώρηση αιτήματος στο Qualco/.test(act) && /Το προσωπικό ανοίγει/.test(act));
  ok("both codes explained in words", /ανοιχτή/.test(act) && /κλειστή/.test(act));
  ok("action says why", (await page.locator("#actPanel .reasons li").count()) >= 2 && /Γιατί αυτή η ενέργεια/.test(act));
  ok("customer status in plain words", /Ταυτοποιήθηκε με ΑΦΜ/.test(act) && /Δεν έχει πρόσβαση/.test(act));
  ok("recipients of a forward listed", /dept@example\.com/.test(act));
  ok("spec wording behind the action is one click away", /Κείμενο της προδιαγραφής/.test(act) && (await page.locator("#actPanel details:not([open])").count()) >= 1);
  ok("no staff tags, no wizard, no engineering terms", !/Προσωπικό:|wizard|βεβαιότητα 1|Ίδια ενέργεια/i.test(await page.textContent("body")));
  await page.click("#actOk");
  ok("confirming the action is saved", /σωστή ενέργεια/.test(await stateText()) && /✓/.test(await page.textContent("#actOk")));
  await page.click("#actOther");
  await page.locator("#actTiles .tile", { hasText: "Παραπομπή στο Portal" }).click();
  await page.locator("#actTiles .tile", { hasText: "Προώθηση" }).click();
  await page.click("#actDone");
  ok("correcting the action is saved and shown", /διορθωμένη/.test(await stateText()) && /Διόρθωση: /.test(await page.textContent("#actPanel")));

  // Comment and navigation
  await page.fill("#comment", "σχόλιο δοκιμής");
  await page.locator("#comment").blur();
  await page.waitForTimeout(20);
  await page.evaluate(() => window.scrollTo(0, 500));
  await page.click("#nextBig");
  ok("next goes on and returns to the top", (await page.textContent("#pos")) === "2 / 40" && (await page.evaluate(() => window.scrollY)) === 0);
  ok("new email starts clean", (await page.inputValue("#comment")) === "" && (await page.locator(".slot.empty").count()) === 3);
  await page.locator("#comment").blur();
  await page.keyboard.press("k");
  ok("keyboard moves back, comment kept", (await page.inputValue("#comment")) === "σχόλιο δοκιμής" && (await page.textContent("#pos")) === "1 / 40");
  await page.evaluate(() => window.scrollTo(0, 200));
  await page.evaluate(() => document.getElementById("actOk").click());
  ok("choosing keeps your place on the page", (await page.evaluate(() => window.scrollY)) === 200);

  // Filters
  await page.click("#filters");
  await page.locator("#filterBody .tile", { hasText: "Ελεγμένα" }).click();
  ok("filter narrows the list straight away", (await page.textContent("#count")).startsWith("1 από"), await page.textContent("#count"));
  await page.locator("#filterBody .tile", { hasText: "Χωρίς έλεγχο" }).click();
  ok("second choice in a group replaces the first", (await page.textContent("#count")).startsWith("39 από"), await page.textContent("#count"));
  await page.locator("#filterBody .tile", { hasText: "Με δεύτερη πιθανή" }).click();
  const multi = await page.textContent("#count");
  ok("filters combine", parseInt(multi) < 39 && parseInt(multi) > 0, multi);
  await page.click("#filterDone");
  ok("button counts active filters", (await page.textContent("#filters")) === "Φίλτρα (2)");
  await page.click("#clearFilters");
  ok("clearing brings everything back", (await page.textContent("#count")).startsWith("40 από"));
  await page.click("#filters");
  await page.click("#filterCat");
  await page.locator("#catTiles .tile", { hasText: "GDPR" }).click();
  ok("category filter opens the same panel and handles no results", (await page.textContent("#count")).startsWith("0 από") && !(await page.locator("#catDlg[open]").count()), await page.textContent("#count"));
  await page.click("#filterReset");
  await page.click("#filterDone");

  // Email without actions
  await page.locator("#items .item").nth(5).click();
  ok("email with no action proposal says so", /Δεν υπάρχει πρόταση/.test(await page.textContent("#actPanel")));
  await page.locator("#items .item").first().click();

  // Sidebar
  const w0 = Math.round((await box("#list")).width);
  await page.click("#tList");
  const seen = new Set(), stop = Date.now() + 450;
  while (Date.now() < stop) { seen.add(Math.round((await box("#list")).width)); await page.waitForTimeout(12); }
  ok("sidebar animates closed", [...seen].some((v) => v > 5 && v < w0 - 5) && seen.has(0), { steps: seen.size });
  ok("email fills the page without the list", (await box("#detail")).width > 1300, Math.round((await box("#detail")).width));
  await page.click("#tList");
  await page.waitForTimeout(350);
  const sp = await box("#split");
  await page.mouse.move(sp.x + 2, 300); await page.mouse.down(); await page.mouse.move(420, 300, { steps: 4 }); await page.mouse.up();
  ok("dragging resizes the list", Math.abs((await box("#list")).width - 420) <= 2, Math.round((await box("#list")).width));

  // Email / assessment bar
  const dragBar = async (x) => { const b = await box(".vbar"); await page.mouse.move(b.x + 8, 300); await page.mouse.down(); await page.mouse.move(x, 300, { steps: 4 }); await page.mouse.up(); };
  const lay = await box(".layout");
  await dragBar(lay.x + lay.width - 480);
  ok("dragging sets the assessment column", Math.abs((await box(".assess")).width - 480) <= 2, Math.round((await box(".assess")).width));
  await dragBar(0);
  ok("email column cannot be squeezed away", (await box(".reading")).width >= 335, Math.round((await box(".reading")).width));
  await dragBar(5000);
  ok("assessment column stops at its minimum", Math.round((await box(".assess")).width) === 360, Math.round((await box(".assess")).width));
  await page.focus(".vbar"); await page.keyboard.press("ArrowLeft");
  ok("arrow key widens it", Math.round((await box(".assess")).width) === 384, Math.round((await box(".assess")).width));
  await page.dispatchEvent(".vbar", "dblclick");
  const dflt = Math.round((await box(".assess")).width);
  ok("double click restores the default", dflt > 384, dflt);
  await page.evaluate(() => window.scrollTo(0, 0));
  await dragBar(lay.x + lay.width - 450);

  // Export, import, old files
  const saveAs = async () => { const [d] = await Promise.all([page.waitForEvent("download"), page.click("#export")]); return { name: d.suggestedFilename(), text: fs.readFileSync(await d.path(), "utf8") }; };
  await page.click("#export");
  ok("export refused without a name", /όνομά/.test(await page.textContent("#msg")));
  await page.fill("#reviewer", "Δοκιμή Χ.");
  await page.locator('[data-key="cand1"]').click();
  const file = await saveAs();
  ok("file name carries the reviewer", file.name === "business_review_Δοκιμή_Χ_.csv", file.name);
  const lines = file.text.replace(/^﻿/, "").split(/\r?\n/);
  ok("file keeps the old columns first, adds the ranks and actions", lines[0] === "id,business_category,business_comment,reviewer,reviewed_at,business_category_2,business_category_3,business_actions", lines[0]);
  ok("row holds the rank and actions", lines[1].includes('"Βεβαιώσεις οφειλής"') && lines[1].includes('"Αντίγραφα συμβάσεων"') && lines[1].includes("request"), lines.length);
  await page.click("#clear");
  ok("clearing removes the review", (await page.textContent("#export")) === "Εξαγωγή (0)");
  await page.setInputFiles("#file", { name: "x.csv", mimeType: "text/csv", buffer: Buffer.from(file.text) });
  await page.waitForTimeout(60);
  names = await slotNames();
  ok("import restores order and actions", names[1] === "Αντίγραφα συμβάσεων" && /ενέργεια/.test(await stateText()), names);
  await page.setInputFiles("#file", { name: "old.csv", mimeType: "text/csv", buffer: Buffer.from('﻿id,business_category,business_comment,reviewer,reviewed_at\r\n"id1","GDPR","παλιό","Α",""\r\n') });
  await page.waitForTimeout(60);
  await page.locator("#items .item").nth(1).click();
  names = await slotNames();
  ok("a file from the earlier version still loads", names.length === 1 && names[0] === "GDPR" && (await page.inputValue("#comment")) === "παλιό", names);

  // The page stays still behind an open panel
  const pageY = () => page.evaluate(() => window.scrollY);
  const widthBefore = (await box("#detail")).width;
  await page.evaluate(() => { window.scrollTo(0, 300); document.getElementById("other").click(); });
  await page.waitForTimeout(40);
  await page.mouse.move(6, 400);
  await page.mouse.wheel(0, 400);
  await page.waitForTimeout(80);
  ok("page does not scroll behind an open panel", (await pageY()) === 300, await pageY());
  ok("page does not jump sideways when a panel opens", Math.abs((await box("#detail")).width - widthBefore) <= 1);
  await page.click("#catDone");
  ok("your place on the page is kept", (await pageY()) === 300, await pageY());
  await page.mouse.wheel(0, 200);
  await page.waitForTimeout(80);
  ok("page scrolls again once the panel closes", (await pageY()) > 300, await pageY());
  await page.evaluate(() => window.scrollTo(0, 0));

  // Help tabs
  await page.click("#help"); await page.click("#tabFiles");
  ok("instruction tabs work", (await page.locator("#panFiles").isVisible()) && !(await page.locator("#panReview").isVisible()));
  await page.click("#helpClose");

  // Reload keeps everything
  await page.click("#tList"); await page.waitForTimeout(320);
  await page.reload(); await page.waitForTimeout(120);
  ok("list choice remembered, no animation on load", Math.round((await box("#list")).width) === 0);
  ok("name and review remembered", (await page.inputValue("#reviewer")) === "Δοκιμή Χ." && (await page.textContent("#export")) === "Εξαγωγή (2)", await page.textContent("#export"));
  ok("column width remembered", Math.abs((await box(".assess")).width - 450) <= 2, Math.round((await box(".assess")).width));

  // Reviews saved by the earlier version of the page
  await page.evaluate(() => localStorage.setItem("classifier-review-verdicts", JSON.stringify({ id0: { cat: "GDPR", comment: "x", at: "" } })));
  await page.reload(); await page.waitForTimeout(120);
  names = await slotNames();
  ok("reviews saved by the earlier version are kept", names.length === 1 && names[0] === "GDPR", names);

  // Reduced motion: shorter, not removed
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.click("#tList");
  const motion = new Set(), until = Date.now() + 300;
  while (Date.now() < until) { motion.add(Math.round((await box("#list")).width)); await page.waitForTimeout(8); }
  ok("animation still visible with reduced motion", motion.size > 2, { steps: motion.size });
  await page.click("#tList"); await page.waitForTimeout(200);
  const foldBox = page.locator("#reading .fold").first(), before = (await foldBox.boundingBox()).height;
  await page.locator("#reading .fold-head").first().click();
  const shrink = new Set(), until1 = Date.now() + 300;
  while (Date.now() < until1) { shrink.add(Math.round((await foldBox.boundingBox()).height)); await page.waitForTimeout(8); }
  ok("hiding an email still animates with reduced motion", [...shrink].some((v) => v > 5 && v < before - 5), { steps: shrink.size });
  ok("no script errors", page.scriptErrors === 0, page.scriptErrors);
  await context.close();
}

async function realData(browser, w, h) {
  const tag = `real ${w}x${h}`;
  const context = await browser.newContext({ viewport: { width: w, height: h } });
  const page = await open(context, REAL);
  const c = await page.evaluate(async () => {
    const c = { emails: 0, sideways: 0, innerScroll: 0, notThree: 0, noReason: 0, emptyBody: 0, htmlTags: 0, chains: 0, seams: 0, proposedMany: 0, noAction: 0, noWhy: 0, actionsPerEmail: {}, wizardOutsideEmails: 0, msAvg: 0, msMax: 0 };
    const own = JSON.stringify([D.spec, E.map((e) => e.action)]).toLowerCase();
    c.wizardOutsideEmails = (own.match(/wizard|\bwiz\b/g) || []).length;
    let spent = 0;
    for (const e of shown) {
      const t0 = performance.now();
      show(e);
      document.documentElement.getBoundingClientRect();
      const dt = performance.now() - t0; spent += dt; c.msMax = Math.max(c.msMax, Math.round(dt));
      c.emails++;
      if (document.documentElement.scrollWidth > innerWidth + 1) c.sideways++;
      if ([...document.querySelectorAll(".assess,.reading,.panel,.sheet,.why")].some((n) => getComputedStyle(n).overflowY !== "visible")) c.innerScroll++;
      if (e.top3.length !== 3) c.notThree++;
      if (e.top3.some((t) => !t.why)) c.noReason++;
      if (!e.chain[0].body) c.emptyBody++;
      if ([...document.querySelectorAll("#reading .body")].some((n) => /<\s*\/?\s*(html|head|body|div|p|br|table|tr|td|span|font|style|meta)\b[^>]*>/i.test(n.textContent))) c.htmlTags++;
      if (e.chain.length > 1) { c.chains++; c.seams += e.chain.length - 1; }
      if (e.top3[1].p >= D.also) c.proposedMany++;
      if (!e.action) c.noAction++;
      else {
        const n = e.action.items.length; c.actionsPerEmail[n] = (c.actionsPerEmail[n] || 0) + 1;
        if (e.action.items.some((x) => !x.why.length)) c.noWhy++;
      }
    }
    c.msAvg = Math.round(spent / c.emails);
    return c;
  });
  notes[tag] = c;
  ok(`${tag}: nothing goes off the page or into a scroll box`, c.emails > 0 && c.sideways === 0 && c.innerScroll === 0, c);
  ok(`${tag}: three probabilities and clean text on every email`, c.notThree === 0 && c.htmlTags === 0, { notThree: c.notThree, htmlTags: c.htmlTags });
  ok(`${tag}: no wizard in anything we wrote`, c.wizardOutsideEmails === 0, c.wizardOutsideEmails);
  await page.click("#other");
  const r = await tileReport(page, "#catTiles .tile");
  ok(`${tag}: real category panel, boxes equal`, r.widths === 1 && r.heights === 1 && r.clipped === 0, r);
  await page.click("#catDone");
  ok(`${tag}: no script errors`, page.scriptErrors === 0, page.scriptErrors);
  await context.close();
}

(async () => {
  const browser = await loadPlaywright().chromium.launch();
  let error = null;
  try {
    for (const [w, h] of [[1920, 1080], [1536, 730], [1366, 768], [1366, 620], [1280, 600], [1101, 640], [1024, 600], [800, 600], [390, 800]]) await layoutAt(browser, w, h);
    await behaviour(browser);
    if (REAL) { await realData(browser, 1366, 768); await realData(browser, 1280, 620); }
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
