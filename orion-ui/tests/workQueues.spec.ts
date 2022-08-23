import { expect } from '@playwright/test'
import { test, useForm, useLabel, useTable, usePageHeading, useLink, pages, useIconButtonMenu, useModal, useButton } from './utilities'
import { useToggle } from './utilities/useToggle'

test.describe.configure({ mode: 'serial' })

test.beforeEach(async ({ page }) => {
  await page.goto(pages.workQueues)
})

const workQueueNameToCreate = 'string'

test('Can create work queue', async ({ page }) => {
  const { table, rows: workQueues } = useTable()
  const existingWorkQueues = await workQueues.count()

  await createWorkQueue()

  await page.goto(pages.workQueues)

  await table.waitFor()
  const newWorkQueues = await workQueues.count()

  expect(newWorkQueues).toBe(existingWorkQueues + 1)
})

test('Can toggle workQueue from list', async () => {
  const { rows: worksQueues } = useTable()
  const worksQueue = worksQueues.filter({
    hasText: workQueueNameToCreate,
  })

  const { getState, setState } = useToggle(worksQueue)
  const currentState = await getState()
  await setState(!currentState)
  const newState = await getState()

  expect(newState).toBe(!currentState)
})

test('Can delete worksQueue from list', async () => {
  const { rows: worksQueues } = useTable()
  const worksQueue = worksQueues.filter({
    hasText: workQueueNameToCreate,
  }).first()
  const existingWorksQueues = await worksQueues.count()

  const { selectItem } = useIconButtonMenu(undefined, worksQueue)
  await selectItem('Delete')

  const { footer, closed } = useModal()
  const { button } = useButton('Delete', footer)

  await button.click()
  await closed()

  const newWorksQueues = await worksQueues.count()

  expect(newWorksQueues).toBe(existingWorksQueues - 1)
})

test('Can toggle workQueue', async ({ page }) => {
  await createWorkQueue()
  await page.waitForNavigation({
    url: /\/work-queue\//,
  })

  const { toggle, getState, setState } = useToggle()
  await toggle.waitFor()
  const currentState = await getState()
  await setState(!currentState)
  const newState = await getState()

  expect(newState).toBe(!currentState)
})

async function createWorkQueue(): Promise<void> {
  const { heading } = usePageHeading()
  const { link } = useLink(pages.workQueuesCreate, heading)
  await link.click()

  const { control: name } = useLabel('Name')
  const input = name.locator('input')
  await input.fill(workQueueNameToCreate)

  const { submit } = useForm()
  await submit()
}