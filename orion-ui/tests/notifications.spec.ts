import { expect } from '@playwright/test'
import { mocker } from '@prefecthq/orion-design'
import { test, useForm, useCombobox, useLabel, useSelect, useTable, useButton, usePageHeading, useLink, pages, useIconButtonMenu, useTag, useModal } from './utilities'

test.describe.configure({ mode: 'serial' })

test.beforeEach(async ({ page }) => {
  await page.goto(pages.notifications())
})

test('Can create notification', async () => {
  const { table, rows: notifications } = useTable()
  const existingNotifications = await notifications.count()

  const { heading } = usePageHeading()
  const { link } = useLink(pages.notificationsCreate(), heading)
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
  const input = webhookUrl.locator('input')
  await input.fill(mocker.create('url'))

  const { submit } = useForm()
  await submit()

  await table.waitFor()
  const newNotifications = await notifications.count()

  expect(newNotifications).toBe(existingNotifications + 1)
})

test('Can edit notification', async () => {
  const tagToAdd = mocker.create('string')

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