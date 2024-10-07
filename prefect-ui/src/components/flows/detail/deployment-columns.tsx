import { ColumnDef } from "@tanstack/react-table"
import { components } from '@/api/prefect'
import { Button } from "@/components/ui/button"
import { MoreHorizontal } from "lucide-react"
import { Link } from "@tanstack/react-router"

type Deployment = components['schemas']['DeploymentResponse']

export const columns: ColumnDef<Deployment>[] = [
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => (
      <Link to='/flows/flow/$id/deployment/$deploymentId' params={{id: row.original.flow_id, deploymentId: row.original.id}} className="text-primary hover:underline cursor-pointer">
        {row.original.name}
      </Link>
    ),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => (
      <span className={`px-2 py-1 rounded-full text-xs font-medium`}>
      </span>
    ),
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
    accessorKey: "schedule",
    header: "Schedule",
    cell: ({ row }) => (
      <span>noice</span>
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
