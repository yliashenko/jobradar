import { test, expect } from '../../fixtures/server';
import { FeedPage } from '../../pages/feed.page';
import { sel } from '../../utils/selectors';
import { vacancyStatuses } from '../../utils/statuses';

test.describe('Vacancy filters', () => {
  // 'applied' is intentionally not used here: that tab renders the hiring
  // pipeline (hiring cards), covered in hiring.spec.ts. 'interested' is a plain
  // feed tab, so the ranked job-card list still applies.

  let feed: FeedPage;
  test.beforeEach(async ({ page }) => { feed = new FeedPage(page); });

  test('by status keeps only that status @regression', async () => {
    await feed.filter({ status: vacancyStatuses.interested });
    await expect(feed.cards()).toHaveCount(1);
  });

  test('by source keeps only that source @regression', async () => {
    await feed.filter({ source: 'djinni' });
    await expect(feed.cards()).toHaveCount(2);
  });

  test('by minimum score keeps only high-scored cards @regression', async () => {
    await feed.filter({ min: '8' });
    await expect(feed.cards()).toHaveCount(2);
  });

  test('by full-text search matches the title @regression', async () => {
    await feed.filter({ q: 'SDET' });
    await expect(feed.cards()).toHaveCount(1);
  });

  test('by tech tag keeps only cards carrying it @regression', async () => {
    await feed.filter({ tech: 'Python' });
    await expect(feed.cards()).toHaveCount(2);
  });

  test('combined source and score filters narrow together @regression', async () => {
    await feed.filter({ source: 'dou', min: '8' });
    await expect(feed.cards()).toHaveCount(2);
  });
});

// Seeded dated rows: v9 = 3d, v10 = 10d, v11 = 40d old (first_seen via days_ago).
test.describe('Period filter', () => {
  test('the week filter keeps recent vacancies and drops older ones @regression', async ({ page }) => {
    await page.goto('/?days=7');
    await expect(page.locator(sel.jobCardOf('v9'))).toBeVisible();
    await expect(page.locator(sel.jobCardOf('v11'))).toHaveCount(0);
  });

  test('the two-weeks filter keeps a 10-day-old vacancy @regression', async ({ page }) => {
    await page.goto('/?days=14');
    await expect(page.locator(sel.jobCardOf('v10'))).toBeVisible();
    await expect(page.locator(sel.jobCardOf('v11'))).toHaveCount(0);
  });
});

test.describe('Tag filter', () => {
  let feed: FeedPage;
  test.beforeEach(async ({ page }) => { feed = new FeedPage(page); });

  test('clicking a tag narrows the feed to cards carrying it @smoke', async () => {
    await feed.open();
    await feed.filterByTag('pytest');
    await expect(feed.cards()).toHaveCount(3); // v1, v4, v5 carry pytest
    await expect(feed.card('v2')).toHaveCount(0);
  });

  test('the tag filter respects word boundaries: Java does not match JavaScript @regression', async () => {
    await feed.open();
    await feed.filterByTag('Java');
    await expect(feed.cards()).toHaveCount(3);
    await expect(feed.card('v3')).toHaveCount(0);
  });

  // A tag cycles include → exclude → off; each transition is arranged via URL.
  test('clicking a tag adds it as an include filter @regression', async ({ page }) => {
    await page.goto('/');
    await page.locator(sel.tag('Playwright')).first().click();
    expect(page.url()).toContain('tech=Playwright');
    await expect(page.locator(sel.jobCardOf('v1'))).toBeVisible();
    await expect(page.locator(sel.jobCardOf('v2'))).toHaveCount(0);
  });

  test('clicking an already-included tag flips it to exclude @regression', async ({ page }) => {
    await page.goto('/?status=all&tech=Playwright');
    await page.locator(sel.tag('Playwright')).first().click();
    expect(page.url()).toContain('notech=Playwright');
    await expect(page.locator(sel.jobCardOf('v1'))).toHaveCount(0);
  });
});
