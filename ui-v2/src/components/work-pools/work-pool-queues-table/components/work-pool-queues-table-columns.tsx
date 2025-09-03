import { Link } from "@tanstack/react-router";
import type { ColumnDef } from "@tanstack/react-table";
import { ArrowUpDown, HelpCircle } from "lucide-react";
import type { WorkPoolQueue } from "@/api/work-pool-queues";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { WorkPoolQueueStatusBadge } from "@/components/work-pools/work-pool-queue-status-badge";
import { QueueNameWithLateIndicator } from "./queue-name-with-late-indicator";
import { WorkPoolQueueRowActions } from "./work-pool-queue-row-actions";

type WorkPoolQueuesTableColumnsOptions = {
	enableSelection?: boolean;
	enableLateIndicator?: boolean;
};

export const createWorkPoolQueuesTableColumns = ({
	enableSelection = false,
	enableLateIndicator = false,
}: WorkPoolQueuesTableColumnsOptions = {}): ColumnDef<WorkPoolQueue>[] => {
	const columns: ColumnDef<WorkPoolQueue>[] = [];

	// Conditional checkbox column for selection
	if (enableSelection) {
		columns.push({
			id: "select",
			header: ({ table }) => (
				<Checkbox
					checked={
						table.getIsAllPageRowsSelected() ||
						(table.getIsSomePageRowsSelected() && "indeterminate")
					}
					onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
					aria-label="Select all"
				/>
			),
			cell: ({ row }) => (
				<Checkbox
					checked={row.getIsSelected()}
					onCheckedChange={(value) => row.toggleSelected(!!value)}
					aria-label="Select row"
					disabled={!row.getCanSelect()}
				/>
			),
			enableSorting: false,
			enableHiding: false,
		});
	}

	// Name column with conditional late indicator
	columns.push({
		accessorKey: "name",
		header: ({ column }) => (
			<Button
				variant="ghost"
				onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
				className="h-auto p-0 font-semibold"
			>
				Name
				<ArrowUpDown className="ml-2 h-4 w-4" />
			</Button>
		),
		cell: ({ row }) => {
			const queue = row.original;

			if (enableLateIndicator) {
				return <QueueNameWithLateIndicator queue={queue} />;
			}

			// Basic name cell with link and default badge
			const isDefault = queue.name === "default";
			return (
				<div className="flex items-center space-x-2">
					<Link
						to="/work-pools/work-pool/$workPoolName/queue/$workQueueName"
						params={{
							workPoolName: queue.work_pool_name || "",
							workQueueName: queue.name,
						}}
						className="font-medium text-blue-600 hover:text-blue-800"
					>
						{queue.name}
					</Link>
					{isDefault && (
						<Badge variant="secondary" className="text-xs">
							Default
						</Badge>
					)}
				</div>
			);
		},
	});

	// Concurrency limit column
	columns.push({
		accessorKey: "concurrency_limit",
		header: ({ column }) => (
			<Button
				variant="ghost"
				onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
				className="h-auto p-0 font-semibold"
			>
				Concurrency Limit
				<ArrowUpDown className="ml-2 h-4 w-4" />
			</Button>
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
				<Button
					variant="ghost"
					onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
					className="h-auto p-0 font-semibold"
				>
					Priority
					<ArrowUpDown className="ml-2 h-4 w-4" />
				</Button>
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
		cell: ({ row }) => <WorkPoolQueueRowActions queue={row.original} />,
		enableSorting: false,
	});

	return columns;
};

// Basic version for backward compatibility
export const workPoolQueuesTableColumns: ColumnDef<WorkPoolQueue>[] =
	createWorkPoolQueuesTableColumns();

// Enhanced version with all features enabled (replaces enhancedWorkPoolQueuesTableColumns)
export const enhancedWorkPoolQueuesTableColumns: ColumnDef<WorkPoolQueue>[] =
	createWorkPoolQueuesTableColumns({
		enableSelection: false,
		enableLateIndicator: true,
	});
