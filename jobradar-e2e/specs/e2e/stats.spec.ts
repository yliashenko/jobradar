import { test, expect } from '../../fixtures/server';
import { StatsPage } from '../../pages/stats.page';
import { writeProfile } from '../../fixtures/overlays';

// Market coverage = how many of the top-demand skills the profile owns
test.describe('Stats — profile coverage', () => {
  test('an empty profile covers none of the top-demand skills @regression', async ({ page }) => {
    await page.goto('/stats'); // resetState left no profile.json → owned is empty
    const covered = parseInt(await page.locator('.big').first().innerText(), 10);
    expect(covered).toBe(0);
  });

  test('adding a demanded skill as an extra raises coverage @regression', async ({ page, server }) => {
    await writeProfile(server.home, { extra_skills: ['Playwright'] });
    await page.goto('/stats');
    const covered = parseInt(await page.locator('.big').first().innerText(), 10);
    expect(covered).toBeGreaterThan(0);
  });
});

test.describe('Stats', () => {
  test('shows the vacancies-by-source section @smoke', async ({ page }) => {
    const stats = new StatsPage(page);
    await stats.open();
    await expect(stats.section('Vacancies by source')).toBeVisible();
  });

  test('shows the Djinni comparison section @regression', async ({ page }) => {
    const stats = new StatsPage(page);
    await stats.open();
    await expect(stats.section('Djinni: what DOU does not have')).toBeVisible();
  });

  test('renders stat rows @regression', async ({ page }) => {
    const stats = new StatsPage(page);
    await stats.open();
    await expect(stats.rows().first()).toBeVisible();
  });
});
