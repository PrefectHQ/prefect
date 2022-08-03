import { expect } from '@playwright/test'
import { test, useTable } from './utilities'

test('Flows show up in the list', async ({ page }) => {
  await page.goto('/flows')

  const { rows: flows } = useTable('.flows-table')
  const count = await flows.count()

  await expect(count).toEqual(2)
})
