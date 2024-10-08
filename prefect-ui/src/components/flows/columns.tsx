import {
  ColumnDef,
} from '@tanstack/react-table'
import { Checkbox } from "@/components/ui/checkbox"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { MoreVerticalIcon } from 'lucide-react'
import { Link } from '@tanstack/react-router'
import { components } from '@/api/prefect'
import { useQuery } from '@tanstack/react-query'
import { deploymentsCountQueryParams, getLatestFlowRunsQueryParams, getNextFlowRunsQueryParams } from './queries'
import { cn } from '@/lib/utils'
import { format, parseISO } from 'date-fns'

type Flow = components['schemas']['Flow']

const FlowName = ({ row }: { row: { original: Flow } }) => {
    if (!row.original.id) return null;

    return (
        <div>
            <Link to='/flows/flow/$id' params={{id: row.original.id}} className="text-primary hover:underline cursor-pointer">{row.original.name}</Link>
            <div className="text-sm text-muted-foreground">Created {row.original?.created && format(parseISO(row.original.created), 'yyyy-MM-dd')}</div>
        </div>
    )
}
    
const FlowLastRun = ({ row }: { row: { original: Flow } }) => {
    if (!row.original.id) return null;

    const { data } = useQuery(getLatestFlowRunsQueryParams(row.original.id, 16, { enabled: true }))
    return JSON.stringify(data?.[0]?.name)
}

const FlowNextRun = ({ row }: { row: { original: Flow } }) => {
    if (!row.original.id) return null;

    const { data } = useQuery(getNextFlowRunsQueryParams(row.original.id, 16, { enabled: true }))
    return JSON.stringify(data?.[0]?.name)
}

const FlowDeploymentCount = ({ row }: { row: { original: Flow } }) => {
    if (!row.original.id) return null;

    const { data } = useQuery(deploymentsCountQueryParams(row.original.id, { enabled: true }))
    return data
}

const FlowActionMenu = ({ row }: { row: { original: Flow } }) => {
    const id = row.original.id;
    if (!id){return null};
    return (
        <DropdownMenu>
            <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="h-8 w-8 p-0">
                    <span className="sr-only">Open menu</span>
                    <MoreVerticalIcon className="h-4 w-4" />
                </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
                <DropdownMenuLabel>Actions</DropdownMenuLabel>
                <DropdownMenuItem onClick={() => navigator.clipboard.writeText(id)}>
                    Copy ID
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem>Delete</DropdownMenuItem>
                <DropdownMenuItem>Automate</DropdownMenuItem>
            </DropdownMenuContent>
        </DropdownMenu>
    )
}

const FlowActivity = ({ row }: { row: { original: Flow } }) => {
    if (!row.original.id) return null;

    const { data } = useQuery(getLatestFlowRunsQueryParams(row.original.id, 16, { enabled: true }))

    return (
        <div className="flex h-[24px]">
         {Array(16).fill(1)?.map((_, index) => (
            <div 
            key={index}
            className={
                cn(
                    "flex-1 mr-[1px] rounded-full bg-gray-400",
                    data?.[index]?.state_type && data?.[index]?.state_type === 'COMPLETED' && 'bg-green-500',
                    data?.[index]?.state_type && data?.[index]?.state_type !== 'COMPLETED' && 'bg-red-500',
            )}/>
         ))}
        </div>
    )
}

export const columns: ColumnDef<Flow>[] = [
    {
      id: "select",
      header: ({ table }) => (
        <Checkbox
          checked={table.getIsAllPageRowsSelected()}
          onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
          aria-label="Select all"
        />
      ),
      cell: ({ row }) => (
        <Checkbox
          checked={row.getIsSelected()}
          onCheckedChange={(value) => row.toggleSelected(!!value)}
          aria-label="Select row"
        />
      ),
      enableSorting: false,
      enableHiding: false,
    },
    {
      accessorKey: "name",
      header: "Name",
      cell: FlowName,
    },
    {
      accessorKey: "lastRuns",
      header: 'Last Run',
      cell: FlowLastRun,
    },
    {
      accessorKey: "nextRuns",
      header: 'Next Run',
      cell: FlowNextRun,
    },
    {
      accessorKey: "deployments",
      header: "Deployments",
      cell: FlowDeploymentCount,
    },
    {
      accessorKey: "activity",
      header: "Activity",
      cell: FlowActivity,
    },
    {
      id: "actions",
      cell: FlowActionMenu,
    },
  ]
