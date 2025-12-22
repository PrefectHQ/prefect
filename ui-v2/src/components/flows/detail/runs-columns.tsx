import type { ColumnDef } from "@tanstack/react-table";
import { format, parseISO } from "date-fns";
import type { components } from "@/api/prefect";
import { Checkbox } from "@/components/ui/checkbox";
import { StateBadge } from "@/components/ui/state-badge";
import { DeploymentCell, WorkPoolCell } from "./cells";

type FlowRun = components["schemas"]["FlowRunResponse"];

export const columns: ColumnDef<FlowRun>[] = [
	{
		id: "select",
		header: ({ table }) => (
			<Checkbox
				checked={table.getIsAllPageRowsSelected()}
				onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
				aria-label="Select all"
			/>
		),
		cell: ({ row }) => (
			<Checkbox
				checked={row.getIsSelected()}
				onCheckedChange={(value) => row.toggleSelected(!!value)}
				aria-label="Select row"
			/>
		),
		enableSorting: false,
		enableHiding: false,
		maxSize: 10,
	},
	{
		accessorKey: "created",
		header: "Time",
		cell: ({ row }) => (
			<div className="text-xs text-muted-foreground uppercase font-mono">
				{row.original.created &&
					format(parseISO(row.original.created), "MMM dd HH:mm:ss OOOO")}
			</div>
		),
	},
	{
		accessorKey: "state",
		header: "State",
		cell: ({ row }) =>
			row.original.state?.type ? (
				<StateBadge
					type={row.original.state.type}
					name={row.original.state.name}
				/>
			) : null,
	},
	{
		accessorKey: "name",
		header: "Name",
		cell: ({ row }) => row.original.name,
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
		cell: ({ row }) => row.original.work_queue_name,
	},
	{
		accessorKey: "tags",
		header: "Tags",
		cell: ({ row }) =>
			row.original.tags?.map((tag) => (
				<span
					key={tag}
					className="bg-gray-100 text-gray-800 text-xs font-medium px-2 py-0.5 rounded"
				>
					{tag}
				</span>
			)),
	},
	{
		accessorKey: "duration",
		header: "Duration",
		cell: ({ row }) => (
			<span>
				{row.original.estimated_run_time
					? `${row.original.estimated_run_time}s`
					: "-"}
			</span>
		),
	},
];
