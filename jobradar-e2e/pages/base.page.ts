import { type Page, type Locator } from '@playwright/test';

export abstract class BasePage {
  constructor(protected readonly page: Page) {}

  cards(): Locator {
    return this.page.getByTestId('job-card');
  }

  card(hash: string): Locator {
    return this.page.locator(`[data-testid="job-card"][data-hash="${hash}"]`);
  }
}
