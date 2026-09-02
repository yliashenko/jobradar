import { test, expect } from '../../fixtures/server';
import { FeedPage } from '../../pages/feed.page';
import { TagsPage } from '../../pages/tags.page';
import { writeProfile } from '../../fixtures/overlays';
import { sel } from '../../utils/selectors';

test.describe('Tags cloud', () => {
  let tagsPage: TagsPage;
  test.beforeEach(async ({ page }) => { tagsPage = new TagsPage(page); });

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

  // Profile "not for me" (exclude) mutes a skill two ways: out of the tags cloud,
  // and a vacancy whose TITLE carries it is hidden from the feed.
  test('an excluded skill is muted from the tags cloud @regression', async ({ page, server }) => {
    await writeProfile(server.home, { exclude: ['JavaScript'] });
    const tags = new TagsPage(page);
    await tags.open();
    await expect(tags.tag('JavaScript')).toHaveCount(0);
    await expect(tags.tag('Playwright')).toBeVisible();
  });
});
