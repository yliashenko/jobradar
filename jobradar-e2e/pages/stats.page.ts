import { type Locator } from '@playwright/test';
import { BasePage } from './base.page';
import { Routes } from '../utils/routes';

export class StatsPage extends BasePage {
  async open(): Promise<void> {
    await this.page.goto(Routes.stats);
  }

  section(name: string): Locator {
    return this.page.getByRole('heading', { name });
  }

  rows(): Locator {
    return this.page.locator('.statrow');
  }
}
