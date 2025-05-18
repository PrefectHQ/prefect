import { createFakeWorkQueue } from '@/mocks'
import { reactQueryDecorator } from '@/storybook/utils'
import type { Meta, StoryObj } from '@storybook/react'
import { WorkPoolQueuesDataTable } from './work-pool-queues-data-table'

const meta: Meta<typeof WorkPoolQueuesDataTable> = {
  title: 'Components/WorkPools/WorkPoolQueuesDataTable',
  component: WorkPoolQueuesDataTable,
  decorators: [reactQueryDecorator],
}
export default meta

type Story = StoryObj<typeof WorkPoolQueuesDataTable>

export const Default: Story = {
  args: {
    workPoolName: 'my-pool',
    workQueues: [createFakeWorkQueue({ work_pool_name: 'my-pool' }), createFakeWorkQueue({ work_pool_name: 'my-pool' })],
  },
}
