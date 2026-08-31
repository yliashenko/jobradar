import { test, expect } from '../../fixtures/server';
import { HttpStatus } from '../../utils/http';
import { Routes } from '../../utils/routes';

const UNKNOWN_PATH = '/nope';

test.describe('HTTP contract', () => {
  test('GET /health returns 200 @smoke', async ({ request }) => {
    const res = await request.get(Routes.health);
    expect(res.status()).toBe(HttpStatus.Ok);
    expect(await res.text()).toContain('ok');
  });

  test('GET on an unknown path returns 404 @regression', async ({ request }) => {
    const res = await request.get(UNKNOWN_PATH);
    expect(res.status()).toBe(HttpStatus.NotFound);
    expect(await res.text()).toContain('Not Found');
  });

  test('POST on an unknown path returns 404 @regression', async ({ request }) => {
    const res = await request.post(UNKNOWN_PATH);
    expect(res.status()).toBe(HttpStatus.NotFound);
    expect(await res.text()).toContain('Not Found');
  });

  test('POST to a GET-only route returns 405 @regression', async ({ request }) => {
    const res = await request.post(Routes.health);
    expect(res.status()).toBe(HttpStatus.MethodNotAllowed);
    expect(await res.text()).toContain('Method Not Allowed');
  });

  test('GET to a POST-only route returns 405 @regression', async ({ request }) => {
    const res = await request.get(Routes.status);
    expect(res.status()).toBe(HttpStatus.MethodNotAllowed);
    expect(await res.text()).toContain('Method Not Allowed');
  });

  test('POST /status with an invalid status returns 400 @smoke', async ({ request }) => {
    const res = await request.post(Routes.status, { form: { status: 'invalid_status', hash: 'deadbeef' } });
    expect(res.status()).toBe(HttpStatus.BadRequest);
    expect(await res.text()).toContain('Unknown status or empty identifier');
  });
});

test.describe('Authorization', () => {
  test('a request without a token is rejected with 403 @smoke', async ({ playwright, server }) => {
    const anon = await playwright.request.newContext({ baseURL: server.url, extraHTTPHeaders: {} });
    const res = await anon.get(Routes.feed);
    expect(res.status()).toBe(HttpStatus.Forbidden);
    expect(await res.text()).toContain('Invalid or missing token');
    await anon.dispose();
  });

  test('a request carrying the token header is accepted with 200 @smoke', async ({ api }) => {
    const res = await api.feed();
    expect(res.status()).toBe(HttpStatus.Ok);
  });
});
