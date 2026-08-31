import { test, expect } from '../../fixtures/server';
import { HttpStatus } from '../../utils/http';
import { Routes } from '../../utils/routes';

const PAGES = [Routes.feed, Routes.runs, Routes.tags, Routes.stats, Routes.calendar, Routes.profile];

test.describe('Pages render', () => {
  for (const path of PAGES) {
    test(`GET ${path} returns 200 @smoke`, async ({ request }) => {
      const res = await request.get(path);
      expect(res.status()).toBe(HttpStatus.Ok);
    });
  }
});
