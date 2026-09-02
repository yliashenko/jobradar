import { type Locator } from '@playwright/test';
import { BasePage } from './base.page';
import { step } from '../utils/step';
import { Routes } from '../utils/routes';
import { sel } from '../utils/selectors';

export class FeedPage extends BasePage {
  tag(term: string): Locator {
    return this.page.locator(sel.tag(term)).first();
  }

  scoring(hash: string){
    return this.page.locator(`${hash} ${sel.scoreOpen}`).first();
  }

  statusButton(hash: string, status: string): Locator {
    return this.card(hash).locator(sel.statusBtn(status));
  }

  @step('open feed')
  async open(query = ''): Promise<void> {
    await this.page.goto(Routes.feed + query);
  }

  @step('open feed on status')
  async openFeedOnStatus(status: string): Promise<void> {
    await this.open(`?status=${status}`);
  }

  @step('apply filters')
  async filter(params: Record<string, string>): Promise<void> {
    await this.page.goto(`${Routes.feed}?${new URLSearchParams(params).toString()}`);
  }

  @step('filter by tag')
  async filterByTag(term: string): Promise<void> {
    await this.tag(term).click();
  }

  @step('change card status')
  async setStatus(hash: string, status: string): Promise<void> {
    await this.statusButton(hash, status).click();
  }

  @step('open company')
  async openCompany(name: string): Promise<void> {
    await this.page.locator('a.co').filter({ hasText: name }).first().click();
  }
}
