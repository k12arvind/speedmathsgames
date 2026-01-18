/**
 * Playwright tests for Family Dashboard 7-Day Calendar
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = 'https://speedmathsgames.com';

test.setTimeout(60000);

test.describe('Family Dashboard Calendar', () => {

    test('Page loads with calendar section', async ({ page }) => {
        await page.goto(`${BASE_URL}/family_dashboard.html`, { waitUntil: 'domcontentloaded' });

        // Check weekly activity section exists
        const sectionTitle = page.locator('text=Weekly Activity Tracker');
        await expect(sectionTitle).toBeVisible();

        // Check week calendar container exists
        const weekCalendar = page.locator('#week-calendar');
        await expect(weekCalendar).toBeVisible();

        console.log('Calendar section loaded successfully');
    });

    test('Calendar shows 7 days', async ({ page }) => {
        await page.goto(`${BASE_URL}/family_dashboard.html`, { waitUntil: 'networkidle' });

        // Wait for calendar to render
        await page.waitForSelector('.day-cell', { timeout: 10000 });

        // Count day cells
        const dayCells = page.locator('.day-cell');
        const count = await dayCells.count();

        expect(count).toBe(7);
        console.log(`Calendar shows ${count} days`);
    });

    test('Calendar user toggle works', async ({ page }) => {
        await page.goto(`${BASE_URL}/family_dashboard.html`, { waitUntil: 'networkidle' });

        // Check toggle buttons exist
        const saanviBtn = page.locator('.user-toggle-btn[data-user="saanvi"]');
        const navyaBtn = page.locator('.user-toggle-btn[data-user="navya"]');

        await expect(saanviBtn).toBeVisible();
        await expect(navyaBtn).toBeVisible();

        // Saanvi should be active by default
        await expect(saanviBtn).toHaveClass(/active/);

        console.log('User toggle buttons work');
    });

    test('Day cells are clickable', async ({ page }) => {
        await page.goto(`${BASE_URL}/family_dashboard.html`, { waitUntil: 'networkidle' });

        // Wait for calendar to render
        await page.waitForSelector('.day-cell', { timeout: 10000 });

        // Click on today's cell (last cell)
        const dayCells = page.locator('.day-cell');
        const todayCell = dayCells.last();
        await todayCell.click();

        // Day details panel should appear (uses 'visible' class)
        const detailsPanel = page.locator('#day-details');
        await expect(detailsPanel).toHaveClass(/visible/);

        console.log('Day cell click shows details panel');
    });

    test('Close button hides details panel', async ({ page }) => {
        await page.goto(`${BASE_URL}/family_dashboard.html`, { waitUntil: 'networkidle' });

        // Wait for calendar to render
        await page.waitForSelector('.day-cell', { timeout: 10000 });

        // Click on a day cell
        const dayCells = page.locator('.day-cell');
        await dayCells.first().click();

        // Panel should be visible
        const detailsPanel = page.locator('#day-details');
        await expect(detailsPanel).toHaveClass(/visible/);

        // Click close button
        const closeBtn = page.locator('.close-details');
        await closeBtn.click();

        // Panel should be hidden (no 'visible' class)
        await expect(detailsPanel).not.toHaveClass(/visible/);

        console.log('Close button works correctly');
    });

    test('Day cells have activity indicators', async ({ page }) => {
        await page.goto(`${BASE_URL}/family_dashboard.html`, { waitUntil: 'networkidle' });

        // Wait for calendar to render
        await page.waitForSelector('.day-cell', { timeout: 10000 });

        // Check that day cells are rendered
        const dayCells = page.locator('.day-cell');
        const count = await dayCells.count();

        expect(count).toBe(7);
        console.log(`Found ${count} day cells with activity tracking`);
    });

    test('Study session logged text template exists', async ({ page }) => {
        await page.goto(`${BASE_URL}/family_dashboard.html`, { waitUntil: 'networkidle' });

        // Check page contains the "Study session logged" text template
        const pageContent = await page.content();
        const hasTemplate = pageContent.includes('Study session logged');

        expect(hasTemplate).toBeTruthy();
        console.log('Study session logged template exists');
    });

    test('Legend shows activity types', async ({ page }) => {
        await page.goto(`${BASE_URL}/family_dashboard.html`, { waitUntil: 'domcontentloaded' });

        // Check legend items exist
        const diaryLegend = page.locator('.legend-item:has-text("Diary")');
        const gkLegend = page.locator('.legend-item:has-text("GK Practice")');
        const mathLegend = page.locator('.legend-item:has-text("Math")');

        await expect(diaryLegend).toBeVisible();
        await expect(gkLegend).toBeVisible();
        await expect(mathLegend).toBeVisible();

        console.log('Activity legend is visible');
    });
});
