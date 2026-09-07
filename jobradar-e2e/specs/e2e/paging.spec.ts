import { test, expect } from '../../fixtures/server';
import { FeedPage } from '../../pages/feed.page';
import { seedSet } from '../../fixtures/overlays';
import { sel } from '../../utils/selectors';

// The feed pages at views.FEED_PAGE (25). The catalog holds 9 'new' rows — under
// one page on purpose, so every other spec asserts exact counts with no pager in
// the way. These tests add the `paging` set (30 more 'new' rows) on top, giving
// 39 in the tab: a full page of 25 and a remainder of 14.
const PAGE = 25;
const NEW_ROWS = 39;
const LAST_PAGE_ROWS = NEW_ROWS - PAGE;

test.describe('Feed pager', () => {
  let feed: FeedPage;
  test.beforeEach(async ({ page }) => { feed = new FeedPage(page); });

  test('a feed shorter than one page shows no pager @regression', async () => {
    await feed.open();
    await expect(feed.pager()).toHaveCount(0);
  });

  test.describe('with more vacancies than fit one page', () => {
    test.beforeEach(async ({ server }) => { await seedSet(server.home, 'paging'); });

    test('the first page renders exactly one page of cards @smoke', async () => {
      await feed.open();
      await expect(feed.cards()).toHaveCount(PAGE);
    });

    test('the first page offers the next one and not the previous @regression', async () => {
      await feed.open();
      await expect(feed.pager().locator(sel.pagerNext)).toBeVisible();
      await expect(feed.pager().locator(sel.pagerPrev)).toHaveCount(0);
    });

    test('the counter names the whole match, not just the page @regression', async () => {
      await feed.open();
      await expect(feed.counts()).toContainText(`shown ${PAGE} of ${NEW_ROWS}`);
    });

    test('the last page holds the remainder @regression', async () => {
      await feed.open('?page=2');
      await expect(feed.cards()).toHaveCount(LAST_PAGE_ROWS);
    });

    test('the last page offers the previous one and not the next @regression', async () => {
      await feed.open('?page=2');
      await expect(feed.pager().locator(sel.pagerPrev)).toBeVisible();
      await expect(feed.pager().locator(sel.pagerNext)).toHaveCount(0);
    });

    test('walking to the next page shows different vacancies @regression', async () => {
      await feed.open();
      const first = await feed.cardHashes();
      await feed.nextPage();
      const second = await feed.cardHashes();
      expect(second.filter((h) => first.includes(h))).toEqual([]);
    });

    test('walking back returns to the first page @regression', async () => {
      await feed.open('?page=2');
      await feed.prevPage();
      await expect(feed.cards()).toHaveCount(PAGE);
    });

    test('a page past the last is clamped, not shown empty @regression', async () => {
      await feed.open('?page=99');
      await expect(feed.cards()).toHaveCount(LAST_PAGE_ROWS);
    });

    test('a non-numeric page falls back to the first @regression', async () => {
      await feed.open('?page=nonsense');
      await expect(feed.cards()).toHaveCount(PAGE);
    });

    // Otherwise a new filter would drop you on page 2 of its result, which reads
    // as vacancies missing from the top.
    test('filtering by a tag drops the page from the URL @regression', async ({ page }) => {
      await feed.open('?page=2');
      await feed.filterByTag('Selenium');
      expect(page.url()).not.toContain('page=');
    });

    test('filtering by a tag lands on its first page @regression', async () => {
      await feed.open('?page=2');
      await feed.filterByTag('Selenium');
      await expect(feed.cards()).toHaveCount(PAGE);
    });
  });
});
