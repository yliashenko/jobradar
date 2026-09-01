import { type Locator } from '@playwright/test';
import { BasePage } from './base.page';
import { Routes } from '../utils/routes';
import { sel } from '../utils/selectors';

export class TagsPage extends BasePage {
  async open(): Promise<void> {
    await this.page.goto(Routes.tags);
  }

  tags(): Locator {
    return this.page.locator(sel.tagAny);
  }

  tag(term: string): Locator {
    return this.page.locator(sel.tag(term));
  }
}
