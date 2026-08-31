import { test, expect } from '../../fixtures/server';

// v1 is seeded with a full scorer breakdown (band strong, verdict, matched, gaps),
// so these run on seeded state alone — no LLM, no run. Each test opens the popup
// once (one Act) and asserts facets of that one opened modal.
const v1 = '[data-testid="job-card"][data-hash="v1"]';

test.describe('score details', () => {
  test('the score popup shows band, verdict, covers and gaps @regression', async ({ page }) => {
    await page.goto('/');
    await page.locator(`${v1} [data-testid="score-open"]`).click();

    const modal = page.locator('#score-v1[data-testid="score-modal"]');
    await expect(modal).toBeVisible();
    await expect(modal.locator('.scorepop-sub')).toContainText('strong match');
    await expect(modal.locator('.scorepop-verdict')).toContainText('Strong automation fit');

    const covers = modal.locator('.scorepop-points.covers');
    await expect(covers).toContainText('Playwright');
    await expect(covers).toContainText('pytest');
    await expect(modal.locator('.scorepop-points.gaps')).toContainText('Python is curated LLM code');
  });

  test('the score popup highlights stack terms @regression', async ({ page }) => {
    await page.goto('/');
    await page.locator(`${v1} [data-testid="score-open"]`).click();
    const marks = page.locator('#score-v1 .scorepop-verdict b.tech');
    await expect(marks.filter({ hasText: 'Playwright' })).toHaveCount(1);
  });

  test('a scored card shows its mark and the threshold on the rail @regression', async ({ page }) => {
    await page.goto('/');
    const rail = page.locator(v1).locator('.rail').first();
    await expect(rail.locator('.rail-threshold')).toHaveCount(1);
    await expect(rail.locator('.rail-mark')).toHaveCount(1);
    await expect(page.locator(`${v1} [data-testid="score-open"] .num`)).toHaveText('8.7');
  });

  // PW-SCO-4 — the e2e server runs with the scorer off and no API key, so an
  // unscored card (v8) offers the "scoring needs a key" affordance, not a score.
  test('an unscored card shows the no-key scoring affordance @regression', async ({ page }) => {
    await page.goto('/');
    const v8 = '[data-testid="job-card"][data-hash="v8"]';
    await expect(page.locator(`${v8} [data-testid="score-nokey"]`)).toBeVisible();
  });
});
