import { test, expect } from '../../fixtures/server';
import { ProfilePage } from '../../pages/profile.page';
import { Routes } from '../../utils/routes';

test.describe('Profile', () => {
  let profile: ProfilePage;
  test.beforeEach(async ({ page }) => { profile = new ProfilePage(page); });

  test('renders the edit form @smoke', async () => {
    await profile.open();
    await expect(profile.heading('Specialization')).toBeVisible();
    await expect(profile.cvTrigger()).toBeVisible();
  });

  test('exposes the save actions @regression', async () => {
    await profile.open();
    await expect(profile.saveButton()).toBeVisible();
    await expect(profile.saveScanButton()).toBeVisible();
  });

  test('detecting skills lists the technologies from the CV @regression', async () => {
    await profile.open();
    await profile.openCvModal();
    await profile.cvInput().fill('Experience with Playwright, pytest and Selenium');
    await profile.detectSkills();
    await expect(profile.skillCheckbox('Playwright')).toBeChecked();
    await expect(profile.skillCheckbox('pytest')).toBeChecked();
  });

  test('saving the profile persists it across reloads @regression', async () => {
    await profile.open();
    await profile.seniorityInput().fill('Senior');
    await profile.notesInput().fill('QA automation focus');
    await profile.save();
    await expect(profile.savedNotes()).toContainText('QA automation focus');

    await profile.open();
    await expect(profile.savedNotes()).toContainText('QA automation focus');
  });

  test('editing a saved profile updates it @regression', async () => {
    await profile.open();
    await profile.notesInput().fill('first note');
    await profile.save();
    await expect(profile.savedNotes()).toContainText('first note');

    await profile.edit();
    await profile.notesInput().fill('second note');
    await profile.save();
    await expect(profile.savedNotes()).toContainText('second note');
  });

  test('detecting skills fills in the seniority from the CV @regression', async () => {
    await profile.open();
    await profile.openCvModal();
    await profile.cvInput().fill('Senior QA Automation Engineer, 6 years in test automation');
    await profile.detectSkills();
    await expect(profile.seniorityInput()).toHaveValue('Senior');
  });

  test('a lowercase skill in the CV maps to its canonical spelling @regression', async () => {
    await profile.open();
    await profile.openCvModal();
    await profile.cvInput().fill('experience with playwright and pytest');
    await profile.detectSkills();
    await expect(profile.skillCheckbox('Playwright')).toBeChecked();
  });

  test('detecting skills previews without saving the profile @regression', async () => {
    await profile.open();
    await profile.openCvModal();
    await profile.cvInput().fill('Playwright, pytest');
    await profile.detectSkills();
    await expect(profile.skillCheckbox('Playwright')).toBeChecked();

    await profile.open(); // fresh visit — nothing was saved
    await expect(profile.skillCheckbox('Playwright')).toHaveCount(0);
  });

  test('an extra skill is saved even though it is not in the CV @regression', async ({ page }) => {
    await profile.open();
    await page.locator('input[name="extra"]').fill('Scrum');
    await profile.save();
    await page.goto('/profile?edit=1');
    await expect(page.locator('input[name="extra"]')).toHaveValue('Scrum');
  });

  test('the selected role persists across a save @regression', async ({ page }) => {
    await profile.open();
    const other = page.locator('input[name="role"]:not(:checked)').first();
    const value = await other.getAttribute('value');
    await other.check();
    await profile.save();
    await page.goto('/profile?edit=1');
    await expect(page.locator(`input[name="role"][value="${value}"]`)).toBeChecked();
  });

  // LLM access moved to the Settings page (Profile now holds only the candidate).
  test('the LLM config is saved in settings @regression', async ({ page }) => {
    await page.goto(Routes.settings);
    await page.locator('select[name="llm_provider"]').selectOption('openai');
    await page.locator('input[name="api_key"]').fill('sk-test-123');
    await page.getByRole('button', { name: 'Save', exact: true }).click();
    await page.goto(`${Routes.settings}?edit=1`);
    await expect(page.locator('select[name="llm_provider"]')).toHaveValue('openai');
    await expect(page.locator('input[name="api_key"]')).toHaveValue('sk-test-123');
  });
});
