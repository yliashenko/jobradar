import { test, expect } from '../../fixtures/server';
import { FeedPage } from '../../pages/feed.page';
import { Routes } from '../../utils/routes';
import { sel } from '../../utils/selectors';

const scoreNum = `${sel.card} ${sel.scoreOpen} .num`;

test.describe('Feed', () => {
  test('the default feed shows new vacancies and hides triaged ones @smoke', async ({ page }) => {
    await page.goto(Routes.feed);
    await expect(page.locator(sel.cardOf('v1'))).toBeVisible();
    await expect(page.locator(sel.cardOf('v6'))).toHaveCount(0);
    await expect(page.locator(sel.cardOf('v7'))).toHaveCount(0);
  });

  test('every card on the default feed is in the `new` status @smoke', async ({ page }) => {
    await page.goto(Routes.feed);
    const cards = await page.locator(sel.card).count();
    expect(cards).toBeGreaterThan(0);
    await expect(page.locator(`${sel.statusBtn('new')}.on`)).toHaveCount(cards);
  });

  test('changing a card status through the UI persists across navigation @regression', async ({ page }) => {
    const feed = new FeedPage(page);
    await feed.open();
    await expect(feed.card('v1')).toHaveCount(1);
    await feed.setStatus('v1', 'interested');
    await expect(feed.card('v1')).toHaveCount(0);
    await feed.open('?status=interested');
    await expect(feed.card('v1')).toHaveCount(1);
  });

  test('an archived vacancy is absent from the all tab @regression', async ({ page }) => {
    await page.goto('/?status=all');
    await expect(page.locator(sel.cardOf('v_arch'))).toHaveCount(0);
    await expect(page.locator(sel.cardOf('v1'))).toBeVisible(); // guard vs empty-page false pass
  });
});

test.describe('feed card interactions', () => {
  // djinni = two different companies, so company-grouping doesn't reorder the sort.
  test('the default feed sorts by score high → low @regression', async ({ page }) => {
    await page.goto('/?source=djinni');
    const scores = (await page.locator(scoreNum).allInnerTexts()).map(parseFloat);
    expect(scores.length).toBeGreaterThan(1);
    expect(scores).toEqual([...scores].sort((a, b) => b - a));
  });

  test('sort=score_asc orders the feed by score low → high @regression', async ({ page }) => {
    await page.goto('/?source=djinni&sort=score_asc');
    const scores = (await page.locator(scoreNum).allInnerTexts()).map(parseFloat);
    expect(scores.length).toBeGreaterThan(1);
    expect(scores).toEqual([...scores].sort((a, b) => a - b));
  });

  test('a card description expands in place @regression', async ({ page }) => {
    await page.goto('/');
    const first = page.locator(sel.card).first();
    await expect(first.locator('.desc')).toBeHidden(); // guard: an always-visible .desc can't pass
    await first.locator('details.unfold summary').click();
    await expect(first.locator('details.unfold')).toHaveAttribute('open', '');
    await expect(first.locator('.desc')).toBeVisible();
  });

  test('an unscored card sinks to the bottom under score high → low @regression', async ({ page }) => {
    await page.goto('/?status=all&tech=API');
    await expect(page.locator(sel.card).last()).toHaveAttribute('data-hash', 'v8');
  });

  test('an unscored card sinks to the bottom under score low → high @regression', async ({ page }) => {
    await page.goto('/?status=all&tech=API&sort=score_asc');
    await expect(page.locator(sel.card).last()).toHaveAttribute('data-hash', 'v8');
  });
});
