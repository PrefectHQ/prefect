import { components } from "@/api/prefect";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { format, parseISO } from "date-fns";
import { MoreVerticalIcon } from "lucide-react";
import {
	deploymentsCountQueryParams,
	getLatestFlowRunsQueryParams,
	getNextFlowRunsQueryParams,
} from "./queries";

type Flow = components["schemas"]["Flow"];

export const FlowName = ({ row }: { row: { original: Flow } }) => {
	if (!row.original.id) return null;

	return (
		<div>
			<Link
				to="/flows/flow/$id"
				params={{ id: row.original.id }}
				className="text-primary hover:underline cursor-pointer"
			>
				{row.original.name}
			</Link>
			<div className="text-sm text-muted-foreground">
				Created{" "}
				{row.original?.created &&
					format(parseISO(row.original.created), "yyyy-MM-dd")}
			</div>
		</div>
	);
};

export const FlowLastRun = ({ row }: { row: { original: Flow } }) => {
	const { data } = useQuery(
		getLatestFlowRunsQueryParams(row.original.id || "", 16, {
			enabled: !!row.original.id,
		}),
	);

	if (!row.original.id) return null;
	return JSON.stringify(data?.[0]?.name);
};

export const FlowNextRun = ({ row }: { row: { original: Flow } }) => {
	const { data } = useQuery(
		getNextFlowRunsQueryParams(row.original.id || "", 16, {
			enabled: !!row.original.id,
		}),
	);

	if (!row.original.id) return null;
	return JSON.stringify(data?.[0]?.name);
};

export const FlowDeploymentCount = ({ row }: { row: { original: Flow } }) => {
	const { data } = useQuery(
		deploymentsCountQueryParams(row.original.id || "", {
			enabled: !!row.original.id,
		}),
	);
	if (!row.original.id) return null;

	return data;
};

export const FlowActionMenu = ({ row }: { row: { original: Flow } }) => {
	const id = row.original.id;
	if (!id) {
		return null;
	}
	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button variant="ghost" className="h-8 w-8 p-0">
					<span className="sr-only">Open menu</span>
					<MoreVerticalIcon className="h-4 w-4" />
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
				<DropdownMenuItem>Delete</DropdownMenuItem>
				<DropdownMenuItem>Automate</DropdownMenuItem>
			</DropdownMenuContent>
		</DropdownMenu>
	);
};

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
