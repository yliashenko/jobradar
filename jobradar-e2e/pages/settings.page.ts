import { type Locator } from '@playwright/test';
import { BasePage } from './base.page';
import { step } from '../utils/step';
import { Routes } from '../utils/routes';

/** Settings edit form: LLM access + Telegram (collapsible sections) and the
 *  reminder-style auto-scan schedule. Selectors are name/testid based, matching
 *  the rest of the suite. */
export class SettingsPage extends BasePage {
  async openEdit(): Promise<void> {
    await this.page.goto(`${Routes.settings}?edit=1`);
  }

  // --- Auto-scan schedule ---
  autoScanToggle(): Locator {
    return this.page.locator('input[name="schedule_enabled"]');
  }
  repeatSelect(): Locator {
    return this.page.locator('select[name="schedule_repeat"]');
  }
  weekdaySelect(): Locator {
    return this.page.locator('select[name="schedule_weekday"]');
  }
  monthdaySelect(): Locator {
    return this.page.locator('select[name="schedule_monthday"]');
  }
  hourSelect(): Locator {
    return this.page.locator('select[name="schedule_hour"]');
  }

  // --- Collapsible sections ---
  section(name: 'llm' | 'telegram'): Locator {
    return this.page.locator(`[data-testid="settings-${name}"]`);
  }
  sectionSummary(name: 'llm' | 'telegram'): Locator {
    return this.section(name).locator('summary');
  }
  apiKeyInput(): Locator {
    return this.page.locator('input[name="api_key"]');
  }
  botTokenInput(): Locator {
    return this.page.locator('input[name="telegram_bot_token"]');
  }

  saveButton(): Locator {
    return this.page.getByRole('button', { name: 'Save', exact: true });
  }

  @step('save settings')
  async save(): Promise<void> {
    await this.saveButton().click();
  }

  @step('expand a collapsed section')
  async expand(name: 'llm' | 'telegram'): Promise<void> {
    await this.sectionSummary(name).click();
  }
}
