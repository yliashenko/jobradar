import { test, expect } from '../../fixtures/server';
import { SettingsPage } from '../../pages/settings.page';

test.describe('Auto-scan schedule', () => {
  let settings: SettingsPage;
  test.beforeEach(async ({ page }) => { settings = new SettingsPage(page); });

  test('saving a schedule persists it across reloads @smoke', async () => {
    await settings.openEdit();
    await settings.autoScanToggle().check();
    await settings.repeatSelect().selectOption('weekly');
    await settings.weekdaySelect().selectOption('2'); // Wednesday
    await settings.hourSelect().selectOption('10');
    await settings.save();

    await settings.openEdit();
    await expect(settings.autoScanToggle()).toBeChecked();
    await expect(settings.repeatSelect()).toHaveValue('weekly');
    await expect(settings.weekdaySelect()).toHaveValue('2');
    await expect(settings.hourSelect()).toHaveValue('10');
  });

  test('the daily default hides the weekday and day-of-month pickers @regression', async () => {
    await settings.openEdit();
    await expect(settings.repeatSelect()).toHaveValue('daily');
    await expect(settings.weekdaySelect()).toBeHidden();
    await expect(settings.monthdaySelect()).toBeHidden();
  });

  test('a weekly repeat reveals the weekday picker @regression', async () => {
    await settings.openEdit();
    await settings.repeatSelect().selectOption('weekly');
    await expect(settings.weekdaySelect()).toBeVisible();
    await expect(settings.monthdaySelect()).toBeHidden();
  });

  test('a monthly repeat reveals the day-of-month picker @regression', async () => {
    await settings.openEdit();
    await settings.repeatSelect().selectOption('monthly');
    await expect(settings.monthdaySelect()).toBeVisible();
    await expect(settings.weekdaySelect()).toBeHidden();
  });
});

test.describe('Settings sections', () => {
  let settings: SettingsPage;
  test.beforeEach(async ({ page }) => { settings = new SettingsPage(page); });

  test('an unconfigured LLM section starts open @smoke', async () => {
    await settings.openEdit();
    await expect(settings.apiKeyInput()).toBeVisible();
  });

  test('an unconfigured Telegram section starts open @regression', async () => {
    await settings.openEdit();
    await expect(settings.botTokenInput()).toBeVisible();
  });

  test('a configured LLM section starts collapsed @regression', async ({ page, api }) => {
    await api.saveSettings({ api_key: 'sk-ant-e2e', llm_provider: 'anthropic' });
    await settings.openEdit();
    await expect(settings.apiKeyInput()).toBeHidden();
    await expect(page.getByText('key set')).toBeVisible();
  });

  test('a configured Telegram section starts collapsed @regression', async ({ page, api }) => {
    await api.saveSettings({ telegram_bot_token: '123456789:AA', telegram_enabled: 'on' });
    await settings.openEdit();
    await expect(settings.botTokenInput()).toBeHidden();
    await expect(page.getByText('bot token set')).toBeVisible();
  });

  test('expanding a collapsed LLM section reveals its fields @regression', async ({ api }) => {
    await api.saveSettings({ api_key: 'sk-ant-e2e', llm_provider: 'anthropic' });
    await settings.openEdit();
    await settings.expand('llm');
    await expect(settings.apiKeyInput()).toBeVisible();
  });
});
