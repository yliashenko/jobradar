import { test, expect } from '../../fixtures/server';
import { FeedPage } from '../../pages/feed.page';
import { CompanyPage } from '../../pages/company.page';

test.describe('Company page', () => {
  let company: CompanyPage;
  test.beforeEach(async ({ page }) => { company = new CompanyPage(page); });

  test('opening a company shows its heading and all its vacancies @regression', async ({ page }) => {
    const feed = new FeedPage(page);

    await feed.open();
    await feed.openCompany('Acme');

    await expect(company.heading('Acme')).toBeVisible();
    await expect(company.cards()).toHaveCount(2);
  });

  test('a single-vacancy company shows exactly one card @regression', async () => {
    await company.open('Globex');
    await expect(company.heading('Globex')).toBeVisible();
    await expect(company.cards()).toHaveCount(1);
  });

  test('navigating directly by URL opens the company @regression', async () => {    
    await company.open('Umbrella');
    await expect(company.heading('Umbrella')).toBeVisible();
    await expect(company.cards()).toHaveCount(1);
  });
});
