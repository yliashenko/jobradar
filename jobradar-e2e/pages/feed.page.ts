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

  // ---- pager -------------------------------------------------------------

  pager(): Locator {
    return this.page.locator(sel.pager);
  }

  counts(): Locator {
    return this.page.locator(sel.counts);
  }

  @step('go to the next page')
  async nextPage(): Promise<void> {
    await this.page.locator(sel.pagerNext).click();
  }

  @step('go to the previous page')
  async prevPage(): Promise<void> {
    await this.page.locator(sel.pagerPrev).click();
  }

  /** The hashes rendered on the current page, for overlap checks between pages. */
  async cardHashes(): Promise<string[]> {
    return this.cards().evaluateAll((els) =>
      els.map((e) => e.getAttribute('data-hash') || ''),
    );
  }

  // ---- tag picker popup --------------------------------------------------
  // Its body is fetched on first open, so every locator below only resolves
  // after openTagPicker().

  tagPanel(): Locator {
    return this.page.locator(sel.tagPanel);
  }

  tagPickRows(): Locator {
    return this.page.locator(sel.tagPickRow);
  }

  /** Rows the popup's own search left visible (it hides, never removes). */
  visibleTagPickRows(): Locator {
    return this.page.locator(`${sel.tagPickRow}:visible`);
  }

  @step('open the tag picker')
  async openTagPicker(): Promise<void> {
    await this.page.locator(`${sel.tagPicker} > summary`).click();
    await this.tagPanel().waitFor();
  }

  @step('search inside the tag picker')
  async searchTagPicker(text: string): Promise<void> {
    await this.page.locator(sel.tagPickSearch).fill(text);
  }

  @step('apply a tag from the picker')
  async applyTagFromPicker(term: string): Promise<void> {
    await this.page.locator(sel.tagPickBox(term)).check();
    await this.page.locator(sel.tagPickApply).click();
  }
}
