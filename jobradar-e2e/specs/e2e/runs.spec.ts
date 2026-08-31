import { test, expect } from '../../fixtures/server';
import { HttpStatus } from '../../utils/http';
import { Routes } from '../../utils/routes';
import { RunsPage } from '../../pages/runs.page';

test.describe('Runs journal', () => {
  test('GET /runs returns 200 @smoke', async ({ request }) => {
    const res = await request.get(Routes.runs);
    expect(res.status()).toBe(HttpStatus.Ok);
  });

  test('shows the Recent scans heading @smoke', async ({ page }) => {
    const runs = new RunsPage(page);
    await runs.open();
    await expect(runs.heading()).toBeVisible();
  });

  test('shows the empty state when there were no scans @regression', async ({ page }) => {
    const runs = new RunsPage(page);
    await runs.open();
    await expect(runs.emptyState()).toBeVisible();
  });
});
