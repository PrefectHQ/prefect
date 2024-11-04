import { components } from "@/api/prefect";
import { Checkbox } from "@/components/ui/checkbox";
import { ColumnDef } from "@tanstack/react-table";
import {
	FlowActionMenu,
	FlowActivity,
	FlowDeploymentCount,
	FlowLastRun,
	FlowName,
	FlowNextRun,
} from "./cells";

type Flow = components["schemas"]["Flow"];

export const columns: ColumnDef<Flow>[] = [
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
	},
	{
		accessorKey: "name",
		header: "Name",
		cell: FlowName,
	},
	{
		accessorKey: "lastRuns",
		header: "Last Run",
		cell: FlowLastRun,
	},
	{
		accessorKey: "nextRuns",
		header: "Next Run",
		cell: FlowNextRun,
	},
	{
		accessorKey: "deployments",
		header: "Deployments",
		cell: FlowDeploymentCount,
	},
	{
		accessorKey: "activity",
		header: "Activity",
		cell: FlowActivity,
	},
	{
		id: "actions",
		cell: FlowActionMenu,
	},
];
