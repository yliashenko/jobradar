import { type Locator } from '@playwright/test';
import { BasePage } from './base.page';
import { Routes } from '../utils/routes';

export class RunsPage extends BasePage {
  async open(): Promise<void> {
    await this.page.goto(Routes.runs);
  }

  heading(): Locator {
    return this.page.getByRole('heading', { name: 'Recent scans' });
  }

  emptyState(): Locator {
    return this.page.locator('.empty').first();
  }
}
