import { test, expect } from '../../fixtures/server';
import { configureRun } from '../../fixtures/run';
import { runScan } from '../../fixtures/helpers';
import { sel } from '../../utils/selectors';

// Flagship complex-e2e: heavy prep (fixture source + stub LLM + a real scan), a
// thin UI assertion. The pipeline logic stays in pytest; these prove it surfaces
// end-to-end. runScan is synchronous, so there's no async/lock race with the
// per-test reset — POST /run's async trigger is covered by ops.spec.
test.describe('pipeline run', () => {
  test('a fresh scan surfaces a scored vacancy in the feed @regression', async ({ page, server }) => {
    await configureRun(server.home, server.llmUrl, [
      { title: 'Fixture QA Automation', company: 'Fixture Co', description: 'Playwright, pytest' },
    ]);
    await runScan(server.home);

    await page.goto('/?status=all');
    const c = page.locator(sel.card, { hasText: 'Fixture QA Automation' });
    await expect(c).toBeVisible();
    await expect(c.locator(sel.scoreOpen)).toBeVisible();
  });

  test('the same vacancy from two sources is shown once @regression', async ({ page, server }) => {
    await configureRun(server.home, server.llmUrl, [
      { title: 'Crosspost SDET Role', company: 'CrossCo', source: 'dou', url: 'https://example.test/dou' },
      { title: 'Crosspost SDET Role', company: 'CrossCo', source: 'djinni', url: 'https://example.test/djinni' },
    ]);
    await runScan(server.home);

    await page.goto('/?status=all');
    await expect(page.locator(sel.card, { hasText: 'Crosspost SDET Role' })).toHaveCount(1);
  });

  test('two vacancies differing only in case/whitespace collapse to one @regression', async ({ page, server }) => {
    await configureRun(server.home, server.llmUrl, [
      { title: 'Senior QA Engineer', company: 'DupCo', url: 'https://example.test/a' },
      { title: '  senior   qa engineer ', company: 'dupco', url: 'https://example.test/b' },
    ]);
    await runScan(server.home);

    await page.goto('/?status=all');
    await expect(page.locator(sel.card, { hasText: /senior qa engineer/i })).toHaveCount(1);
  });

  // digits are not stripped — a deliberate trade-off (better extra than a miss).
  test('two vacancies differing only by a digit in the title stay separate @regression', async ({ page, server }) => {
    await configureRun(server.home, server.llmUrl, [
      { title: 'QA Engineer #1', company: 'NumCo', url: 'https://example.test/1' },
      { title: 'QA Engineer #2', company: 'NumCo', url: 'https://example.test/2' },
    ]);
    await runScan(server.home);

    await page.goto('/?status=all');
    await expect(page.locator(sel.card, { hasText: 'QA Engineer #' })).toHaveCount(2);
  });

  // L0 excludes by title, not body.
  test('a title matching an L0 exclude is dropped, others survive @regression', async ({ page, server }) => {
    await configureRun(
      server.home,
      server.llmUrl,
      [
        { title: 'Manual QA Tester', company: 'ExclCo', description: 'testing' },
        { title: 'Automation QA Wizard', company: 'PassCo', description: 'Playwright' },
      ],
      { l0: { exclude_title: ['[Mm]anual'] } },
    );
    await runScan(server.home);

    await page.goto('/?status=all');
    await expect(page.locator(sel.card, { hasText: 'Automation QA Wizard' })).toBeVisible();
    await expect(page.locator(sel.card, { hasText: 'Manual QA Tester' })).toHaveCount(0);
  });
});
