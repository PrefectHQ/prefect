import { ColumnDef } from "@tanstack/react-table"
import { components } from '@/api/prefect'
import { Button } from "@/components/ui/button"
import { MoreHorizontal } from "lucide-react"
import { format, parseISO } from 'date-fns'
import { Link } from "@tanstack/react-router"

type FlowRun = components['schemas']['FlowRun']

export const columns: ColumnDef<FlowRun>[] = [
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => (
      <div>
        <Link to='/flows/flow/$id/run/$runId' params={{id: row.original.flow_id, runId: row.original.id}} className="text-primary hover:underline cursor-pointer">
          {row.original.name}
        </Link>
        <div className="text-sm text-muted-foreground">
          {row.original.created && format(parseISO(row.original.created), 'yyyy-MM-dd HH:mm:ss')}
        </div>
      </div>
    ),
  },
  {
    accessorKey: "state",
    header: "State",
    cell: ({ row }) => (
      <span className={`px-2 py-1 rounded-full text-xs font-medium
        ${row.original.state?.type === 'COMPLETED' ? 'bg-green-100 text-green-800' : 
          row.original.state?.type === 'FAILED' ? 'bg-red-100 text-red-800' : 
          'bg-yellow-100 text-yellow-800'}`}>
        {row.original.state?.name}
      </span>
    ),
  },
  {
    accessorKey: "duration",
    header: "Duration",
    cell: ({ row }) => (
      <span>{row.original.estimated_run_time ? `${row.original.estimated_run_time}s` : '-'}</span>
    ),
  },
  {
    accessorKey: "actions",
    header: "",
    cell: ({ row }) => (
      <Button variant="ghost" size="icon">
        <MoreHorizontal className="h-4 w-4" />
      </Button>
    ),
  },
]
