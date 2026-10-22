#!/usr/bin/env node
// Render docs/playbook.html to docs/playbook.pdf (A4, page numbers) with Playwright's Chromium.
// Usage: node docs/build-pdf.cjs [--screens DIR]   (needs Playwright: npm i -g playwright, or a local install)
const path = require("path");
const { execSync } = require("child_process");

function loadPlaywright() {
  try { return require("playwright"); } catch (_) {
    const globalRoot = execSync("npm root -g").toString().trim();
    return require(path.join(globalRoot, "playwright"));
  }
}

(async () => {
  const { chromium } = loadPlaywright();
  const src = path.resolve(__dirname, "playbook.html");
  const out = path.resolve(__dirname, "playbook.pdf");
  const screensAt = process.argv.indexOf("--screens");
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    await page.goto("file://" + src, { waitUntil: "networkidle" });
    await page.evaluate(() => document.fonts.ready);
    await page.emulateMedia({ media: "print", colorScheme: "light" });
    await page.pdf({
      path: out, format: "A4", printBackground: true, preferCSSPageSize: true, displayHeaderFooter: true,
      headerTemplate: "<span></span>",
      footerTemplate: '<div style="font:8px Helvetica,Arial,sans-serif;color:#667;width:100%;padding:0 13mm;display:flex;justify-content:space-between">' +
        '<span>PRD to PR Playbook · v1.0</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>',
    });
    console.log("wrote " + out);
    if (screensAt > -1) {
      const dir = path.resolve(process.argv[screensAt + 1] || ".");
      for (const [name, opts] of [["desktop-light", { width: 1280, height: 900, scheme: "light" }],
                                   ["desktop-dark", { width: 1280, height: 900, scheme: "dark" }],
                                   ["phone-light", { width: 390, height: 844, scheme: "light" }]]) {
        const p = await browser.newPage({ viewport: { width: opts.width, height: opts.height } });
        await p.emulateMedia({ colorScheme: opts.scheme });
        await p.goto("file://" + src, { waitUntil: "networkidle" });
        await p.evaluate(() => document.fonts.ready);
        await p.screenshot({ path: path.join(dir, name + ".png"), fullPage: false });
        const overflow = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        console.log(name + ": horizontal overflow " + overflow + "px");
        await p.close();
      }
    }
  } finally {
    await browser.close();
  }
})().catch((e) => { console.error(e); process.exit(1); });
