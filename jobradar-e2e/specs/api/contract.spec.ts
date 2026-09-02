import { test, expect } from '../../fixtures/server';
import { HttpStatus } from '../../utils/http';
import { vacancyStatuses } from '../../utils/statuses';

// Contract layer (request, no browser): assertions on the raw HTTP response.
test.describe('POST /status redirect contract', () => {
  test('a valid status returns 303 with a Location @regression', async ({ api }) => {
    const res = await api.setStatus('v1', vacancyStatuses.interested);

    expect(res.status()).toBe(HttpStatus.SeeOther);
    expect(res.headers()['location']).toBe('/');
  });

  test('the status change persists over the wire @regression', async ({ api }) => {
    await api.setStatus('v1', vacancyStatuses.interested);
    const feed = await api.feed('?status=interested');
    expect(feed.status()).toBe(HttpStatus.Ok);
    expect(await feed.text()).toContain('data-hash="v1"');
  });
});

// resetState deletes profile.json before each test, so the save is isolated.
test.describe('POST /profile redirect contract', () => {
  test('save returns 303 to the saved view @regression', async ({ request }) => {
    const res = await request.post('/profile', { form: { action: 'save' }, maxRedirects: 0 });
    expect(res.status()).toBe(HttpStatus.SeeOther);
    expect(res.headers()['location']).toContain('/profile?saved=1');
  });
});
