import type { ColumnDef } from "@tanstack/react-table";
import { ArrowDown, ArrowUp } from "lucide-react";
import type { WorkPoolWorker } from "@/api/work-pools";
import { FormattedDate } from "@/components/ui/formatted-date";
import { WorkerStatusBadge } from "@/components/workers/worker-status-badge";
import { cn } from "@/utils";

export const createWorkersTableColumns = (): ColumnDef<WorkPoolWorker>[] => [
	{
		accessorKey: "name",
		header: ({ column }) => {
			const sorted = column.getIsSorted();
			return (
				<button
					type="button"
					onClick={() => column.toggleSorting(sorted === "asc")}
					className="flex items-center gap-1 group h-auto p-0 font-medium text-muted-foreground hover:text-foreground"
				>
					Name
					<span
						className={cn(
							"opacity-0 group-hover:opacity-100 transition-opacity size-3",
							sorted && "opacity-100 text-foreground",
						)}
					>
						{sorted === "desc" ? (
							<ArrowDown className="size-3" />
						) : (
							<ArrowUp className="size-3" />
						)}
					</span>
				</button>
			);
		},
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
