import { test, expect, Page } from '@playwright/test'

async function countNotifications(page: Page): Promise<number> {
  const rows = await page.locator('.notifications-table .p-table-body .p-table-row')

  return await rows.count()
}

test('Can create a notification', async ({ page }) => {
  await page.goto('http://127.0.0.1:4200/notifications')
  const notifications = await countNotifications(page)

  // navigate to the Create Notification page
  await page.locator('[href="/notifications/new"]').first().click()
  await page.locator('.notification-create').waitFor()

  // select a state
  const states = await page.locator('.state-select')
  await states.click()
  await page.locator('.p-select-option').first().click()
  await states.click()

  // add a tag
  const tags = await page.locator('.p-tags-input')
  await tags.click()
  await page.locator('.p-combobox__text-input').fill('foo')
  await page.keyboard.press('Enter')
  await tags.click()

  // pick "Slack Webhook"
  await page.locator('.p-button-group').locator('text=Slack Webhook').click()

  // fill Webhook URL input
  await page.locator('text=Webhook URL').fill('https://slack.test')

  // create the notification
  await page.locator('.p-form__footer').locator('text=Create').click()

  // wait for navigation to the Notifications page
  await page.locator('.notifications .p-table.notifications-table').waitFor()

  const expected = notifications + 1

  expect(await countNotifications(page)).toBe(expected)
})
