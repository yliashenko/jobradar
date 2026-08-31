import { test, expect } from '../../fixtures/server';
import { FeedPage } from '../../pages/feed.page';

const card = (h: string) => `[data-testid="job-card"][data-hash="${h}"]`;

test.describe('Vacancy filters', () => {
  test('by status keeps only that status @regression', async ({ page }) => {
    const feed = new FeedPage(page);
    await feed.filter({ status: 'applied' });
    await expect(feed.cards()).toHaveCount(1);
  });

  test('by source keeps only that source @regression', async ({ page }) => {
    const feed = new FeedPage(page);
    await feed.filter({ source: 'djinni' });
    await expect(feed.cards()).toHaveCount(2);
  });

  test('by minimum score keeps only high-scored cards @regression', async ({ page }) => {
    const feed = new FeedPage(page);
    await feed.filter({ min: '8' });
    await expect(feed.cards()).toHaveCount(2);
  });

  test('by full-text search matches the title @regression', async ({ page }) => {
    const feed = new FeedPage(page);
    await feed.filter({ q: 'SDET' });
    await expect(feed.cards()).toHaveCount(1);
  });

  test('by tech tag keeps only cards carrying it @regression', async ({ page }) => {
    const feed = new FeedPage(page);
    await feed.filter({ tech: 'Python' });
    await expect(feed.cards()).toHaveCount(2);
  });

  test('combined source and score filters narrow together @regression', async ({ page }) => {
    const feed = new FeedPage(page);
    await feed.filter({ source: 'dou', min: '8' });
    await expect(feed.cards()).toHaveCount(2);
  });
});

// Seeded dated rows: v9 = 3d, v10 = 10d, v11 = 40d old (first_seen via days_ago).
test.describe('period filter', () => {
  test('the week filter keeps recent vacancies and drops older ones @regression', async ({ page }) => {
    await page.goto('/?days=7');
    await expect(page.locator(card('v9'))).toBeVisible();
    await expect(page.locator(card('v11'))).toHaveCount(0);
  });

  test('the two-weeks filter keeps a 10-day-old vacancy @regression', async ({ page }) => {
    await page.goto('/?days=14');
    await expect(page.locator(card('v10'))).toBeVisible();
    await expect(page.locator(card('v11'))).toHaveCount(0);
  });
});
