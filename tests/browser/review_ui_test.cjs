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
  const context = await browser.newContext({ viewport: { width: 1600, height: 900 } });
  const page = await context.newPage();
  let scriptErrors = 0;
  let consoleErrors = 0;
  page.on("pageerror", () => scriptErrors++);
  page.on("console", (m) => { if (m.type() === "error") consoleErrors++; });
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
    const kind = await page.$eval("#viewer-body", (b) => b.firstElementChild ? b.firstElementChild.tagName + (b.firstElementChild.className ? "." + b.firstElementChild.className : "") : "none");
    ok("attachment opens in the viewer", ["IFRAME", "DIV.img", "DIV.nopreview"].includes(kind), { kind });
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

  await page.click("#lang");
  ok("language switches to English", (await page.getAttribute("html", "lang")) === "en");
  await page.click("#lang");
  await page.reload();
  const reopened = await page.waitForSelector("#case h2", { timeout: 15000 }).then(() => true, () => false);
  ok("reload keeps the open case", reopened);
  await page.screenshot({ path: path.join(OUTPUT, "review_1600x900.png") });

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
  await context.close();
}

(async () => {
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({ headless: !args.includes("--headed") });
  try {
    await behaviour(browser);
    for (const [w, h] of [[1920, 1080], [1366, 768], [1280, 600], [800, 900]]) await layoutAt(browser, w, h);
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
