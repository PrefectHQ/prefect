import type { ColumnDef } from "@tanstack/react-table";
import type { components } from "@/api/prefect";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";
import { StatusBadge } from "@/components/ui/status-badge";
import { MiniDeploymentActivity } from "./mini-deployment-activity";

type Deployment = components["schemas"]["DeploymentResponse"];

export const columns: ColumnDef<Deployment>[] = [
	{
		accessorKey: "name",
		header: "Name",
		cell: ({ row }) => row.original.name,
	},
	{
		accessorKey: "status",
		header: "Status",
		cell: ({ row }) => {
			const status = row.original.paused
				? "PAUSED"
				: (row.original.status ?? "NOT_READY");
			return <StatusBadge status={status} />;
		},
	},
	{
		accessorKey: "tags",
		header: "Tags",
		cell: ({ row }) => (
			<div className="flex flex-wrap gap-1">
				{row.original.tags?.map((tag) => (
					<span
						key={tag}
						className="bg-gray-100 text-gray-800 text-xs font-medium px-2 py-0.5 rounded"
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
		cell: ({ row }) => (
			<div className="flex flex-col gap-1">
				{row.original.schedules?.map((schedule) => {
					if (
						schedule.schedule &&
						typeof schedule.schedule === "object" &&
						"cron" in schedule.schedule
					) {
						const cronExpression = schedule.schedule.cron;
						return (
							<span key={schedule.id} className="text-xs">
								Cron: {cronExpression}
							</span>
						);
					}
					if (
						schedule.schedule &&
						typeof schedule.schedule === "object" &&
						"interval" in schedule.schedule
					) {
						return (
							<span key={schedule.id} className="text-xs">
								Interval: {schedule.schedule.interval} seconds
							</span>
						);
					}
					if (
						schedule.schedule &&
						typeof schedule.schedule === "object" &&
						"rrule" in schedule.schedule
					) {
						return (
							<span key={schedule.id} className="text-xs">
								RRule: {schedule.schedule.rrule}
							</span>
						);
					}
					return (
						<span key={schedule.id} className="text-xs">
							{JSON.stringify(schedule.schedule)}
						</span>
					);
				})}
			</div>
		),
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
						<Button variant="ghost" className="size-8 p-0">
							<span className="sr-only">Open menu</span>
							<Icon id="MoreHorizontal" className="size-4" />
						</Button>
					</DropdownMenuTrigger>
					<DropdownMenuContent align="end">
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
	},
];
