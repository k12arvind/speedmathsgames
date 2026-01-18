/**
 * Playwright tests using existing Chrome profile with authentication
 * This allows testing with the user's logged-in session
 */

const { chromium } = require('playwright');

const BASE_URL = 'https://speedmathsgames.com';

// Path to Chrome profile on macOS
const CHROME_USER_DATA_DIR = '/Users/arvind/Library/Application Support/Google/Chrome';

async function runTests() {
    console.log('🚀 Starting tests with Chrome profile...\n');

    // Launch Chrome with existing profile
    const browser = await chromium.launchPersistentContext(CHROME_USER_DATA_DIR, {
        channel: 'chrome',
        headless: false,  // Need to be visible to use existing session
        args: [
            '--disable-blink-features=AutomationControlled',
        ],
        timeout: 60000,
    });

    const page = await browser.newPage();
    let passed = 0;
    let failed = 0;

    try {
        // Test 1: Load family dashboard with authentication
        console.log('📋 Test 1: Loading Family Dashboard with auth...');
        await page.goto(`${BASE_URL}/family_dashboard.html`, { waitUntil: 'networkidle', timeout: 30000 });

        // Wait for GK stats to load
        await page.waitForSelector('#gk-stats-container', { timeout: 15000 });
        await page.waitForFunction(() => {
            const container = document.getElementById('gk-stats-container');
            return container && !container.textContent.includes('Loading');
        }, { timeout: 15000 });

        // Check summary cards have data
        const pdfsRevised = await page.locator('.gk-summary-value').nth(0).textContent();
        const totalTests = await page.locator('.gk-summary-value').nth(1).textContent();
        console.log(`   PDFs Revised: ${pdfsRevised}, Total Tests: ${totalTests}`);

        if (parseInt(pdfsRevised) > 0 || parseInt(totalTests) > 0) {
            console.log('   ✅ PASSED: Dashboard loaded with data\n');
            passed++;
        } else {
            console.log('   ❌ FAILED: No data loaded\n');
            failed++;
        }

        // Test 2: Check separate View and Test time columns
        console.log('📋 Test 2: Checking separate View/Test time columns...');
        const dailyRows = page.locator('.gk-daily-row');
        const rowCount = await dailyRows.count();
        console.log(`   Found ${rowCount} daily activity rows`);

        if (rowCount > 0) {
            const firstRow = dailyRows.first();

            // Check for view-time column
            const viewTimeExists = await firstRow.locator('.daily-stat.view-time').count() > 0;
            const testTimeExists = await firstRow.locator('.daily-stat.test-time').count() > 0;

            if (viewTimeExists && testTimeExists) {
                const viewTimeValue = await firstRow.locator('.daily-stat.view-time .stat-value').textContent();
                const testTimeValue = await firstRow.locator('.daily-stat.test-time .stat-value').textContent();
                console.log(`   View Time: ${viewTimeValue.trim()}, Test Time: ${testTimeValue.trim()}`);
                console.log('   ✅ PASSED: Separate View and Test time columns exist\n');
                passed++;
            } else {
                console.log(`   ❌ FAILED: view-time=${viewTimeExists}, test-time=${testTimeExists}`);
                console.log('   You may need to hard refresh (Cmd+Shift+R) to clear cache\n');
                failed++;
            }
        } else {
            console.log('   ⚠️ SKIPPED: No daily rows found\n');
        }

        // Test 3: Verify View indicator shows complete+partial format
        console.log('📋 Test 3: Checking complete/partial view indicator...');
        if (rowCount > 0) {
            const firstRow = dailyRows.first();
            const viewValue = await firstRow.locator('.daily-stat.viewed .stat-value').textContent();
            console.log(`   View indicator value: "${viewValue.trim()}"`);

            // Should match pattern like "2+1" or "3" or "0"
            const pattern = /^\d+(\+\d+)?$/;
            if (pattern.test(viewValue.trim())) {
                console.log('   ✅ PASSED: View indicator format is correct\n');
                passed++;
            } else {
                console.log('   ❌ FAILED: Unexpected format\n');
                failed++;
            }
        }

        // Test 4: Test API with authentication
        console.log('📋 Test 4: Testing API with authentication...');
        const apiResponse = await page.evaluate(async () => {
            const response = await fetch('/api/admin/gk/tests?user_id=saanvi&limit=5');
            return response.json();
        });

        console.log(`   API response keys: ${Object.keys(apiResponse).join(', ')}`);

        if (apiResponse.tests && apiResponse.tests.length > 0) {
            const firstTest = apiResponse.tests[0];
            console.log(`   First test: ${firstTest.pdf_filename}`);
            console.log(`   Has active_time_seconds: ${firstTest.hasOwnProperty('active_time_seconds')}`);
            console.log(`   active_time_seconds value: ${firstTest.active_time_seconds}`);

            if (firstTest.hasOwnProperty('active_time_seconds')) {
                console.log('   ✅ PASSED: API returns active_time_seconds\n');
                passed++;
            } else {
                console.log('   ❌ FAILED: active_time_seconds not in response\n');
                failed++;
            }
        } else if (apiResponse.error) {
            console.log(`   ❌ FAILED: API error - ${apiResponse.error}\n`);
            failed++;
        }

        // Test 5: Test Views API
        console.log('📋 Test 5: Testing Views API...');
        const viewsResponse = await page.evaluate(async () => {
            const response = await fetch('/api/admin/gk/views?user_id=saanvi&limit=10');
            return response.json();
        });

        console.log(`   Views API response: complete=${viewsResponse.complete_count}, partial=${viewsResponse.partial_count}`);

        if (viewsResponse.views && viewsResponse.views.length > 0) {
            const firstView = viewsResponse.views[0];
            console.log(`   First view: ${firstView.pdf_id}`);
            console.log(`   Has active_time_seconds: ${firstView.hasOwnProperty('active_time_seconds')}`);

            if (viewsResponse.hasOwnProperty('complete_count') && viewsResponse.hasOwnProperty('partial_count')) {
                console.log('   ✅ PASSED: Views API returns complete/partial counts\n');
                passed++;
            } else {
                console.log('   ❌ FAILED: Missing complete/partial counts\n');
                failed++;
            }
        } else if (viewsResponse.error) {
            console.log(`   ❌ FAILED: API error - ${viewsResponse.error}\n`);
            failed++;
        }

        // Take a screenshot for verification
        await page.screenshot({ path: 'test-results/family_dashboard_with_auth.png', fullPage: true });
        console.log('📸 Screenshot saved to test-results/family_dashboard_with_auth.png\n');

    } catch (error) {
        console.error('❌ Test error:', error.message);
        failed++;
    } finally {
        await browser.close();
    }

    // Summary
    console.log('═══════════════════════════════════════');
    console.log(`📊 Test Results: ${passed} passed, ${failed} failed`);
    console.log('═══════════════════════════════════════');

    return failed === 0;
}

// Run tests
runTests()
    .then(success => process.exit(success ? 0 : 1))
    .catch(error => {
        console.error('Fatal error:', error);
        process.exit(1);
    });
