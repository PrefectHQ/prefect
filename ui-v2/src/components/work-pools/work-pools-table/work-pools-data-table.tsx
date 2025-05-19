import type { WorkPool } from '@/api/work-pools'
import { useDeleteWorkPool } from '@/api/work-pools'
import { DataTable } from '@/components/ui/data-table'
import { SearchInput } from '@/components/ui/input'
import { StatusBadge } from '@/components/ui/status-badge'
import { WorkPoolContextMenu } from '../work-pool-card/components/work-pool-context-menu'
import { WorkPoolName } from '../work-pool-card/components/work-pool-name'
import { WorkPoolPauseResumeToggle } from '../work-pool-card/components/work-pool-pause-resume-toggle'
import { WorkPoolTypeBadge } from '../work-pool-card/components/work-pool-type-badge'
import { pluralize } from '@/utils'
import { createColumnHelper, getCoreRowModel, useReactTable } from '@tanstack/react-table'
import { useCallback, useMemo, useState } from 'react'
import { toast } from 'sonner'

type WorkPoolsDataTableProps = {
  workPools: WorkPool[]
  totalCount: number
}

const columnHelper = createColumnHelper<WorkPool>()

export const WorkPoolsDataTable = ({ workPools, totalCount }: WorkPoolsDataTableProps) => {
  const { deleteWorkPool } = useDeleteWorkPool()
  const [search, setSearch] = useState('')

  const filteredWorkPools = useMemo(() => {
    return workPools.filter(pool =>
      [pool.name, pool.description, pool.type, pool.id].join(' ').toLowerCase().includes(search.toLowerCase()),
    )
  }, [workPools, search])

  const handleDelete = useCallback(
    (pool: WorkPool) => {
      deleteWorkPool(pool.name, {
        onSuccess: () => toast.success(`${pool.name} deleted`),
        onError: () => toast.error(`Failed to delete ${pool.name}`),
      })
    },
    [deleteWorkPool],
  )

  const columns = useMemo(
    () => [
      columnHelper.display({
        id: 'name',
        header: 'Name',
        cell: ({ row }) => <WorkPoolName workPoolName={row.original.name} />,
      }),
      columnHelper.accessor('type', {
        header: 'Type',
        cell: info => <WorkPoolTypeBadge type={info.getValue()} />,
      }),
      columnHelper.accessor('concurrency_limit', {
        header: 'Concurrency',
        cell: info => info.getValue() ?? 'Unlimited',
      }),
      columnHelper.accessor('status', {
        header: 'Status',
        cell: info => info.getValue() && <StatusBadge status={info.getValue()} />,
      }),
      columnHelper.display({
        id: 'actions',
        cell: ({ row }) => (
          <div className='flex items-center gap-2 justify-end'>
            <WorkPoolPauseResumeToggle workPool={row.original} />
            <WorkPoolContextMenu workPool={row.original} onDelete={() => handleDelete(row.original)} />
          </div>
        ),
      }),
    ],
    [handleDelete],
  )

  const table = useReactTable({
    data: filteredWorkPools,
    columns,
    getCoreRowModel: getCoreRowModel(),
  })

  return (
    <div>
      <div className='flex items-end justify-between pb-4'>
        <p className='text-sm text-muted-foreground'>
          {totalCount} {pluralize(totalCount, 'work pool')}
        </p>
        <SearchInput placeholder='Search work pools...' value={search} onChange={e => setSearch(e.target.value)} />
      </div>
      <DataTable table={table} />
    </div>
  )
}
