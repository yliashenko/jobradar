import { test, expect } from '../../fixtures/server';
import { HttpStatus } from '../../utils/http';
import { sel } from '../../utils/selectors';
import { rm } from 'node:fs/promises';
import { join } from 'node:path';

// No jobs.db → get_db() returns None → every route renders the empty-state.
// We reproduce it by removing the seeded DB; resetState restores it next test.
test.describe('empty state (no database yet)', () => {
  test('every page returns 200 with no DB seeded @regression', async ({ request, server }) => {
    await rm(join(server.home, 'jobs.db'), { force: true });
    for (const path of ['/', '/runs', '/tags', '/stats', '/calendar', '/company', '/profile']) {
      const res = await request.get(path);
      expect(res.status(), `GET ${path}`).toBe(HttpStatus.Ok);
    }
  });

  test('the feed shows the empty-state message and a Scan CTA @smoke', async ({ page, server }) => {
    await rm(join(server.home, 'jobs.db'), { force: true });
    await page.goto('/');
    await expect(page.locator('.empty')).toContainText('No scan yet');
    await expect(page.locator(`${sel.runbox} button`)).toBeVisible();
  });
});
