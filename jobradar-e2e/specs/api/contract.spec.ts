import { test, expect } from '../../fixtures/server';
import { HttpStatus } from '../../utils/http';

// API / contract layer (request, no browser). The overlay found that only the
// 400 (invalid status) and 405 (wrong method) cases on POST /status were
// asserted — never the 303 a *valid* status returns, nor that the write lands.

// PW-FEED-5: assertion is on the raw response (status + Location) and a
// read-back of the feed body over the wire.
test.describe('POST /status redirect contract', () => {
  test('a valid status returns 303 with a Location @regression', async ({ api }) => {
    const res = await api.setStatus('v1', 'interested');
    expect(res.status()).toBe(HttpStatus.SeeOther);
    expect(res.headers()['location']).toBe('/');
  });

  test('the status change persists over the wire @regression', async ({ api }) => {
    await api.setStatus('v1', 'interested');
    const feed = await api.feed('?status=interested');
    expect(feed.status()).toBe(HttpStatus.Ok);
    expect(await feed.text()).toContain('data-hash="v1"');
  });
});

// PW-PRO-4 — save contract. Assertion on the raw response (303 + Location),
// not the rendered page. resetState deletes profile.json before each test, so a
// save here is isolated.
test.describe('POST /profile redirect contract', () => {
  test('save returns 303 to the saved view @regression', async ({ request }) => {
    const res = await request.post('/profile', { form: { action: 'save' }, maxRedirects: 0 });
    expect(res.status()).toBe(HttpStatus.SeeOther);
    expect(res.headers()['location']).toContain('/profile?saved=1');
  });
});
