import { test, expect } from '../../fixtures/server';
import { writeProfile, writeFacts } from '../../fixtures/overlays';
import { sel } from '../../utils/selectors';

const FACTS = 'QA Automation Engineer. Playwright, pytest, API. 6 years.';

test.describe('application tracker', () => {
  test('archiving an applied vacancy removes it from the feed @regression', async ({ request, page }) => {
    await request.post('/hiring/update', { form: { hash: 'v7', archive: '1' }, maxRedirects: 0 });
    await page.goto('/?status=all');
    await expect(page.locator(sel.cardOf('v7'))).toHaveCount(0);
  });

  test('moving an applied vacancy to a stage marks it active @regression', async ({ request, page }) => {
    await request.post('/hiring/update', { form: { hash: 'v7', go: 'pre_screen' }, maxRedirects: 0 });
    await page.goto('/hiring');
    const stage = page.locator(
      '[data-testid="hiring-card"][data-hash="v7"] [data-testid="hiring-stage"][data-stage="pre_screen"]',
    );
    await expect(stage).toHaveClass(/\bon\b/);
  });
});

// Cover letters run through the same OpenAI-compatible path as the scorer, so the
// per-worker stub answers them. The graceful-degrade cases need no LLM at all.
test.describe('cover letter', () => {
  test('missing career-facts.md returns a helpful error @regression', async ({ request }) => {
    const res = await request.post('/hiring/cover', { form: { hash: 'v7' } });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.ok).toBe(false);
    expect(body.error).toContain('career-facts.md');
  });

  test('no API key returns a key-needed error @regression', async ({ request, server }) => {
    await writeFacts(server.home, FACTS);
    const body = await (await request.post('/hiring/cover', { form: { hash: 'v7' } })).json();
    expect(body.ok).toBe(false);
    expect(body.error).toContain('API key');
  });

  test('generates a cover letter via the stub and caches it @regression', async ({ request, server }) => {
    await writeFacts(server.home, FACTS);
    await writeProfile(server.home, {
      api_key: 'test',
      llm_provider: 'openai',
      llm_base_url: server.llmUrl,
      llm_model: 'stub',
    });
    const first = await (await request.post('/hiring/cover', { form: { hash: 'v7' } })).json();
    expect(first.ok).toBe(true);
    expect(first.cached).toBe(false);
    expect(first.letter).toContain('stub cover letter');

    const second = await (await request.post('/hiring/cover', { form: { hash: 'v7' } })).json();
    expect(second.cached).toBe(true); // served from cover_data, no regeneration
  });
});
