import { test, expect } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.goto('http://127.0.0.1:4200/runs')
})

test('Flow runs page has Flow Runs title', async ({ page }) => {

  const heading = page.locator('.page-heading')

  await expect(heading).toHaveText('Flow Runs')
})
