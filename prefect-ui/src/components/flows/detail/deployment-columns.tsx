import { ColumnDef } from "@tanstack/react-table"
import { components } from '@/api/prefect'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Button } from "@/components/ui/button"
import { MoreHorizontal } from "lucide-react"

type Deployment = components['schemas']['DeploymentResponse']

export const columns: ColumnDef<Deployment>[] = [
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => (
        row.original.name
    ),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => {
      return row.original.status;
    },
  },
  {
    accessorKey: "tags",
    header: "Tags",
    cell: ({ row }) => (
      <div className="flex flex-wrap gap-1">
        {row.original.tags?.map((tag, index) => (
          <span key={index} className="bg-gray-100 text-gray-800 text-xs font-medium px-2 py-0.5 rounded">
            {tag}
          </span>
        ))}
      </div>
    ),
  },
  {
    accessorKey: "schedules",
    header: "Schedules",
    cell: ({ row }) => (
      <div className="flex flex-col gap-1">
        {row.original.schedules?.map((schedule, index) => (
          <span key={index} className="text-xs">
            {JSON.stringify(schedule.schedule)}
          </span>
        ))}
      </div>
    ),
  },
  {
    id: "actions",
    cell: () => {
      return (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="h-8 w-8 p-0">
              <span className="sr-only">Open menu</span>
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem>Quick run</DropdownMenuItem>
            <DropdownMenuItem>Custom run</DropdownMenuItem>
            <DropdownMenuItem>Copy ID</DropdownMenuItem>
            <DropdownMenuItem>Edit</DropdownMenuItem>
            <DropdownMenuItem>Delete</DropdownMenuItem>
            <DropdownMenuItem>Duplicate</DropdownMenuItem>
            <DropdownMenuItem>Manage Access</DropdownMenuItem>
            <DropdownMenuItem>Add to incident</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      )
    },
  },
]
