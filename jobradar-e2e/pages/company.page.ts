import { type Locator } from '@playwright/test';
import { BasePage } from './base.page';
import { Routes } from '../utils/routes';

export class CompanyPage extends BasePage {
  async open(name: string): Promise<void> {
    await this.page.goto(`${Routes.company}?name=${encodeURIComponent(name)}`);
  }

  heading(name: string): Locator {
    return this.page.getByRole('heading', { name });
  }
}
