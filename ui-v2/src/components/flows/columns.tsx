import type { ColumnDef } from "@tanstack/react-table";
import type { components } from "@/api/prefect";
import { Checkbox } from "@/components/ui/checkbox";
import {
	FlowActionMenu,
	FlowActivity,
	FlowDeploymentCount,
	FlowLastRun,
	FlowName,
	FlowNextRun,
	FlowsTableHeaderCell,
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
		maxSize: 10,
	},
	{
		accessorKey: "name",
		header: () => <FlowsTableHeaderCell content="Flow" />,
		cell: FlowName,
	},
	{
		accessorKey: "lastRuns",
		header: () => <FlowsTableHeaderCell content="Last Run" />,
		cell: FlowLastRun,
	},
	{
		accessorKey: "nextRuns",
		header: () => <FlowsTableHeaderCell content="Next Run" />,
		cell: FlowNextRun,
	},
	{
		accessorKey: "deployments",
		header: () => <FlowsTableHeaderCell content="Deployments" />,
		cell: FlowDeploymentCount,
	},
	{
		accessorKey: "activity",
		header: () => <FlowsTableHeaderCell content="Activity" />,
		cell: FlowActivity,
	},
	{
		id: "actions",
		cell: FlowActionMenu,
	},
];
