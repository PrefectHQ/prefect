import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { subWeeks } from "date-fns";
import { useMemo } from "react";
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
import { Typography } from "../ui/typography";

type Flow = components["schemas"]["Flow"];

export const FlowsTableHeaderCell = ({ content }: { content: string }) => (
	<Typography variant="bodySmall" className="font-bold text-foreground m-2">
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
		<div className="flex items-center gap-1 p-2">
			{lastRun.state_type && (
				<StateIcon
					type={lastRun.state_type}
					name={lastRun.state_name ?? undefined}
				/>
			)}
			<Link to="/runs/flow-run/$id" params={{ id: lastRun.id ?? "" }}>
				<Typography
					variant="bodySmall"
					className="text-blue-700 hover:underline"
					fontFamily="mono"
				>
					{lastRun.name}
				</Typography>
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
		<div className="flex items-center gap-1 p-2">
			{nextRun.state_type && (
				<StateIcon type={nextRun.state_type} name={nextRun.state_name} />
			)}
			<Link to="/runs/flow-run/$id" params={{ id: nextRun.id ?? "" }}>
				<Typography
					variant="bodySmall"
					className="text-blue-700 hover:underline"
					fontFamily="mono"
				>
					{nextRun.name}
				</Typography>
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
		return (
			<Typography
				variant="bodySmall"
				className="text-muted-foreground p-2"
				fontFamily="mono"
			>
				None
			</Typography>
		);
	}

	return (
		<Link
			to="/flows/flow/$id"
			params={{ id: flowId }}
			search={{ tab: "Deployments" }}
		>
			<Typography
				variant="bodySmall"
				className="text-blue-700 hover:underline p-2"
				fontFamily="mono"
			>
				{count} {pluralize(count, "Deployment")}
			</Typography>
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
