import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { subWeeks } from "date-fns";
import { useMemo } from "react";
import { toast } from "sonner";
import { buildFilterFlowRunsQuery } from "@/api/flow-runs";
import {
	buildDeploymentsCountByFlowQuery,
	buildNextRunsByFlowQuery,
	useDeleteFlowById,
} from "@/api/flows";
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
import { FlowRunActivityBarChart } from "@/components/ui/flow-run-activity-bar-graph";
import { Icon } from "@/components/ui/icons";
import { StateIcon } from "@/components/ui/state-badge";
import { pluralize } from "@/utils";
import { formatDate } from "@/utils/date";

type Flow = components["schemas"]["Flow"];

export const FlowName = ({ row }: { row: { original: Flow } }) => {
	if (!row.original.id) return null;

	return (
		<div className="flex flex-col pl-4">
			<Link
				to="/flows/flow/$id"
				params={{ id: row.original.id }}
				className="text-sm font-medium truncate"
				title={row.original.name}
			>
				{row.original.name}
			</Link>
			<span className="text-xs text-muted-foreground">
				Created{" "}
				{row.original?.created && formatDate(row.original.created, "dateTime")}
			</span>
		</div>
	);
};

export const FlowLastRun = ({ row }: { row: { original: Flow } }) => {
	const flowId = row.original.id;
	const { data: flowRuns } = useQuery({
		...buildFilterFlowRunsQuery({
			flows: { operator: "and_", id: { any_: [flowId ?? ""] } },
			flow_runs: {
				operator: "and_",
				start_time: { is_null_: false },
			},
			offset: 0,
			limit: 1,
			sort: "START_TIME_DESC",
		}),
		enabled: !!flowId,
	});

	const lastRun = flowRuns?.[0];
	if (!flowId || !lastRun) return null;

	return (
		<div className="flex items-center gap-1">
			{lastRun.state_type && (
				<StateIcon
					type={lastRun.state_type}
					name={lastRun.state_name ?? undefined}
				/>
			)}
			<Link to="/runs/flow-run/$id" params={{ id: lastRun.id ?? "" }}>
				<span className="text-sm text-blue-700 hover:underline">
					{lastRun.name}
				</span>
			</Link>
		</div>
	);
};

export const FlowNextRun = ({ row }: { row: { original: Flow } }) => {
	const flowId = row.original.id;
	const { data: nextRunsMap } = useQuery(
		buildNextRunsByFlowQuery(flowId ? [flowId] : [], { enabled: !!flowId }),
	);

	const nextRun = flowId ? nextRunsMap?.[flowId] : null;
	if (!flowId || !nextRun) return null;

	return (
		<div className="flex items-center gap-1">
			{nextRun.state_type && (
				<StateIcon type={nextRun.state_type} name={nextRun.state_name} />
			)}
			<Link to="/runs/flow-run/$id" params={{ id: nextRun.id ?? "" }}>
				<span className="text-sm text-blue-700 hover:underline">
					{nextRun.name}
				</span>
			</Link>
		</div>
	);
};

export const FlowDeploymentCount = ({ row }: { row: { original: Flow } }) => {
	const flowId = row.original.id;
	const { data: countsMap } = useQuery(
		buildDeploymentsCountByFlowQuery(flowId ? [flowId] : [], {
			enabled: !!flowId,
		}),
	);
	if (!flowId) return null;

	const count = countsMap?.[flowId] ?? 0;

	if (count === 0) {
		return <span className="text-sm text-muted-foreground">None</span>;
	}

	return (
		<Link
			to="/flows/flow/$id"
			params={{ id: flowId }}
			search={{ tab: "deployments" }}
		>
			<span className="text-sm text-blue-700 hover:underline">
				{count} {pluralize(count, "Deployment")}
			</span>
		</Link>
	);
};

export const FlowActionMenu = ({ row }: { row: { original: Flow } }) => {
	const id = row.original.id;

	const { deleteFlow } = useDeleteFlowById();

	if (!id) {
		return null;
	}
	return (
		<div className="flex justify-end">
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
						onClick={() => {
							void navigator.clipboard.writeText(id);
							toast.success("ID copied");
						}}
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

const NUMBER_OF_ACTIVITY_BARS = 16;

export const FlowActivity = ({ row }: { row: { original: Flow } }) => {
	const flowId = row.original.id;

	const { startDate, endDate } = useMemo((): {
		startDate: Date;
		endDate: Date;
	} => {
		const now = new Date();
		return {
			startDate: subWeeks(now, 1),
			endDate: now,
		};
	}, []);

	const { data: flowRuns } = useQuery({
		...buildFilterFlowRunsQuery({
			flows: { operator: "and_", id: { any_: [flowId ?? ""] } },
			flow_runs: {
				operator: "and_",
				start_time: { is_null_: false },
			},
			offset: 0,
			limit: NUMBER_OF_ACTIVITY_BARS,
			sort: "START_TIME_DESC",
		}),
		enabled: !!flowId,
	});

	if (!flowId) return null;

	return (
		<FlowRunActivityBarChart
			chartId={`flow-activity-${flowId}`}
			enrichedFlowRuns={flowRuns ?? []}
			startDate={startDate}
			endDate={endDate}
			numberOfBars={NUMBER_OF_ACTIVITY_BARS}
			className="h-[24px] w-[140px]"
		/>
	);
};
