import { type Locator } from '@playwright/test';
import { BasePage } from './base.page';
import { Routes } from '../utils/routes';

export class TagsPage extends BasePage {
  async open(): Promise<void> {
    await this.page.goto(Routes.tags);
  }

  tags(): Locator {
    return this.page.getByTestId('tag');
  }

  tag(term: string): Locator {
    return this.page.locator(`[data-testid="tag"][data-tag="${term}"]`);
  }
}
