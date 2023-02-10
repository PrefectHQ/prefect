import { test as base, Page, APIRequestContext } from '@playwright/test'
import { mapper, mocker, WorkQueue, WorkQueueCreate } from '@prefecthq/prefect-ui-library'

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

    await use(async (override: Partial<WorkQueueCreate> = {}) => {
      const data = mocker.create('workQueueCreate', [override])

      workQueue = await createWorkQueue(request, data)

      return workQueue
    })

    if (workQueue) {
      try {
        await deleteWorkQueue(request, workQueue.id)
      } catch {
        // do nothing
      }
    }
  },
})

const baseUrl = process.env.playwright_base_api_url ?? 'http://127.0.0.1:4200/api'

// could possibly be replaced with actual api calls in future
async function createWorkQueue(request: APIRequestContext, workQueue: WorkQueueCreate): Promise<WorkQueue> {
  const response = await request.post(`${baseUrl}/work_queues/`, {
    data: mapper.map('WorkQueueCreate', workQueue, 'WorkQueueCreateRequest'),
  })

  return mapper.map('WorkQueueResponse', await response.json(), 'WorkQueue')
}

async function deleteWorkQueue(request: APIRequestContext, id: string): Promise<void> {
  await request.delete(`${baseUrl}/work_queues/${id}`)
}