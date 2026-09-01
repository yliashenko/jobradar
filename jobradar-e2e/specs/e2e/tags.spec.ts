import { test, expect } from '../../fixtures/server';
import { FeedPage } from '../../pages/feed.page';
import { TagsPage } from '../../pages/tags.page';
import { writeProfile } from '../../fixtures/overlays';
import { sel } from '../../utils/selectors';

test.describe('Tags cloud', () => {
  test('lists the seeded technologies @smoke', async ({ page }) => {
    const tags = new TagsPage(page);
    await tags.open();
    await expect(tags.tag('Playwright')).toBeVisible();
    await expect(tags.tag('pytest')).toBeVisible();
  });

  test('reflects every unique tag from the seed @regression', async ({ page }) => {
    const tags = new TagsPage(page);
    await tags.open();
    await expect(tags.tags()).toHaveCount(18);
  });

  test('clicking a tag applies the tag filter @regression', async ({ page }) => {
    const tags = new TagsPage(page);
    await tags.open();
    await tags.tag('pytest').click();
    await expect(page).toHaveURL(/tech=pytest/);
  });
});

test.describe('Tag filter', () => {
  test('clicking a tag narrows the feed to cards carrying it @smoke', async ({ page }) => {
    const feed = new FeedPage(page);
    await feed.open();
    await feed.filterByTag('pytest');
    await expect(feed.cards()).toHaveCount(3); // v1, v4, v5 carry pytest
    await expect(feed.card('v2')).toHaveCount(0);
  });

  test('the tag filter respects word boundaries: Java does not match JavaScript @regression', async ({ page }) => {
    const feed = new FeedPage(page);
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
    await expect(page.locator(sel.cardOf('v1'))).toBeVisible();
    await expect(page.locator(sel.cardOf('v2'))).toHaveCount(0);
  });

  test('clicking an already-included tag flips it to exclude @regression', async ({ page }) => {
    await page.goto('/?status=all&tech=Playwright');
    await page.locator(sel.tag('Playwright')).first().click();
    expect(page.url()).toContain('notech=Playwright');
    await expect(page.locator(sel.cardOf('v1'))).toHaveCount(0);
  });
});

// Profile "not for me" (exclude) mutes a skill two ways: out of the tags cloud,
// and a vacancy whose TITLE carries it is hidden from the feed.
test.describe('anti-goal (not for me) muting', () => {
  test('an excluded skill is muted from the tags cloud @regression', async ({ page, server }) => {
    await writeProfile(server.home, { exclude: ['JavaScript'] });
    const tags = new TagsPage(page);
    await tags.open();
    await expect(tags.tag('JavaScript')).toHaveCount(0);
    await expect(tags.tag('Playwright')).toBeVisible();
  });

  test('a vacancy whose title carries an excluded skill is hidden from the feed @regression', async ({ page, server }) => {
    await writeProfile(server.home, { exclude: ['JavaScript'] });
    await page.goto('/');
    await expect(page.locator(sel.cardOf('v3'))).toHaveCount(0); // title "…(JavaScript)"
    await expect(page.locator(sel.cardOf('v1'))).toBeVisible();
  });
});
