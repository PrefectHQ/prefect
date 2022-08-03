import { expect } from '@playwright/test'
import { test, usePageHeading } from './utilities'

test('Flow runs page has Flow Runs title', async ({ page }) => {
  await page.goto('/runs')

  const { heading } = usePageHeading()

  await expect(heading).toHaveText('Flow Runs')
})
