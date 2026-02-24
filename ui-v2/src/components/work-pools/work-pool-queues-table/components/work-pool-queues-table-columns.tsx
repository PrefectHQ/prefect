import { Link } from "@tanstack/react-router";
import type { ColumnDef } from "@tanstack/react-table";
import { ArrowDown, ArrowUp, HelpCircle } from "lucide-react";
import type { WorkPoolQueue } from "@/api/work-pool-queues";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { WorkPoolQueueStatusBadge } from "@/components/work-pools/work-pool-queue-status-badge";
import { cn } from "@/utils";
import { WorkPoolQueueMenu } from "../../work-pool-queue-menu";
import { WorkPoolQueueToggle } from "../../work-pool-queue-toggle";
import { QueueNameWithLateIndicator } from "./queue-name-with-late-indicator";

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
		header: ({ column }) => {
			const sorted = column.getIsSorted();
			return (
				<button
					type="button"
					onClick={() => column.toggleSorting(sorted === "asc")}
					className="flex items-center gap-1 group h-auto p-0 font-medium text-muted-foreground hover:text-foreground"
				>
					Concurrency Limit
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
			const limit = row.original.concurrency_limit;
			return limit !== null && limit !== undefined ? limit.toString() : "∞";
		},
	});

	// Priority column
	columns.push({
		accessorKey: "priority",
		header: ({ column }) => {
			const sorted = column.getIsSorted();
			return (
				<div className="flex items-center space-x-1">
					<button
						type="button"
						onClick={() => column.toggleSorting(sorted === "asc")}
						className="flex items-center gap-1 group h-auto p-0 font-medium text-muted-foreground hover:text-foreground"
					>
						Priority
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
			);
		},
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
