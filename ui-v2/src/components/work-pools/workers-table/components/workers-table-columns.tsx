import type { ColumnDef } from "@tanstack/react-table";
import type { WorkPoolWorker } from "@/api/work-pools";
import { FormattedDate } from "@/components/ui/formatted-date";
import { SortableColumnHeader } from "@/components/work-pools/work-pool-queues-table/components/sortable-column-header";
import { WorkerStatusBadge } from "@/components/workers/worker-status-badge";

export const createWorkersTableColumns = (): ColumnDef<WorkPoolWorker>[] => [
	{
		accessorKey: "name",
		header: ({ column }) => (
			<SortableColumnHeader column={column} label="Name" />
		),
		cell: ({ row }) => {
			const worker = row.original;
			return (
				<span
					className="font-medium truncate block max-w-[200px]"
					title={worker.name}
				>
					{worker.name}
				</span>
			);
		},
	},
	{
		accessorKey: "last_heartbeat_time",
		header: "Last Seen",
		cell: ({ row }) => {
			const lastSeen = row.original.last_heartbeat_time;
			return <FormattedDate date={lastSeen} format="relative" showTooltip />;
		},
	},
	{
		accessorKey: "status",
		header: "Status",
		cell: ({ row }) => <WorkerStatusBadge status={row.original.status} />,
	},
];

type WorkersTableColumnsWithActionsProps = {
	workPoolName: string;
	ActionsComponent: React.ComponentType<{
		worker: WorkPoolWorker;
		workPoolName: string;
	}>;
};

export const createWorkersTableColumnsWithActions = ({
	workPoolName,
	ActionsComponent,
}: WorkersTableColumnsWithActionsProps): ColumnDef<WorkPoolWorker>[] => [
	...createWorkersTableColumns(),
	{
		id: "actions",
		header: "",
		cell: ({ row }) => (
			<ActionsComponent worker={row.original} workPoolName={workPoolName} />
		),
		enableSorting: false,
		size: 50,
		maxSize: 50,
	},
];
