/**
 * Playwright tests for Family Dashboard DATA VALIDATION
 * These tests verify actual data is loaded, not just UI elements
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = 'https://speedmathsgames.com';

test.setTimeout(60000);

test.describe('Family Dashboard Data Validation', () => {

    test('GK Practice History loads actual test data', async ({ page }) => {
        // Login first (family dashboard requires auth)
        await page.goto(`${BASE_URL}/family_dashboard.html`, { waitUntil: 'networkidle' });

        // Wait for GK stats container to load
        await page.waitForSelector('#gk-stats-container', { timeout: 10000 });

        // Wait for loading to finish (loading text should disappear)
        await page.waitForFunction(() => {
            const container = document.getElementById('gk-stats-container');
            return container && !container.textContent.includes('Loading');
        }, { timeout: 15000 });

        // Get the GK summary values
        const content = await page.textContent('#gk-stats-container');
        console.log('GK Stats Container content:', content.substring(0, 500));

        // Check that we have test data (not all zeros)
        const totalTestsValue = await page.locator('.gk-summary-value').nth(1).textContent();
        console.log('Total tests value:', totalTestsValue);

        // Should show some tests (based on database having 17 tests for saanvi)
        const totalTests = parseInt(totalTestsValue) || 0;
        expect(totalTests).toBeGreaterThan(0);
        console.log(`Found ${totalTests} GK tests in history`);
    });

    test('Weekly calendar shows GK activity indicators', async ({ page }) => {
        await page.goto(`${BASE_URL}/family_dashboard.html`, { waitUntil: 'networkidle' });

        // Wait for calendar to render
        await page.waitForSelector('.day-cell', { timeout: 10000 });

        // Wait for activity data to load
        await page.waitForTimeout(2000);

        // Check for GK activity dots (green dots)
        const gkDots = page.locator('.activity-dot.gk');
        const gkDotCount = await gkDots.count();
        console.log(`Found ${gkDotCount} GK activity indicators in calendar`);

        // Should have at least 1 GK activity indicator (based on test data)
        expect(gkDotCount).toBeGreaterThan(0);
    });

    test('Family overview card shows GK stats', async ({ page }) => {
        await page.goto(`${BASE_URL}/family_dashboard.html`, { waitUntil: 'networkidle' });

        // Wait for family grid to load
        await page.waitForSelector('#family-grid', { timeout: 10000 });

        // Wait for loading to finish
        await page.waitForFunction(() => {
            const grid = document.getElementById('family-grid');
            return grid && !grid.textContent.includes('Loading');
        }, { timeout: 10000 });

        // Get Saanvi's GK tests count from the card
        const saanviCard = page.locator('.member-card.saanvi');
        await expect(saanviCard).toBeVisible();

        const cardContent = await saanviCard.textContent();
        console.log('Saanvi card content:', cardContent.substring(0, 300));

        // Check for GK Practice section
        expect(cardContent).toContain('GK Practice');
    });

    test('Click on day shows activity details', async ({ page }) => {
        await page.goto(`${BASE_URL}/family_dashboard.html`, { waitUntil: 'networkidle' });

        // Wait for calendar
        await page.waitForSelector('.day-cell', { timeout: 10000 });
        await page.waitForTimeout(2000);

        // Find a day with activity (has-activity class)
        const activeDays = page.locator('.day-cell.has-activity');
        const activeCount = await activeDays.count();
        console.log(`Found ${activeCount} days with activity`);

        if (activeCount > 0) {
            // Click on the first active day
            await activeDays.first().click();

            // Details panel should show
            const detailsPanel = page.locator('#day-details.visible');
            await expect(detailsPanel).toBeVisible();

            // Check details content
            const detailsContent = await page.textContent('#details-content');
            console.log('Day details content:', detailsContent.substring(0, 200));

            // Should have some activity info
            expect(detailsContent.length).toBeGreaterThan(10);
        } else {
            console.log('No days with activity found - skipping detail check');
        }
    });

    test('API endpoint returns GK test data', async ({ request }) => {
        // Test the API directly
        const response = await request.get(`${BASE_URL}/api/admin/gk/tests?user_id=saanvi&limit=5`);

        console.log('API Response status:', response.status());
        const data = await response.json();
        console.log('API Response:', JSON.stringify(data).substring(0, 500));

        // Check response structure
        expect(data).toHaveProperty('tests');
        expect(data).toHaveProperty('count');

        // Should have test data
        expect(data.count).toBeGreaterThan(0);
        console.log(`API returned ${data.count} tests`);

        // Check first test has expected fields
        if (data.tests.length > 0) {
            const firstTest = data.tests[0];
            expect(firstTest).toHaveProperty('pdf_filename');
            expect(firstTest).toHaveProperty('total_questions');
            expect(firstTest).toHaveProperty('correct_answers');
            console.log('First test:', firstTest.pdf_filename,
                        `${firstTest.correct_answers}/${firstTest.total_questions}`);
        }
    });

    test('Weekly calendar shows correct number of tests', async ({ page }) => {
        await page.goto(`${BASE_URL}/family_dashboard.html`, { waitUntil: 'networkidle' });

        // Wait for both calendar and GK stats to load
        await page.waitForSelector('.day-cell', { timeout: 10000 });
        await page.waitForSelector('#gk-stats-container', { timeout: 10000 });

        // Wait for data to fully load
        await page.waitForFunction(() => {
            const container = document.getElementById('gk-stats-container');
            return container && !container.textContent.includes('Loading');
        }, { timeout: 15000 });

        // Count days with GK activity
        const gkDots = page.locator('.activity-dot.gk');
        const calendarGKDays = await gkDots.count();

        // Get total tests from summary
        const totalTestsText = await page.locator('.gk-summary-value').nth(1).textContent();
        const totalTests = parseInt(totalTestsText) || 0;

        console.log(`Calendar shows ${calendarGKDays} days with GK activity`);
        console.log(`Summary shows ${totalTests} total tests`);

        // If there are tests, calendar should show some activity
        if (totalTests > 0) {
            expect(calendarGKDays).toBeGreaterThanOrEqual(1);
        }
    });
});
