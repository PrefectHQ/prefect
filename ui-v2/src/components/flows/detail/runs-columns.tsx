import { ColumnDef } from "@tanstack/react-table"
import { components } from '@/api/prefect'
import { format, parseISO } from 'date-fns'
import { useQuery } from '@tanstack/react-query'
import { QueryService } from '@/api/service'

type FlowRun = components['schemas']['FlowRun']

const DeploymentCell = ({ row }: { row: { original: FlowRun } }) => {
  const deploymentId = row.original.deployment_id;
  const { data: deployment } = useQuery({
    queryKey: ['deployment', deploymentId],
    queryFn: () => QueryService.GET('/deployments/{id}', { params: { path: { id: deploymentId as string } } }),
    enabled: !!deploymentId
  });
  return (
      deployment?.data?.name
  )
};

const WorkPoolCell = ({ row }: { row: { original: FlowRun } }) => {
  const deploymentId = row.original.deployment_id;
  const { data: deployment } = useQuery({
    queryKey: ['deployment', deploymentId],
    queryFn: () => QueryService.GET('/deployments/{id}', { params: { path: { id: deploymentId as string} } }),
    enabled: !!deploymentId
  });

  return (
      deployment?.data?.work_pool_name
  )
};

export const columns: ColumnDef<FlowRun>[] = [
  {
    accessorKey: "created",
    header: "Time",
    cell: ({ row }) => (
      <div className="text-xs text-muted-foreground uppercase font-mono">
        {row.original.created && format(parseISO(row.original.created), 'MMM dd HH:mm:ss OOOO')}
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
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => (
          row.original.name

    ),
  },
  {
    accessorKey: "deployment",
    header: "Deployment",
    cell: ({ row }) => <DeploymentCell row={row} />,
  },
  {
    accessorKey: "work_pool",
    header: "Work Pool",
    cell: ({ row }) => <WorkPoolCell row={row} />,
  },
  {
    accessorKey: "work_queue",
    header: "Work Queue",
    cell: ({ row }) => (
        row.original.work_queue_name
    ),
  },
  {
    accessorKey: "tags",
    header: "Tags",
    cell: ({ row }) => row.original.tags?.map((tag, index) => (
      <span key={index} className="bg-gray-100 text-gray-800 text-xs font-medium px-2 py-0.5 rounded">
        {tag}
      </span>
    )),
  },
  {
    accessorKey: "duration",
    header: "Duration",
    cell: ({ row }) => (
      <span>{row.original.estimated_run_time ? `${row.original.estimated_run_time}s` : '-'}</span>
    ),
  },
]
