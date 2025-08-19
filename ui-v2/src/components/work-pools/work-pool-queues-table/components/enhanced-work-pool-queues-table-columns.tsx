import type { ColumnDef } from "@tanstack/react-table";
import { ArrowUpDown, HelpCircle } from "lucide-react";
import type { WorkPoolQueue } from "@/api/work-pool-queues";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { WorkPoolQueueStatusBadge } from "@/components/work-pools/work-pool-queue-status-badge";
import { WorkPoolQueueToggle } from "@/components/work-pools/work-pool-queue-toggle";
import { QueueNameWithLateIndicator } from "./queue-name-with-late-indicator";
import { WorkPoolQueueRowActions } from "./work-pool-queue-row-actions";

export const enhancedWorkPoolQueuesTableColumns: ColumnDef<WorkPoolQueue>[] = [
	// Checkbox column using Tanstack Table's selection API
	{
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
				disabled={!row.getCanSelect()} // Respects enableRowSelection function
			/>
		),
		enableSorting: false,
		enableHiding: false,
	},

	// Enhanced name column with late flow runs indicator
	{
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
			return <QueueNameWithLateIndicator queue={queue} />;
		},
	},

	// Concurrency limit column
	{
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
	},

	// Priority column
	{
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
	},

	// Status column
	{
		accessorKey: "status",
		header: "Status",
		cell: ({ row }) => (
			<WorkPoolQueueStatusBadge status={row.original.status || "READY"} />
		),
	},

	// Enhanced actions column with toggle
	{
		id: "actions",
		header: "",
		cell: ({ row }) => (
			<div className="flex items-center space-x-2">
				<WorkPoolQueueToggle
					queue={row.original}
					disabled={row.original.name === "default"}
				/>
				<WorkPoolQueueRowActions queue={row.original} />
			</div>
		),
		enableSorting: false,
	},
];
