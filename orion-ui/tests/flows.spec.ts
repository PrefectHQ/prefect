import { test, expect } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.goto('http://127.0.0.1:4200/flows')
})

test('Flows show up in the list', async ({ page }) => {
  const flows = page.locator('.flows-table .p-table-body .p-table-row')

  await expect(await flows.count()).toEqual(2)
})
