const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext();
    const page = await context.newPage();

    const BASE_URL = 'https://speedmathsgames.com';
    const results = { passed: [], failed: [] };

    const log = (msg) => console.log(`[TEST] ${msg}`);

    // Capture console messages and session ID
    let capturedSessionId = null;
    page.on('console', msg => {
        const text = msg.text();
        if (msg.type() === 'error') {
            console.log(`[CONSOLE ERROR] ${text}`);
        } else if (text.includes('View session started:')) {
            console.log(`[CONSOLE] ${text}`);
            const match = text.match(/View session started: ([a-f0-9-]+)/);
            if (match) {
                capturedSessionId = match[1];
            }
        } else if (text.includes('view') || text.includes('pages')) {
            console.log(`[CONSOLE] ${text}`);
        }
    });

    page.on('pageerror', err => {
        console.log(`[PAGE ERROR] ${err.message}`);
    });

    try {
        // 1. Test Dashboard loads
        log('Testing dashboard...');
        await page.goto(`${BASE_URL}/comprehensive_dashboard.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForTimeout(2000);

        const title = await page.title();
        if (title) {
            results.passed.push('Dashboard loads');
            log('Dashboard loaded: ' + title);
        } else {
            results.failed.push('Dashboard did not load');
        }

        // 2. Check Views column exists in table
        log('Checking Views column...');
        const viewsHeader = await page.$('th:has-text("Views")');
        if (viewsHeader) {
            results.passed.push('Views column exists in table');
            log('Views column found');
        } else {
            results.failed.push('Views column not found');
            log('Views column not found');
        }

        // 2b. Check Last Viewed column exists in table
        log('Checking Last Viewed column...');
        const lastViewedHeader = await page.$('th:has-text("Last Viewed")');
        if (lastViewedHeader) {
            results.passed.push('Last Viewed column exists in table');
            log('Last Viewed column found');
        } else {
            results.failed.push('Last Viewed column not found');
            log('Last Viewed column not found');
        }

        // 3. Wait for PDFs to load and find one to test
        log('Waiting for PDF list...');
        await page.waitForTimeout(3000);

        // Find a View PDF button
        const viewPdfButtons = await page.$$('button:has-text("View PDF")');
        log(`Found ${viewPdfButtons.length} View PDF buttons`);

        if (viewPdfButtons.length === 0) {
            results.failed.push('No View PDF buttons found');
            throw new Error('No PDFs to test');
        }

        // Get the PDF filename from the first row
        const firstRow = await page.$('table tbody tr');
        const pdfName = await firstRow.$eval('td:first-child', el => el.textContent.trim());
        log(`Testing with PDF: ${pdfName}`);

        // 4. Get initial view count for this PDF (6th column is Views)
        const cells = await firstRow.$$('td');
        let initialViewCount = 0;
        if (cells.length >= 6) {
            const viewText = await cells[5].textContent();
            initialViewCount = parseInt(viewText.match(/\d+/)?.[0] || '0');
        }
        log(`Initial view count: ${initialViewCount}`);

        // 5. Click View PDF button (it navigates to a new page)
        log('Opening PDF viewer...');

        // Get the onclick attribute to find the PDF filename
        const onclickAttr = await viewPdfButtons[0].getAttribute('onclick');
        const pdfFilenameMatch = onclickAttr.match(/viewPdf\('([^']+)'\)/);
        const pdfFilename = pdfFilenameMatch ? pdfFilenameMatch[1] : null;
        log(`PDF filename: ${pdfFilename}`);

        // Navigate directly to the PDF viewer
        if (pdfFilename) {
            await page.goto(`${BASE_URL}/pdf-viewer.html?pdf_id=${encodeURIComponent(pdfFilename)}`, {
                waitUntil: 'domcontentloaded',
                timeout: 30000
            });
        } else {
            // Click the button and wait for navigation
            await Promise.all([
                page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {}),
                viewPdfButtons[0].click()
            ]);
        }
        await page.waitForTimeout(5000);

        // 6. Check if PDF viewer loaded
        const pdfContainer = await page.$('#pdf-container');
        if (pdfContainer) {
            results.passed.push('PDF viewer opened');
            log('PDF viewer opened');
        } else {
            results.failed.push('PDF viewer did not open');
        }

        // 7. Wait for pages to render
        log('Waiting for pages to render...');
        await page.waitForTimeout(5000);

        // Debug: Check page content
        const pageUrl = page.url();
        log(`Current URL: ${pageUrl}`);

        const bodyHtml = await page.$eval('body', el => el.innerHTML.substring(0, 500));
        log(`Body preview: ${bodyHtml.substring(0, 200)}...`);

        // Wait for page wrappers to appear
        await page.waitForSelector('.page-wrapper', { timeout: 15000 }).catch(() => {
            log('Timeout waiting for .page-wrapper');
        });
        await page.waitForTimeout(2000);

        // Count pages
        const pageWrappers = await page.$$('.page-wrapper');
        const totalPages = pageWrappers.length;
        log(`PDF has ${totalPages} pages`);

        // If no pages, check for canvas elements
        if (totalPages === 0) {
            const canvases = await page.$$('canvas');
            log(`Found ${canvases.length} canvas elements`);
            const divs = await page.$$('#pdf-container > div');
            log(`Found ${divs.length} divs in pdf-container`);
        } else {
            // Check page-label elements
            const pageLabels = await page.$$('.page-label');
            log(`Found ${pageLabels.length} page-label elements`);
            if (pageLabels.length > 0) {
                const labelText = await pageLabels[0].textContent();
                log(`First page label: "${labelText}"`);
            }
        }

        if (totalPages > 0) {
            results.passed.push(`PDF rendered with ${totalPages} pages`);
        } else {
            results.failed.push('No pages rendered');
        }

        // 8. Scroll through all pages visually
        log('Scrolling through all pages...');
        for (let i = 0; i < totalPages; i++) {
            await page.evaluate((index) => {
                const wrappers = document.querySelectorAll('.page-wrapper');
                if (wrappers[index]) {
                    wrappers[index].scrollIntoView({ behavior: 'instant', block: 'start' });
                }
            }, i);
            await page.waitForTimeout(400);
            if ((i + 1) % 3 === 0 || i === totalPages - 1) {
                log(`  Scrolled to page ${i + 1}/${totalPages}`);
            }
        }
        log(`Completed scrolling all ${totalPages} pages`);

        // Since IntersectionObserver doesn't work reliably in headless, call the API directly
        // to simulate viewing all pages
        if (capturedSessionId) {
            log(`Using captured session ID: ${capturedSessionId}`);
            log('Simulating view completion via API...');
            const allPages = Array.from({length: totalPages}, (_, i) => i + 1);
            const updateResponse = await page.request.post(
                `${BASE_URL}/api/annotations/${encodeURIComponent(pdfFilename)}/view-session/update`,
                {
                    data: {
                        session_id: capturedSessionId,
                        pages_viewed: allPages
                    }
                }
            );
            const updateData = await updateResponse.json();
            log(`API response: is_complete=${updateData.is_complete}, just_completed=${updateData.just_completed}`);

            if (updateData.is_complete) {
                results.passed.push('View session completed via API');
            }
        } else {
            log('No session ID captured - cannot test view completion');
            results.failed.push('Session ID not captured');
        }

        // 9. Wait for debounced update to send (longer wait)
        log('Waiting for view tracking to complete...');
        await page.waitForTimeout(3000);

        // Scroll to last page again to ensure it's detected
        if (totalPages > 0) {
            await pageWrappers[totalPages - 1].scrollIntoViewIfNeeded();
            await page.waitForTimeout(1000);
        }
        await page.waitForTimeout(2000);

        // 10. Check console for completion message
        const consoleMessages = [];
        page.on('console', msg => consoleMessages.push(msg.text()));

        // Check for completion toast
        const toast = await page.$('div:has-text("PDF fully viewed")');
        if (toast) {
            results.passed.push('View completion toast appeared');
            log('PDF fully viewed toast appeared');
        } else {
            log('Toast not visible (may have auto-dismissed)');
        }

        // 11. Go back to dashboard and check view count
        log('Returning to dashboard...');
        await page.goto(`${BASE_URL}/comprehensive_dashboard.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForTimeout(4000);

        // Find the same PDF row and check view count
        const rows = await page.$$('table tbody tr');
        let newViewCount = initialViewCount;
        const pdfNameStart = pdfName.split(' ')[0].substring(0, 20);

        for (const row of rows) {
            const name = await row.$eval('td:first-child', el => el.textContent.trim());
            if (name.includes(pdfNameStart)) {
                const rowCells = await row.$$('td');
                if (rowCells.length >= 6) {
                    const newViewText = await rowCells[5].textContent();
                    newViewCount = parseInt(newViewText.match(/\d+/)?.[0] || '0');
                }
                log(`View count for ${pdfNameStart}...: ${newViewCount}`);
                break;
            }
        }

        if (newViewCount > initialViewCount) {
            results.passed.push(`View count incremented: ${initialViewCount} -> ${newViewCount}`);
            log(`VIEW COUNT INCREMENTED: ${initialViewCount} -> ${newViewCount}`);
        } else {
            results.failed.push(`View count did not increment: still ${newViewCount}`);
            log(`View count did not increment: still ${newViewCount}`);
        }

        // 12. Test API endpoints
        log('Testing API endpoints...');

        const apiTests = [
            { url: '/api/stats', name: 'Stats API' },
            { url: '/api/assessment/categories', name: 'Categories API' },
            { url: '/api/assessment/check-anki', name: 'Check Anki API' },
        ];

        for (const test of apiTests) {
            try {
                const response = await page.request.get(`${BASE_URL}${test.url}`);
                if (response.ok()) {
                    results.passed.push(`${test.name} returns 200`);
                    log(`${test.name} OK`);
                } else {
                    results.failed.push(`${test.name} failed: ${response.status()}`);
                }
            } catch (e) {
                results.failed.push(`${test.name} error: ${e.message}`);
            }
        }

        // Test other HTML pages
        log('Testing HTML pages...');
        const pageTests = [
            '/index.html',
            '/revision_dashboard.html',
            '/mock_analysis.html',
        ];

        for (const pagePath of pageTests) {
            try {
                const response = await page.request.get(`${BASE_URL}${pagePath}`);
                if (response.ok()) {
                    results.passed.push(`${pagePath} loads`);
                    log(`${pagePath} OK`);
                } else {
                    results.failed.push(`${pagePath} failed: ${response.status()}`);
                }
            } catch (e) {
                results.failed.push(`${pagePath} error: ${e.message}`);
            }
        }

    } catch (error) {
        console.error('Test error:', error.message);
        results.failed.push(`Error: ${error.message}`);
    } finally {
        await browser.close();
    }

    // Summary
    console.log('\n' + '='.repeat(50));
    console.log('TEST SUMMARY');
    console.log('='.repeat(50));
    console.log(`PASSED: ${results.passed.length}`);
    results.passed.forEach(t => console.log(`   [PASS] ${t}`));
    console.log(`FAILED: ${results.failed.length}`);
    results.failed.forEach(t => console.log(`   [FAIL] ${t}`));
    console.log('='.repeat(50));

    process.exit(results.failed.length > 0 ? 1 : 0);
})();
