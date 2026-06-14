import { createRequire } from "node:module";

const require = createRequire("/Users/mac/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.pnpm/playwright@1.60.0/node_modules/playwright/package.json");
const { chromium } = require("playwright");

const baseUrl = process.env.MIS_BASE_URL || "http://127.0.0.1:8090/";
const devtoolsUrl = process.env.CHROME_DEVTOOLS_URL || "http://127.0.0.1:9222";

const browser = await chromium.connectOverCDP(devtoolsUrl);
const context = browser.contexts()[0] || await browser.newContext();
const page = context.pages()[0] || await context.newPage();

const consoleMessages = [];
const failedRequests = [];

page.on("console", message => {
  if (["error", "warning"].includes(message.type())) {
    consoleMessages.push({ type: message.type(), text: message.text() });
  }
});
page.on("requestfailed", request => {
  failedRequests.push({ url: request.url(), failure: request.failure()?.errorText || "unknown" });
});
page.on("response", response => {
  if (response.status() >= 400) {
    failedRequests.push({ url: response.url(), status: response.status() });
  }
});

await page.setViewportSize({ width: 1440, height: 1000 });
await page.goto(baseUrl, { waitUntil: "networkidle", timeout: 30_000 });

const loginButton = page.getByRole("button", { name: /登\s*录|登录|登陆|进入/ });
if (await loginButton.count()) {
  await loginButton.first().click();
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(800);
}

const checks = [];
const dashboardText = await page.locator("body").innerText({ timeout: 10_000 });
checks.push({
  name: "React app loaded",
  pass: !dashboardText.includes("前端构建产物不存在") && /工作台|个人工作台|沐辰科技/.test(dashboardText),
});

for (const navName of ["订单中心", "会员管理", "库存管理", "财务报表", "系统设置"]) {
  const navButton = page.getByRole("button", { name: navName });
  if (!(await navButton.count())) {
    checks.push({ name: `Navigate ${navName}`, pass: false, reason: "navigation button not found" });
    continue;
  }
  await navButton.first().click();
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(500);
  const bodyText = await page.locator("body").innerText();
  checks.push({
    name: `Navigate ${navName}`,
    pass: bodyText.includes(navName) || bodyText.includes(navName.replace("管理", "")),
  });
}

await page.screenshot({ path: "../outputs/ui-smoke.png", fullPage: true });

const result = {
  baseUrl,
  checks,
  consoleMessages,
  failedRequests,
  passed: checks.every(check => check.pass) && failedRequests.length === 0 && consoleMessages.every(item => item.type !== "error"),
};

console.log(JSON.stringify(result, null, 2));

await browser.close();

if (!result.passed) {
  process.exitCode = 1;
}
