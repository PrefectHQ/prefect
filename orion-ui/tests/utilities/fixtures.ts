import { test as base, Page, APIRequestContext } from '@playwright/test'
import { mapper, mocker, WorkQueue, WorkQueueCreate } from '@prefecthq/orion-design'

export let PAGE: Page

type CustomFixtures = {
  page: Page,
  useWorkQueue: (override?: Partial<WorkQueue>) => Promise<WorkQueue>,
}

export const test = base.extend<CustomFixtures>({
  page: async ({ page }, use) => {
    PAGE = page
    await use(page)
  },
  useWorkQueue: async ({ request }, use) => {
    let workQueue: WorkQueue | undefined

    await use(async (override: Partial<WorkQueue> = {}) => {
      const data = mocker.create('workQueue', [override])

      workQueue = await createWorkQueue(request, data)

      return workQueue
    })

    if (workQueue) {
      await deleteWorkQueue(request, workQueue.id)
    }
  },
})

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