import { test, expect } from '../../fixtures/server';
import { sel } from '../../utils/selectors';

// v1 is seeded with a full scorer breakdown, so these run on seeded state alone.
const v1 = sel.cardOf('v1');

test.describe('score details', () => {
  test('the score popup shows band, verdict, covers and gaps @regression', async ({ page }) => {
    await page.goto('/');
    await page.locator(`${v1} ${sel.scoreOpen}`).click();

    const modal = page.locator(sel.scoreModal('v1'));
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
    await page.locator(`${v1} ${sel.scoreOpen}`).click();
    const marks = page.locator(sel.scoreModal('v1')).locator('.scorepop-verdict b.tech');
    await expect(marks.filter({ hasText: 'Playwright' })).toHaveCount(1);
  });

  test('a scored card shows its mark and the threshold on the rail @regression', async ({ page }) => {
    await page.goto('/');
    const rail = page.locator(v1).locator('.rail').first();
    await expect(rail.locator('.rail-threshold')).toHaveCount(1);
    await expect(rail.locator('.rail-mark')).toHaveCount(1);
    await expect(page.locator(`${v1} ${sel.scoreOpen} .num`)).toHaveText('8.7');
  });

  // scorer off + no key → an unscored card offers the "needs a key" affordance.
  test('an unscored card shows the no-key scoring affordance @regression', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator(`${sel.cardOf('v8')} [data-testid="score-nokey"]`)).toBeVisible();
  });
});
