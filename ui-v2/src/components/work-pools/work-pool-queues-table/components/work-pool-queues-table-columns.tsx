import { Link } from "@tanstack/react-router";
import type { ColumnDef } from "@tanstack/react-table";
import { ArrowUpDown, HelpCircle } from "lucide-react";
import type { WorkPoolQueue } from "@/api/work-pool-queues";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { WorkPoolQueueStatusBadge } from "@/components/work-pools/work-pool-queue-status-badge";
import { WorkPoolQueueRowActions } from "./work-pool-queue-row-actions";

export const workPoolQueuesTableColumns: ColumnDef<WorkPoolQueue>[] = [
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
	},
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
	{
		accessorKey: "status",
		header: "Status",
		cell: ({ row }) => (
			<WorkPoolQueueStatusBadge status={row.original.status || "READY"} />
		),
	},
	{
		id: "actions",
		header: "",
		cell: ({ row }) => <WorkPoolQueueRowActions queue={row.original} />,
		enableSorting: false,
	},
];
