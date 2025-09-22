import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useDeleteFlowById } from "@/api/flows";
import type { components } from "@/api/prefect";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";
import { cn } from "@/utils";
import { formatDate } from "@/utils/date";
import { Typography } from "../ui/typography";
import {
	deploymentsCountQueryParams,
	getLatestFlowRunsQueryParams,
	getNextFlowRunsQueryParams,
} from "./queries";

type Flow = components["schemas"]["Flow"];

export const FlowsTableHeaderCell = ({ content }: { content: string }) => (
	<Typography variant="bodySmall" className="font-bold text-black m-2">
		{content}
	</Typography>
);
export const FlowName = ({ row }: { row: { original: Flow } }) => {
	if (!row.original.id) return null;

	return (
		<div className="m-2">
			<Link
				to="/flows/flow/$id"
				params={{ id: row.original.id }}
				className="text-blue-700 hover:underline cursor-pointer"
			>
				{row.original.name}
			</Link>
			<Typography
				variant="bodySmall"
				className="text-sm text-muted-foreground"
				fontFamily="mono"
			>
				Created{" "}
				{row.original?.created && formatDate(row.original.created, "dateTime")}
			</Typography>
		</div>
	);
};

export const FlowLastRun = ({ row }: { row: { original: Flow } }) => {
	const { data: flowRun } = useQuery(
		getLatestFlowRunsQueryParams(row.original.id || "", 16, {
			enabled: !!row.original.id,
		}),
	);

	if (!row.original.id || !flowRun?.[0]) return null;
	return (
		<Link to="/runs/flow-run/$id" params={{ id: flowRun[0].id ?? "" }}>
			<Typography
				variant="bodySmall"
				className="text-blue-700 hover:underline p-2"
				fontFamily="mono"
			>
				{flowRun?.[0]?.name}
			</Typography>
		</Link>
	);
};

export const FlowNextRun = ({ row }: { row: { original: Flow } }) => {
	const { data: flowRun } = useQuery(
		getNextFlowRunsQueryParams(row.original.id || "", 16, {
			enabled: !!row.original.id,
		}),
	);

	if (!row.original.id || !flowRun?.[0]) return null;
	return (
		<Link to="/runs/flow-run/$id" params={{ id: flowRun[0].id ?? "" }}>
			<Typography
				variant="bodySmall"
				className="text-blue-700 hover:underline p-2"
				fontFamily="mono"
			>
				{flowRun?.[0]?.name}
			</Typography>
		</Link>
	);
};

export const FlowDeploymentCount = ({ row }: { row: { original: Flow } }) => {
	const { data } = useQuery(
		deploymentsCountQueryParams(row.original.id || "", {
			enabled: !!row.original.id,
		}),
	);
	if (!row.original.id) return null;

	return (
		<Typography
			variant="bodySmall"
			className="text-muted-foreground hover:underline p-2"
			fontFamily="mono"
		>
			{data !== 0 ? data : "None"}
		</Typography>
	);
};

export const FlowActionMenu = ({ row }: { row: { original: Flow } }) => {
	const id = row.original.id;

	const { deleteFlow } = useDeleteFlowById();

	if (!id) {
		return null;
	}
	return (
		<div className="flex justify-end m-2">
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button variant="ghost" className="h-8 w-8 p-0">
						<span className="sr-only">Open menu</span>
						<Icon id="MoreVertical" className="h-4 w-4" />
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent align="end">
					<DropdownMenuLabel>Actions</DropdownMenuLabel>
					<DropdownMenuItem
						onClick={() => void navigator.clipboard.writeText(id)}
					>
						Copy ID
					</DropdownMenuItem>
					<DropdownMenuSeparator />
					<DropdownMenuItem onClick={() => deleteFlow(id)}>
						Delete
					</DropdownMenuItem>
					<DropdownMenuItem>Automate</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
		</div>
	);
};

// TODO: Update this to use the flow run graph from src/components/ui/flow-run-activity-bar-graph
export const FlowActivity = ({ row }: { row: { original: Flow } }) => {
	const { data } = useQuery(
		getLatestFlowRunsQueryParams(row.original.id || "", 16, {
			enabled: !!row.original.id,
		}),
	);
	if (!row.original.id) return null;

	return (
		<div className="flex h-[24px]">
			{Array(16)
				.fill(1)
				?.map((_, index) => (
					<div
						// biome-ignore lint/suspicious/noArrayIndexKey: ok for temporary placeholder component
						key={index}
						className={cn(
							"flex-1 mr-[1px] rounded-full bg-gray-400",
							data?.[index]?.state_type &&
								data?.[index]?.state_type === "COMPLETED" &&
								"bg-green-500",
							data?.[index]?.state_type &&
								data?.[index]?.state_type !== "COMPLETED" &&
								"bg-red-500",
						)}
					/>
				))}
		</div>
	);
};
