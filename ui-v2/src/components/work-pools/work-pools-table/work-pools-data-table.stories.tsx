import { createFakeWorkPool } from '@/mocks'
import { reactQueryDecorator } from '@/storybook/utils'
import type { Meta, StoryObj } from '@storybook/react'
import { WorkPoolsDataTable } from './work-pools-data-table'

const meta: Meta<typeof WorkPoolsDataTable> = {
  title: 'Components/WorkPools/WorkPoolsDataTable',
  component: WorkPoolsDataTable,
  decorators: [reactQueryDecorator],
}
export default meta

type Story = StoryObj<typeof WorkPoolsDataTable>

export const Default: Story = {
  args: {
    workPools: [createFakeWorkPool(), createFakeWorkPool(), createFakeWorkPool()],
    totalCount: 3,
  },
}
