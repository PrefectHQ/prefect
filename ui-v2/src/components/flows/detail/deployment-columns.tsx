import { Link } from "@tanstack/react-router";
import type { components } from "@/api/prefect";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";
import { ScheduleBadgeGroup } from "@/components/ui/schedule-badge";
import { StatusBadge } from "@/components/ui/status-badge";
import type { ColumnDef } from "@/lib/tanstack-table";
import { MiniDeploymentActivity } from "./mini-deployment-activity";

type Deployment = components["schemas"]["DeploymentResponse"];

export const columns: ColumnDef<Deployment>[] = [
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
		maxSize: 20,
		minSize: 20,
	},
	{
		accessorKey: "name",
		header: "Name",
		cell: ({ row }) => (
			<Link
				to="/deployments/deployment/$id"
				params={{ id: row.original.id }}
				className="text-sm font-medium truncate text-link hover:text-link-hover"
				title={row.original.name}
			>
				{row.original.name}
			</Link>
		),
	},
	{
		accessorKey: "status",
		header: "Status",
		cell: ({ row }) =>
			row.original.status ? (
				<StatusBadge status={row.original.status} />
			) : (
				<span className="text-muted-foreground text-sm">None</span>
			),
	},
	{
		accessorKey: "tags",
		header: "Tags",
		cell: ({ row }) => (
			<div className="flex flex-wrap gap-1">
				{row.original.tags?.map((tag) => (
					<span
						key={tag}
						className="bg-secondary text-secondary-foreground text-xs font-medium px-2 py-0.5 rounded"
					>
						{tag}
					</span>
				))}
			</div>
		),
	},
	{
		accessorKey: "schedules",
		header: "Schedules",
		cell: ({ row }) => {
			const schedules = row.original.schedules;
			if (!schedules || schedules.length === 0) return null;
			return <ScheduleBadgeGroup schedules={schedules} />;
		},
		size: 150,
	},
	{
		accessorKey: "activity",
		header: "Activity",
		cell: ({ row }) => {
			if (!row.original.id) return null;
			return <MiniDeploymentActivity deploymentId={row.original.id} />;
		},
	},
	{
		id: "actions",
		cell: ({ row }) => {
			if (!row.original.id) return null;

			return (
				<DropdownMenu>
					<DropdownMenuTrigger asChild>
						<Button variant="ghost" size="icon">
							<span className="sr-only">Open menu</span>
							<Icon id="MoreHorizontal" className="size-4" />
						</Button>
					</DropdownMenuTrigger>
					<DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
						<DropdownMenuItem
							onClick={() =>
								void navigator.clipboard.writeText(row.original.id)
							}
						>
							Copy ID
						</DropdownMenuItem>
					</DropdownMenuContent>
				</DropdownMenu>
			);
		},
		minSize: 30,
		maxSize: 30,
	},
];
