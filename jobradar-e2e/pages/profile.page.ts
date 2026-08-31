import { type Locator } from '@playwright/test';
import { BasePage } from './base.page';
import { step } from '../utils/step';
import { Routes } from '../utils/routes';

export class ProfilePage extends BasePage {
  async open(): Promise<void> {
    await this.page.goto(Routes.profile);
  }

  heading(name: string): Locator {
    return this.page.getByRole('heading', { name });
  }

  seniorityInput(): Locator {
    return this.page.locator('input[name="seniority"]');
  }

  notesInput(): Locator {
    return this.page.locator('textarea[name="notes"]');
  }

  /** Saved notes as shown in the read-only view. */
  savedNotes(): Locator {
    return this.page.locator('.notes');
  }

  cvTrigger(): Locator {
    return this.page.getByRole('link', { name: 'Add CV' });
  }

  cvInput(): Locator {
    return this.page.locator('textarea[name="cv_text"]');
  }

  /** A detected-skill checkbox that appears after "Detect skills". */
  skillCheckbox(value: string): Locator {
    return this.page.locator(`input[name="skills"][value="${value}"]`);
  }

  saveButton(): Locator {
    return this.page.getByRole('button', { name: 'Save', exact: true });
  }

  saveScanButton(): Locator {
    return this.page.getByRole('button', { name: 'Save & Scan' });
  }

  @step('open CV editor')
  async openCvModal(): Promise<void> {
    await this.cvTrigger().click();
  }

  @step('detect skills')
  async detectSkills(): Promise<void> {
    await this.page.getByRole('button', { name: 'Detect skills' }).click();
  }

  @step('save profile')
  async save(): Promise<void> {
    await this.saveButton().click();
  }

  @step('edit profile')
  async edit(): Promise<void> {
    await this.page.getByRole('link', { name: 'Edit' }).click();
  }
}
