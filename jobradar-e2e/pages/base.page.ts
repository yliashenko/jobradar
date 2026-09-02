import { type Page, type Locator } from '@playwright/test';
import { sel } from '../utils/selectors';

export abstract class BasePage {
  constructor(protected readonly page: Page) {}

  cards(): Locator {
    return this.page.locator(sel.card);
  }

  card(hash: string): Locator {
    return this.page.locator(sel.jobCardOf(hash));
  }
}
