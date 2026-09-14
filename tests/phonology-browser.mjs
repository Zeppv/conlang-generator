// Optional browser interaction test. The API itself is separately checked on D1.
// Requires Playwright locally or in the configured development runtime.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
const require = createRequire(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES ? process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES + '/runtime.js' : import.meta.url);
const {chromium} = require('playwright');
const browser = await chromium.launch({headless: true});
const page = await browser.newPage({viewport: {width: 1365, height: 1000}});
const errors = [];
page.on('pageerror', error => errors.push(error.message));
const fixture = (input, status = false) => execFileSync(process.env.PYTHON ?? 'python', ['tests/phonology_browser_fixture.py', ...(status ? ['status'] : [])], {input: JSON.stringify(input), encoding: 'utf8'});
try {
  await page.route('**/api/phonology/**', async route => {
    const status = route.request().url().endsWith('/status');
    await route.fulfill({contentType: 'application/json', body: fixture(status ? null : route.request().postDataJSON(), status)});
  });
  await page.goto(process.env.TEST_URL ?? 'http://localhost:5173');
  await page.getByRole('button', {name: 'Phonology', exact: true}).click();
  await page.getByRole('button', {name: 'Evaluate sound system'}).click();
  await page.getByText('Inventory membership and boundary checks passed.').waitFor();
  await page.getByRole('heading', {name: 'Sounds and their frequency'}).waitFor();
  await page.getByLabel('Sound inventory').fill('p a t');
  assert.equal(await page.getByText('EVALUATION COMPLETE', {exact: true}).count(), 0, 'Editing must hide stale results');
  await page.getByLabel('Sample words').fill('p a\nt a p');
  await page.getByRole('button', {name: 'Evaluate sound system'}).click();
  await page.getByText('3/3', {exact: true}).waitFor();
  const download = page.waitForEvent('download');
  await page.getByRole('button', {name: 'Download report'}).click();
  assert.equal((await download).suggestedFilename(), 'phonology-evaluation.json');
  if (process.env.TEST_SCREENSHOT) await page.screenshot({path: process.env.TEST_SCREENSHOT, fullPage: true});
  await page.setViewportSize({width: 390, height: 844});
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'No horizontal overflow on mobile');
  await page.getByLabel('Lexical comparison').selectOption('');
  await page.getByRole('button', {name: 'Evaluate sound system'}).click();
  await page.getByText('reference not selected', {exact: true}).first().waitFor();
  await page.getByRole('button', {name: 'Concept Explorer', exact: true}).click();
  await page.getByRole('heading', {name: 'Concept Explorer', exact: true}).waitFor();
  assert.deepEqual(errors, []);
  console.log('Browser: evaluation, editing, download, reference omission, navigation, and mobile layout passed.');
} finally { await browser.close(); }
