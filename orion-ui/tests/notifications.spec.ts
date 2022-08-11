import { expect } from '@playwright/test'
import { test, useForm, useCombobox, useLabel, useSelect, useTable, useButton, usePageHeading, useLink, pages, useIconButtonMenu, useTag, useModal } from './utilities'

test.describe.configure({ mode: 'serial' })

test('Can create notification', async ({ page }) => {
  await page.goto(pages.notifications)

  const { table, rows: notifications } = useTable()
  const existingNotifications = await notifications.count()

  const { heading } = usePageHeading()
  const { link } = useLink(pages.notificationsCreate, heading)
  await link.click()

  const { control: states } = useLabel('Run states')
  const { selectOption } = useSelect(states)
  await selectOption('Completed')
  await selectOption('Running')

  const { control: tags } = useLabel('Tags')
  const { selectCustomOption } = useCombobox(tags)
  await selectCustomOption('playwright')

  const { button } = useButton('Slack Webhook')
  await button.click()

  const { control: webhookUrl } = useLabel('Webhook URL')
  await webhookUrl.fill('https://slack.test')

  const { submit } = useForm()
  await submit()

  await table.waitFor()
  const newNotifications = await notifications.count()

  expect(newNotifications).toBe(existingNotifications + 1)
})

test('Can edit notification', async ({ page }) => {
  const tagToAdd = 'playwright-edited'

  await page.goto(pages.notifications)

  const { rows: notifications } = useTable()
  const notification = notifications.first()

  const { selectItem: select } = useIconButtonMenu(undefined, notification)
  await select('Edit')

  const { control: tags } = useLabel('Tags')
  const { selectCustomOption } = useCombobox(tags)
  await selectCustomOption(tagToAdd)

  const { submit } = useForm()
  await submit()

  const { tag } = useTag(tagToAdd)

  await notification.waitFor()
  await tag.waitFor()

  await expect(tag).toBeVisible()
})

test('Can delete notification', async ({ page }) => {
  await page.goto(pages.notifications)

  const { rows: notifications } = useTable()
  const notification = notifications.first()
  const existingNotifications = await notifications.count()

  const { selectItem } = useIconButtonMenu(undefined, notification)
  await selectItem('Delete')

  const { footer, closed } = useModal()
  const { button } = useButton('Delete', footer)

  await button.click()
  await closed()

  const newNotifications = await notifications.count()

  expect(newNotifications).toBe(existingNotifications - 1)
})