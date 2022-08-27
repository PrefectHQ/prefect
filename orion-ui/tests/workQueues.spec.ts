import { APIRequestContext, expect } from '@playwright/test'
import { mapper, mocker, WorkQueue, WorkQueueCreate } from '@prefecthq/orion-design'
import { test, useForm, useLabel, useTable, usePageHeading, useLink, pages, useIconButtonMenu, useModal, useButton } from './utilities'
import { useInput } from './utilities/useInput'
import { useToggle } from './utilities/useToggle'

test.describe.configure({ mode: 'parallel' })

const workQueueIdsCreated: string[] = []

test.afterEach(({ request }) => {
  workQueueIdsCreated.forEach(id => {
    deleteWorkQueue(request, id)
  })
})

test('Can create work queue', async ({ page }) => {
  await page.goto(pages.workQueues())

  const { table } = useTable()
  const { heading } = usePageHeading()
  const { link } = useLink(pages.workQueuesCreate(), heading)
  await link.click()

  const { control: name } = useLabel('Name')
  const workQueueName = mocker.create('string')
  const { input } = useInput(name)
  await input.fill(workQueueName)

  const { submit } = useForm()
  await submit()

  await page.goto(pages.workQueues())

  await table.waitFor()
  const worksQueue = table.filter({
    hasText: workQueueName,
  })

  expect(worksQueue).toBeTruthy()
})

test('Can toggle workQueue from list', async ({ page, request }) => {
  const workQueue = await useWorkQueue(request)
  await page.goto(pages.workQueues())

  const { rows: workQueues } = useTable()
  const worksQueueRow = workQueues.filter({
    hasText: workQueue.name,
  })

  const { toggle } = useToggle(worksQueueRow)
  const currentState = await toggle.isChecked()
  await toggle.setChecked(!currentState)
  const newState = await toggle.isChecked()

  expect(newState).toBe(!currentState)
})

test('Can delete worksQueue from list', async ({ page, request }) => {
  const workQueue = await useWorkQueue(request)

  await page.goto(pages.workQueues())
  const { rows: workQueues } = useTable()
  const worksQueueRow = workQueues.filter({
    hasText: workQueue.name,
  }).first()

  const { selectItem } = useIconButtonMenu(undefined, worksQueueRow)
  await selectItem('Delete')

  const { footer, closed } = useModal()
  const { button } = useButton('Delete', footer)

  await button.click()
  await closed()

  const updatedRow = workQueues.filter({
    hasText: workQueue.name,
  })

  expect(await updatedRow.count()).toBe(0)
})

test('Can toggle workQueue', async ({ page, request }) => {
  const workQueue = await useWorkQueue(request)
  const url = pages.workQueue(workQueue.id)
  await page.goto(url)

  const { toggle } = useToggle()
  await toggle.waitFor()
  const currentState = await toggle.isChecked()
  await toggle.setChecked(!currentState)
  const newState = await toggle.isChecked()

  expect(newState).toBe(!currentState)
})

async function useWorkQueue(request: APIRequestContext): Promise<WorkQueue> {
  const workQueue = await createWorkQueue(request, {
    name: mocker.create('string'),
  })

  workQueueIdsCreated.push(workQueue.id)

  return workQueue
}

const baseUrl = 'http://127.0.0.1:4200/api'
async function createWorkQueue(request: APIRequestContext, workQueue: WorkQueueCreate): Promise<WorkQueue> {
  const response = await request.post(`${baseUrl}/work_queues/`, {
    data: workQueue,
  })

  return mapper.map('WorkQueueResponse', await response.json(), 'WorkQueue')
}

async function deleteWorkQueue(request: APIRequestContext, id: string): Promise<void> {
  await request.delete(`${baseUrl}/work_queues/${id}`)
}