import { expect } from '@playwright/test'
import { test, useForm, useCombobox, useLabel, useSelect, useTable, useButton } from './utilities'

test('Can create a notification', async ({ page }) => {
  await page.goto('/notifications')

  const { table, rows: notifications } = useTable('.notifications-table .p-table')
  const existingNotifications = await notifications.count()

  // navigate to the Create Notification page
  await page.locator('[href="/notifications/new"]').first().click()

  const { control: states } = useLabel('Run states')
  const { selectOption } = useSelect(states)
  await selectOption('Completed')
  await selectOption('Running')

  const { control: tags } = useLabel('Tags')
  const { selectCustomOption } = useCombobox(tags)
  await selectCustomOption('foo')

  const { button } = useButton('Slack Webhook')
  button.click()

  const { control: webhookUrl } = useLabel('Webhook URL')
  webhookUrl.fill('https://slack.test')

  const { submit } = useForm('.notification-form')
  submit()

  await table.waitFor()
  const newNotifications = await notifications.count()

  expect(newNotifications).toBe(existingNotifications + 1)
})
