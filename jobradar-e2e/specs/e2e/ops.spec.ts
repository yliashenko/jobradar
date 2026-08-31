import { test, expect } from '../../fixtures/server';
import { HttpStatus } from '../../utils/http';

// The Scan trigger. The full run journey (scan → scored vacancy in the feed) is the
// flagship pipeline.spec test (run synchronously); here we cover the button's
// contract and UI wiring. (busy/single-flight and the no-runner 503 aren't
// distinguishable over HTTP — both trigger states redirect 303, and serve always
// wires a runner — so those stay unit-tested in pytest.)
test.describe('scan trigger', () => {
  // PW-OPS-1 (contract) — POST /run is fire-and-redirect: 303 back.
  test('POST /run returns 303 @regression', async ({ request }) => {
    const res = await request.post('/run', { form: {}, maxRedirects: 0 });
    expect(res.status()).toBe(HttpStatus.SeeOther);
  });

  // PW-OPS-1 (UI) — the header carries the Scan button, wired to POST /run.
  test('the feed shows a Scan button wired to POST /run @smoke', async ({ page }) => {
    await page.goto('/');
    const form = page.locator('form.runbox');
    await expect(form).toHaveAttribute('action', '/run');
    await expect(form).toHaveAttribute('method', 'post');
    await expect(form.locator('button')).toBeVisible();
  });
});
