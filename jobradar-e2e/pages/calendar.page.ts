import { type Locator } from '@playwright/test';
import { BasePage } from './base.page';
import { Routes } from '../utils/routes';

export class CalendarPage extends BasePage {
  async openMonth(year: number, month: number): Promise<void> {
    await this.page.goto(`${Routes.calendar}?year=${year}&month=${month}`);
  }

  title(): Locator {
    return this.page.locator('.cal-title');
  }

  days(): Locator {
    return this.page.getByTestId('calendar-day');
  }
}
