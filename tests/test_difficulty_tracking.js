/**
 * Playwright tests for Question Difficulty Tracking and Parent Activity Dashboard
 */

const { test, expect } = require('@playwright/test');

const BASE_URL = 'https://speedmathsgames.com';

// Increase timeout for all tests
test.setTimeout(60000);

test.describe('Question Difficulty Tracking System', () => {

    test.describe('API Endpoints', () => {

        test('Difficulty summary API returns correct structure', async ({ request }) => {
            const response = await request.get(`${BASE_URL}/api/assessment/difficulty/summary?user_id=daughter`);

            // Log response for debugging
            const text = await response.text();
            console.log('Response status:', response.status());
            console.log('Response body:', text.substring(0, 200));

            expect(response.status()).toBe(200);

            const data = JSON.parse(text);
            expect(data).toHaveProperty('easy');
            expect(data).toHaveProperty('medium');
            expect(data).toHaveProperty('difficult');
            expect(data).toHaveProperty('very_difficult');
            expect(data).toHaveProperty('total');

            // Total should equal sum
            expect(data.total).toBe(data.easy + data.medium + data.difficult + data.very_difficult);

            console.log('Difficulty Summary:', data);
        });

        test('New questions default to easy', async ({ request }) => {
            const response = await request.get(
                `${BASE_URL}/api/assessment/difficulty/tag?user_id=daughter&note_id=test_new_question_xyz`
            );

            expect(response.status()).toBe(200);
            const data = await response.json();

            expect(data.difficulty_tag).toBe('easy');
            console.log('New question tag:', data);
        });

        test('Questions by difficulty returns list', async ({ request }) => {
            const response = await request.get(
                `${BASE_URL}/api/assessment/difficulty/questions?user_id=daughter&tag=easy&limit=5`
            );

            expect(response.status()).toBe(200);
            const data = await response.json();

            expect(data).toHaveProperty('questions');
            expect(data).toHaveProperty('tag', 'easy');
            expect(Array.isArray(data.questions)).toBeTruthy();

            console.log(`Found ${data.count} easy questions`);
        });
    });

    test.describe('Parent Activity Dashboard', () => {

        test('Page loads and shows header', async ({ page }) => {
            await page.goto(`${BASE_URL}/parent_activity.html`, { waitUntil: 'domcontentloaded' });

            // Check header
            const header = page.locator('h1');
            await expect(header).toContainText('Parent Activity Dashboard');

            // Check selectors exist
            await expect(page.locator('#childSelector')).toBeVisible();
            await expect(page.locator('#datePicker')).toBeVisible();

            console.log('Parent activity page loaded successfully');
        });

        test('Difficulty distribution section exists', async ({ page }) => {
            await page.goto(`${BASE_URL}/parent_activity.html`, { waitUntil: 'domcontentloaded' });

            // Wait for content to load (with longer timeout)
            await page.waitForSelector('.difficulty-section', { timeout: 15000 });

            const section = page.locator('.difficulty-section');
            await expect(section).toBeVisible();

            console.log('Difficulty section found');
        });
    });

    test.describe('Assessment Page', () => {

        test('Page loads successfully', async ({ page }) => {
            await page.goto(`${BASE_URL}/assessment.html`, { waitUntil: 'domcontentloaded' });

            // Just verify it loads
            const title = await page.title();
            console.log('Assessment page title:', title);
            expect(title).toBeTruthy();
        });

        test('Difficulty badge CSS exists', async ({ page }) => {
            await page.goto(`${BASE_URL}/assessment.html`, { waitUntil: 'domcontentloaded' });

            // Check for difficulty badge styles
            const hasStyles = await page.evaluate(() => {
                const styles = Array.from(document.querySelectorAll('style'));
                return styles.some(s => s.textContent.includes('.difficulty-badge'));
            });

            expect(hasStyles).toBeTruthy();
            console.log('Difficulty badge CSS found');
        });

        test('Difficulty badge element exists in DOM', async ({ page }) => {
            await page.goto(`${BASE_URL}/assessment.html`, { waitUntil: 'domcontentloaded' });

            // Check HTML for difficulty badge
            const html = await page.content();
            const hasBadge = html.includes('id="q-difficulty"');

            expect(hasBadge).toBeTruthy();
            console.log('Difficulty badge element found in HTML');
        });
    });

    test.describe('Integration Tests', () => {

        test('Daughter has difficulty data', async ({ request }) => {
            const response = await request.get(`${BASE_URL}/api/assessment/difficulty/summary?user_id=daughter`);
            const data = await response.json();

            console.log('Daughter difficulty data:', data);

            // Should have some data
            expect(data.total).toBeGreaterThan(0);

            // Based on backfill: 3 easy, 5 very_difficult
            expect(data.easy).toBe(3);
            expect(data.very_difficult).toBe(5);
        });

        test('Very difficult questions exist', async ({ request }) => {
            const response = await request.get(
                `${BASE_URL}/api/assessment/difficulty/questions?user_id=daughter&tag=very_difficult&limit=10`
            );
            const data = await response.json();

            console.log(`Found ${data.count} very difficult questions`);
            expect(data.count).toBe(5);

            // Check structure of returned questions
            if (data.questions.length > 0) {
                const q = data.questions[0];
                expect(q).toHaveProperty('anki_note_id');
                expect(q).toHaveProperty('difficulty_tag', 'very_difficult');
                expect(q).toHaveProperty('accuracy');
            }
        });
    });
});
