import { test, expect } from '@playwright/test';

test('FE: loaded', async ({ page }) => {
  // Navigate to the application URL
  await page.goto('http://localhost:5173/');

  // Wait for a specific element to be visible, which implicitly waits for the page to load.
  // Expects page to have a heading with the name of get started.
  await expect(page.getByRole('heading', { name: 'Get started' })).toBeVisible();
});

test('BE: GET /health endpoint should return 200 OK', async ({ page }) => {
  // Navigate to the backend health check endpoint on port 8171
  await page.goto('http://127.0.0.1:8111/health');

  // Check if the response status code is 200 OK
  await expect(page).toHaveURL(/health/);
  await expect(page.getByText('{"status":"ok"}')).toBeVisible();
});