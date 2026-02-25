import { Link } from "@tanstack/react-router";
import type { ColumnDef } from "@tanstack/react-table";
import { HelpCircle } from "lucide-react";
import type { WorkPoolQueue } from "@/api/work-pool-queues";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { WorkPoolQueueStatusBadge } from "@/components/work-pools/work-pool-queue-status-badge";
import { WorkPoolQueueMenu } from "../../work-pool-queue-menu";
import { WorkPoolQueueToggle } from "../../work-pool-queue-toggle";
import { QueueNameWithLateIndicator } from "./queue-name-with-late-indicator";
import { SortableColumnHeader } from "./sortable-column-header";

type WorkPoolQueuesTableColumnsOptions = {
	enableSelection?: boolean;
	enableLateIndicator?: boolean;
};

export const createWorkPoolQueuesTableColumns = ({
	enableLateIndicator = false,
}: WorkPoolQueuesTableColumnsOptions = {}): ColumnDef<WorkPoolQueue>[] => {
	const columns: ColumnDef<WorkPoolQueue>[] = [];
	// Name column with conditional late indicator
	columns.push({
		accessorKey: "name",
		header: ({ column }) => (
			<SortableColumnHeader column={column} label="Name" />
		),
		cell: ({ row }) => {
			const queue = row.original;

			if (enableLateIndicator) {
				return <QueueNameWithLateIndicator queue={queue} />;
			}

			// Basic name cell with link
			return (
				<div className="flex items-center space-x-2">
					<Link
						to="/work-pools/work-pool/$workPoolName/queue/$workQueueName"
						params={{
							workPoolName: queue.work_pool_name || "",
							workQueueName: queue.name,
						}}
						className="font-medium text-link hover:text-link-hover truncate block max-w-[200px]"
						title={queue.name}
					>
						{queue.name}
					</Link>
				</div>
			);
		},
	});

	// Concurrency limit column
	columns.push({
		accessorKey: "concurrency_limit",
		header: ({ column }) => (
			<SortableColumnHeader column={column} label="Concurrency Limit" />
		),
		cell: ({ row }) => {
			const limit = row.original.concurrency_limit;
			return limit !== null && limit !== undefined ? limit.toString() : "∞";
		},
	});

	// Priority column
	columns.push({
		accessorKey: "priority",
		header: ({ column }) => (
			<div className="flex items-center space-x-1">
				<SortableColumnHeader column={column} label="Priority" />
				<TooltipProvider>
					<Tooltip>
						<TooltipTrigger>
							<HelpCircle className="h-4 w-4 text-muted-foreground" />
						</TooltipTrigger>
						<TooltipContent>
							<p>Lower numbers have higher priority</p>
						</TooltipContent>
					</Tooltip>
				</TooltipProvider>
			</div>
		),
		cell: ({ row }) => row.original.priority,
	});

	// Status column
	columns.push({
		accessorKey: "status",
		header: "Status",
		cell: ({ row }) => (
			<WorkPoolQueueStatusBadge status={row.original.status || "READY"} />
		),
	});

	// Actions column
	columns.push({
		id: "actions",
		header: "",
		cell: ({ row }) => (
			<div className="flex items-center justify-end gap-2">
				<WorkPoolQueueToggle queue={row.original} />
				<WorkPoolQueueMenu queue={row.original} />
			</div>
		),
		enableSorting: false,
	});

	return columns;
};

// Basic version for backward compatibility
export const workPoolQueuesTableColumns: ColumnDef<WorkPoolQueue>[] =
	createWorkPoolQueuesTableColumns();
