import { expect } from '@playwright/test'
import { test, useButton, useCombobox, useLabel, useSelect, useTable } from './utilities'

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

  const { button: slackWebhookButton } = useButton('Slack Webhook')
  await slackWebhookButton.click()

  const { control: webhookUrl } = useLabel('Webhook URL')
  await webhookUrl.fill('https://slack.test')

  const { button: createButton } = useButton('Create')
  await createButton.click()

  await table.waitFor()
  const newNotifications = await notifications.count()

  expect(newNotifications).toBe(existingNotifications + 1)
})
