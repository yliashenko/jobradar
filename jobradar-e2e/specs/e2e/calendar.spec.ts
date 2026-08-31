import { test, expect } from '../../fixtures/server';
import { CalendarPage } from '../../pages/calendar.page';

const now = new Date();
const YEAR = now.getUTCFullYear();
const MONTH = now.getUTCMonth() + 1;

test.describe('Calendar', () => {
  test('renders a month grid @smoke', async ({ page }) => {
    const cal = new CalendarPage(page);

    await cal.openMonth(YEAR, MONTH);
    await expect(cal.title()).toBeVisible();
  });

  test('shows today\'s new + applied activity in the current month @regression', async ({ page }) => {
    const cal = new CalendarPage(page);

    await cal.openMonth(YEAR, MONTH);

    const today = new Date().toISOString().slice(0, 10);
    await expect(page.locator(`[data-testid="calendar-day"][data-day="${today}"].cal-new`)).toBeVisible();
    await expect(page.locator(`[data-testid="calendar-day"][data-day="${today}"].cal-applied`)).toBeVisible();
  });

  test('an archived application still counts on the calendar @regression', async ({ page }) => {
    const d = new Date(Date.now() - 5 * 86400000);
    const dstr = d.toISOString().slice(0, 10);
    const cal = new CalendarPage(page);

    await cal.openMonth(d.getUTCFullYear(), d.getUTCMonth() + 1);
    await expect(page.locator(`[data-testid="calendar-day"][data-day="${dstr}"].cal-applied`)).toBeVisible();
  });

  test('a month with no activity has no day markers @regression', async ({ page }) => {
    const cal = new CalendarPage(page);

    await cal.openMonth(2000, 1);
    await expect(cal.days()).toHaveCount(0);
  });
});
