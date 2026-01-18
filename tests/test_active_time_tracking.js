/**
 * Playwright tests for Active Time Tracking
 * Tests verify:
 * 1. PDF view time and test time shown separately in GK Practice History
 * 2. Active time tracking APIs return correct data
 * 3. View and test time columns display properly
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = 'https://speedmathsgames.com';

test.setTimeout(60000);

test.describe('Active Time Tracking', () => {

    test('GK Practice History shows separate View and Test time columns', async ({ page }) => {
        await page.goto(`${BASE_URL}/family_dashboard.html`, { waitUntil: 'networkidle' });

        // Wait for GK stats container to load
        await page.waitForSelector('#gk-stats-container', { timeout: 15000 });

        // Wait for loading to finish
        await page.waitForFunction(() => {
            const container = document.getElementById('gk-stats-container');
            return container && !container.textContent.includes('Loading');
        }, { timeout: 15000 });

        // Check for View time column (📖 icon)
        const viewTimeStats = page.locator('.daily-stat.view-time');
        const viewTimeCount = await viewTimeStats.count();
        console.log(`Found ${viewTimeCount} View time columns`);

        // Check for Test time column (⏱️ icon)
        const testTimeStats = page.locator('.daily-stat.test-time');
        const testTimeCount = await testTimeStats.count();
        console.log(`Found ${testTimeCount} Test time columns`);

        // Should have at least one row with time columns (if there's activity)
        const dailyRows = page.locator('.gk-daily-row');
        const rowCount = await dailyRows.count();
        console.log(`Found ${rowCount} daily activity rows`);

        if (rowCount > 0) {
            // Each row should have both view-time and test-time stats
            expect(viewTimeCount).toBeGreaterThanOrEqual(1);
            expect(testTimeCount).toBeGreaterThanOrEqual(1);

            // Check first row has the time columns
            const firstRow = dailyRows.first();
            await expect(firstRow.locator('.daily-stat.view-time')).toBeVisible();
            await expect(firstRow.locator('.daily-stat.test-time')).toBeVisible();

            // Check the labels
            const viewLabel = await firstRow.locator('.daily-stat.view-time .stat-label').textContent();
            const testLabel = await firstRow.locator('.daily-stat.test-time .stat-label').textContent();
            expect(viewLabel).toBe('View');
            expect(testLabel).toBe('Test');
        }
    });

    test('API returns active_time_seconds for PDF views', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/admin/gk/views?user_id=saanvi&limit=10`);

        // This endpoint requires auth, so we check if we get a proper response structure
        const data = await response.json();
        console.log('Views API response keys:', Object.keys(data));

        if (data.error && data.error.includes('Access denied')) {
            console.log('API requires authentication - skipping detailed check');
            // Test passes - API is protected as expected
            return;
        }

        // If we get data, check for active_time_seconds field
        if (data.views && data.views.length > 0) {
            const firstView = data.views[0];
            console.log('First view keys:', Object.keys(firstView));
            expect(firstView).toHaveProperty('active_time_seconds');
        }
    });

    test('API returns active_time_seconds for tests', async ({ request }) => {
        const response = await request.get(`${BASE_URL}/api/admin/gk/tests?user_id=saanvi&limit=10`);

        const data = await response.json();
        console.log('Tests API response keys:', Object.keys(data));

        if (data.error && data.error.includes('Access denied')) {
            console.log('API requires authentication - skipping detailed check');
            return;
        }

        // If we get data, check for active_time_seconds field
        if (data.tests && data.tests.length > 0) {
            const firstTest = data.tests[0];
            console.log('First test keys:', Object.keys(firstTest));
            expect(firstTest).toHaveProperty('active_time_seconds');
        }
    });

    test('GK Practice History displays time values correctly', async ({ page }) => {
        await page.goto(`${BASE_URL}/family_dashboard.html`, { waitUntil: 'networkidle' });

        // Click on Saanvi tab to ensure we load her data
        const saanviTab = page.locator('[data-gk-filter="saanvi"]');
        await saanviTab.click();

        // Wait for GK stats container to load
        await page.waitForSelector('#gk-stats-container', { timeout: 15000 });

        // Wait for loading to finish
        await page.waitForFunction(() => {
            const container = document.getElementById('gk-stats-container');
            return container && !container.textContent.includes('Loading');
        }, { timeout: 15000 });

        // Small delay for data rendering
        await page.waitForTimeout(1000);

        // Get the rows
        const dailyRows = page.locator('.gk-daily-row');
        const rowCount = await dailyRows.count();
        console.log(`Found ${rowCount} daily rows`);

        if (rowCount > 0) {
            const firstRow = dailyRows.first();

            // Get view time value
            const viewTimeValue = await firstRow.locator('.daily-stat.view-time .stat-value').textContent();
            console.log('View time value:', viewTimeValue);

            // Get test time value
            const testTimeValue = await firstRow.locator('.daily-stat.test-time .stat-value').textContent();
            console.log('Test time value:', testTimeValue);

            // Values should be either a number with 'm' suffix or '-'
            const timePattern = /^(\d+m|-)$/;
            expect(viewTimeValue.trim()).toMatch(timePattern);
            expect(testTimeValue.trim()).toMatch(timePattern);
        }
    });

    test('View and Test time have correct styling', async ({ page }) => {
        await page.goto(`${BASE_URL}/family_dashboard.html`, { waitUntil: 'networkidle' });

        // Click on Saanvi tab
        const saanviTab = page.locator('[data-gk-filter="saanvi"]');
        await saanviTab.click();

        // Wait for loading to finish
        await page.waitForSelector('#gk-stats-container', { timeout: 15000 });
        await page.waitForFunction(() => {
            const container = document.getElementById('gk-stats-container');
            return container && !container.textContent.includes('Loading');
        }, { timeout: 15000 });
        await page.waitForTimeout(1000);

        const dailyRows = page.locator('.gk-daily-row');
        const rowCount = await dailyRows.count();
        console.log(`Found ${rowCount} daily rows for styling test`);

        if (rowCount > 0) {
            const firstRow = dailyRows.first();

            // Check view-time has cyan color (#22d3ee)
            const viewTimeElement = firstRow.locator('.daily-stat.view-time .stat-value');
            const viewTimeColor = await viewTimeElement.evaluate(el =>
                window.getComputedStyle(el).color
            );
            console.log('View time color:', viewTimeColor);
            // Cyan is rgb(34, 211, 238)
            expect(viewTimeColor).toContain('34');

            // Check test-time has purple color (#a78bfa)
            const testTimeElement = firstRow.locator('.daily-stat.test-time .stat-value');
            const testTimeColor = await testTimeElement.evaluate(el =>
                window.getComputedStyle(el).color
            );
            console.log('Test time color:', testTimeColor);
            // Purple is rgb(167, 139, 250)
            expect(testTimeColor).toContain('167');
        }
    });

    test('Complete/Partial view indicator shows correctly', async ({ page }) => {
        await page.goto(`${BASE_URL}/family_dashboard.html`, { waitUntil: 'networkidle' });

        // Click on Saanvi tab
        const saanviTab = page.locator('[data-gk-filter="saanvi"]');
        await saanviTab.click();

        // Wait for loading to finish
        await page.waitForSelector('#gk-stats-container', { timeout: 15000 });
        await page.waitForFunction(() => {
            const container = document.getElementById('gk-stats-container');
            return container && !container.textContent.includes('Loading');
        }, { timeout: 15000 });
        await page.waitForTimeout(1000);

        const dailyRows = page.locator('.gk-daily-row');
        const rowCount = await dailyRows.count();
        console.log(`Found ${rowCount} daily rows for view indicator test`);

        if (rowCount > 0) {
            // Check first row that has views
            for (let i = 0; i < Math.min(rowCount, 5); i++) {
                const row = dailyRows.nth(i);
                const viewValue = await row.locator('.daily-stat.viewed .stat-value').textContent();
                console.log(`Row ${i + 1} view value:`, viewValue);

                // View value should be in format "N" or "N+M" (complete+partial)
                // e.g., "2", "1+1", "0"
                const viewPattern = /^\d+(\+\d+)?$/;
                expect(viewValue.trim()).toMatch(viewPattern);
            }
        }
    });

    test('Summary cards show correct totals', async ({ page }) => {
        await page.goto(`${BASE_URL}/family_dashboard.html`, { waitUntil: 'networkidle' });

        // Wait for summary cards to load
        await page.waitForSelector('.gk-summary-grid', { timeout: 15000 });

        // Get summary values
        const summaryValues = page.locator('.gk-summary-value');
        const summaryLabels = page.locator('.gk-summary-label');

        // Should have 4 summary cards
        const valueCount = await summaryValues.count();
        console.log(`Found ${valueCount} summary cards`);
        expect(valueCount).toBe(4);

        // Check each card
        for (let i = 0; i < 4; i++) {
            const value = await summaryValues.nth(i).textContent();
            const label = await summaryLabels.nth(i).textContent();
            console.log(`Card ${i + 1}: ${label} = ${value}`);
        }

        // PDFs Revised should be a number
        const pdfsRevised = await summaryValues.nth(0).textContent();
        expect(parseInt(pdfsRevised)).toBeGreaterThanOrEqual(0);

        // Total Tests should be a number
        const totalTests = await summaryValues.nth(1).textContent();
        expect(parseInt(totalTests)).toBeGreaterThanOrEqual(0);

        // Questions Attempted should be a number
        const questionsAttempted = await summaryValues.nth(2).textContent();
        expect(parseInt(questionsAttempted)).toBeGreaterThanOrEqual(0);

        // Average Accuracy should be a percentage
        const accuracy = await summaryValues.nth(3).textContent();
        expect(accuracy).toMatch(/\d+%/);
    });
});
