import type { WorkQueue } from '@/api/work-queues'
import { DataTable } from '@/components/ui/data-table'
import { StatusBadge } from '@/components/ui/status-badge'
import { WorkQueueLink } from '../work-queue-link'
import { createColumnHelper, getCoreRowModel, useReactTable } from '@tanstack/react-table'
import { useMemo } from 'react'

type WorkPoolQueuesDataTableProps = {
  workPoolName: string
  workQueues: WorkQueue[]
}

const columnHelper = createColumnHelper<WorkQueue>()

export const WorkPoolQueuesDataTable = ({ workPoolName, workQueues }: WorkPoolQueuesDataTableProps) => {
  const columns = useMemo(
    () => [
      columnHelper.display({
        id: 'name',
        header: 'Name',
        cell: ({ row }) => (
          <WorkQueueLink workPoolName={workPoolName} workQueueName={row.original.name} />
        ),
      }),
      columnHelper.accessor('priority', {
        header: 'Priority',
      }),
      columnHelper.accessor('concurrency_limit', {
        header: 'Concurrency',
        cell: info => info.getValue() ?? 'Unlimited',
      }),
      columnHelper.accessor('status', {
        header: 'Status',
        cell: info => info.getValue() && <StatusBadge status={info.getValue()} />,
      }),
    ],
    [workPoolName],
  )

  const table = useReactTable({
    data: workQueues,
    columns,
    getCoreRowModel: getCoreRowModel(),
  })

  return <DataTable table={table} />
}
