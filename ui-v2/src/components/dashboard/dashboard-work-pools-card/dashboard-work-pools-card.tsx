import { useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { formatDistanceToNowStrict, subSeconds } from "date-fns";
import { secondsInWeek } from "date-fns/constants";
import { type ReactNode, useMemo } from "react";
import {
	buildCountFlowRunsQuery,
	buildFilterFlowRunsQuery,
	type FlowRunsCountFilter,
	type FlowRunsFilter,
} from "@/api/flow-runs";
import type { components } from "@/api/prefect";
import { buildListWorkPoolQueuesQuery } from "@/api/work-pool-queues";
import type { WorkPool } from "@/api/work-pools";
import {
	buildFilterWorkPoolsQuery,
	buildListWorkPoolWorkersQuery,
} from "@/api/work-pools";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FlowRunActivityBarChart } from "@/components/ui/flow-run-activity-bar-graph";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/utils/css";

// Types
type DashboardFilter = {
	range: {
		start: string;
		end: string;
	};
	flow_runs?: {
		start_time_before?: Date;
		start_time_after?: Date;
	};
};

type EnrichedFlowRun = components["schemas"]["FlowRun"] & {
	deployment: components["schemas"]["DeploymentResponse"];
	flow: components["schemas"]["Flow"];
};
// Supporting Components

/**
 * StatisticKeyValue - Simple key/value display component
 */
const StatisticKeyValue = ({
	label,
	value,
	className,
}: {
	label: string;
	value: number;
	className?: string;
}) => (
	<div
		className={cn("text-center", className)}
		data-testid="statistic-key-value"
	>
		<div className="text-lg font-semibold">{value}</div>
		<div className="text-xs text-muted-foreground">{label}</div>
	</div>
);

/**
 * DashboardWorkPoolCardDetail - Wrapper for label/value pairs using definition list structure
 */
const DashboardWorkPoolCardDetail = ({
	label,
	children,
}: {
	label: string;
	children: ReactNode;
}) => (
	<div
		className="text-center max-w-full flex flex-col"
		data-testid="dashboard-work-pool-card-detail"
	>
		<dt className="text-xs text-muted-foreground dashboard-work-pool-card-detail__label">
			{label}
		</dt>
		<dd className="dashboard-work-pool-card-detail__value flex-1 flex items-center justify-center">
			{children}
		</dd>
	</div>
);

/**
 * WorkPoolLastPolled - Shows when work pool was last polled
 */
export const WorkPoolLastPolled = ({ workPool }: { workPool: WorkPool }) => {
	// Fetch workers to get the most recent heartbeat time
	const { data: workers = [] } = useSuspenseQuery(
		buildListWorkPoolWorkersQuery(workPool.name),
	);

	// Find the most recent worker heartbeat
	const lastHeartbeat = useMemo(() => {
		const heartbeats = workers
			.map((worker) => worker.last_heartbeat_time)
			.filter((time): time is string => Boolean(time))
			.map((time) => new Date(time));

		if (heartbeats.length === 0) {
			return null;
		}

		return heartbeats.reduce((latest, current) =>
			current > latest ? current : latest,
		);
	}, [workers]);

	if (!lastHeartbeat) {
		return <span className="text-muted-foreground">Never</span>;
	}

	return (
		<span className="text-sm">
			{formatDistanceToNowStrict(lastHeartbeat, { addSuffix: true })}
		</span>
	);
};

/**
 * Simple status circle indicator
 */
const StatusCircle = ({
	status,
	size = "sm",
}: {
	status: "ready" | "paused" | "not_ready";
	size?: "sm" | "md";
}) => {
	const getStatusColor = () => {
		switch (status) {
			case "ready":
				return "bg-green-500";
			case "paused":
				return "bg-yellow-500";
			case "not_ready":
				return "bg-red-500";
			default:
				return "bg-gray-400";
		}
	};

	const sizeClass = size === "md" ? "h-3 w-3" : "h-2 w-2";

	return (
		<div
			className={cn("rounded-full", getStatusColor(), sizeClass)}
			data-testid="status-circle"
		/>
	);
};

/**
 * WorkPoolQueueStatusArray - Shows status circles for work pool queues
 */
const WorkPoolQueueStatusArray = ({ workPool }: { workPool: WorkPool }) => {
	const { data: queues = [] } = useSuspenseQuery(
		buildListWorkPoolQueuesQuery(workPool.name),
	);

	return (
		<div className="flex flex-wrap gap-1 justify-center items-center pt-1">
			{queues.map((queue) => {
				// Determine queue status based on is_paused and other factors
				let status: "ready" | "paused" | "not_ready" = "not_ready";
				if (queue.is_paused) {
					status = "paused";
				} else if (queue.status === "READY") {
					status = "ready";
				}

				return <StatusCircle key={queue.id} status={status} />;
			})}
		</div>
	);
};

/**
 * FlowRunsBarChart - Mini bar chart showing flow run activity using the existing FlowRunActivityBarChart
 */
const FlowRunsBarChart = ({
	workPool,
	filter,
	mini = false,
}: {
	workPool: WorkPool;
	filter: DashboardFilter;
	mini?: boolean;
}) => {
	// Create filter for flow runs with enriched data (includes deployment and flow)
	const numberOfBars = mini ? 12 : 20;
	const flowRunsFilter: FlowRunsFilter = useMemo(() => {
		const baseFilter = {
			sort: "START_TIME_DESC",
			offset: 0,
			limit: numberOfBars,
			work_pools: {
				operator: "and_",
				name: {
					any_: [workPool.name],
				},
			},
		} as FlowRunsFilter;

		// Add time filtering if provided
		if (
			filter.flow_runs?.start_time_after ||
			filter.flow_runs?.start_time_before
		) {
			baseFilter.flow_runs = {
				operator: "and_",
				start_time: {},
			};
			if (
				filter.flow_runs.start_time_after &&
				baseFilter.flow_runs?.start_time
			) {
				baseFilter.flow_runs.start_time.after_ =
					filter.flow_runs.start_time_after.toISOString();
			}
			if (
				filter.flow_runs.start_time_before &&
				baseFilter.flow_runs?.start_time
			) {
				baseFilter.flow_runs.start_time.before_ =
					filter.flow_runs.start_time_before.toISOString();
			}
		}

		return baseFilter;
	}, [workPool.name, numberOfBars, filter.flow_runs]);

	const { data: flowRuns = [] } = useSuspenseQuery(
		buildFilterFlowRunsQuery(flowRunsFilter, 30000),
	);

	// Transform flow runs to enriched format expected by FlowRunActivityBarChart
	const enrichedFlowRuns = useMemo(() => {
		// Create minimal enriched flow runs for the chart
		return flowRuns.map((run) => {
			const enrichedRun: EnrichedFlowRun = {
				...run,
				deployment: {
					id: run.deployment_id || "unknown-deployment",
					name: "Unknown Deployment",
					flow_id: run.flow_id,
				} as components["schemas"]["DeploymentResponse"],
				flow: {
					id: run.flow_id || "unknown-flow",
					name: "Unknown Flow",
				} as components["schemas"]["Flow"],
			};
			return enrichedRun;
		});
	}, [flowRuns]);

	return (
		<div
			className={cn(
				"flex items-end",
				mini && "w-1/5 shrink-0 h-6 dashboard-work-pool-card__mini-bars",
			)}
			data-testid="flow-runs-bar-chart"
		>
			<FlowRunActivityBarChart
				chartId={`work-pool-${workPool.id}`}
				enrichedFlowRuns={enrichedFlowRuns}
				startDate={subSeconds(new Date(), secondsInWeek)}
				endDate={new Date()}
				numberOfBars={numberOfBars}
				barWidth={mini ? 4 : 8}
				className={cn("w-full overflow-visible", mini ? "h-8" : "h-32")}
			/>
		</div>
	);
};

/**
 * DashboardWorkPoolFlowRunsTotal - Shows total count of flow runs
 */
const DashboardWorkPoolFlowRunsTotal = ({
	workPool,
	filter,
}: {
	workPool: WorkPool;
	filter?: DashboardFilter;
}) => {
	const allRunsCountFilter: FlowRunsCountFilter = useMemo(() => {
		const baseFilter = {
			work_pools: {
				operator: "and_",
				name: {
					any_: [workPool.name],
				},
			},
		} as FlowRunsCountFilter;

		// Add time filtering if provided
		if (
			filter?.flow_runs?.start_time_after ||
			filter?.flow_runs?.start_time_before
		) {
			baseFilter.flow_runs = {
				operator: "and_",
				start_time: {},
			};
			if (
				filter.flow_runs.start_time_after &&
				baseFilter.flow_runs?.start_time
			) {
				baseFilter.flow_runs.start_time.after_ =
					filter.flow_runs.start_time_after.toISOString();
			}
			if (
				filter.flow_runs.start_time_before &&
				baseFilter.flow_runs?.start_time
			) {
				baseFilter.flow_runs.start_time.before_ =
					filter.flow_runs.start_time_before.toISOString();
			}
		}

		return baseFilter;
	}, [workPool.name, filter?.flow_runs]);

	const { data: count } = useSuspenseQuery(
		buildCountFlowRunsQuery(allRunsCountFilter, 30000),
	);

	return (
		<StatisticKeyValue
			className="dashboard-work-pool-flow-runs-total"
			label="total"
			value={count ?? 0}
		/>
	);
};

/**
 * DashboardWorkPoolLateCount - Shows count of late flow runs
 */
const DashboardWorkPoolLateCount = ({
	workPool,
	filter,
}: {
	workPool: WorkPool;
	filter?: DashboardFilter;
}) => {
	const lateFlowRunsFilter: FlowRunsCountFilter = useMemo(() => {
		const baseFilter = {
			work_pools: {
				operator: "and_",
				name: {
					any_: [workPool.name],
				},
			},
			flow_runs: {
				operator: "and_",
				state: {
					operator: "and_",
					name: {
						any_: ["Late"],
					},
				},
			},
		} as FlowRunsCountFilter;

		// Add time filtering if provided
		if (
			filter?.flow_runs?.start_time_after ||
			filter?.flow_runs?.start_time_before
		) {
			if (baseFilter.flow_runs) {
				baseFilter.flow_runs.start_time = {};
				if (
					filter.flow_runs.start_time_after &&
					baseFilter.flow_runs.start_time
				) {
					baseFilter.flow_runs.start_time.after_ =
						filter.flow_runs.start_time_after.toISOString();
				}
				if (
					filter.flow_runs.start_time_before &&
					baseFilter.flow_runs.start_time
				) {
					baseFilter.flow_runs.start_time.before_ =
						filter.flow_runs.start_time_before.toISOString();
				}
			}
		}

		return baseFilter;
	}, [workPool.name, filter?.flow_runs]);

	const { data: count } = useSuspenseQuery(
		buildCountFlowRunsQuery(lateFlowRunsFilter, 30000),
	);

	const lateFlowRunsCount = count ?? 0;

	return (
		<span
			className={cn(
				"work-pool-late-count",
				lateFlowRunsCount < 1 &&
					"work-pool-late-count--zero text-muted-foreground",
			)}
			data-testid="work-pool-late-count"
		>
			{lateFlowRunsCount}
		</span>
	);
};

/**
 * DashboardWorkPoolFlowRunCompleteness - Shows completion percentage with trend
 */
const DashboardWorkPoolFlowRunCompleteness = ({
	workPool,
	filter,
}: {
	workPool: WorkPool;
	filter?: DashboardFilter;
}) => {
	// Current period filter
	const workQueueFilter: FlowRunsFilter = useMemo(() => {
		const baseFilter = {
			sort: "START_TIME_DESC",
			offset: 0,
			limit: 100,
			work_pools: {
				operator: "and_",
				name: {
					any_: [workPool.name],
				},
			},
		} as FlowRunsFilter;

		// Add time filtering if provided
		if (
			filter?.flow_runs?.start_time_after ||
			filter?.flow_runs?.start_time_before
		) {
			baseFilter.flow_runs = {
				operator: "and_",
				start_time: {},
			};
			if (
				filter.flow_runs.start_time_after &&
				baseFilter.flow_runs?.start_time
			) {
				baseFilter.flow_runs.start_time.after_ =
					filter.flow_runs.start_time_after.toISOString();
			}
			if (
				filter.flow_runs.start_time_before &&
				baseFilter.flow_runs?.start_time
			) {
				baseFilter.flow_runs.start_time.before_ =
					filter.flow_runs.start_time_before.toISOString();
			}
		}

		return baseFilter;
	}, [workPool.name, filter?.flow_runs]);

	// For now, skip the previous period calculation to simplify implementation
	// Previous period filter would need proper date handling from the dashboard filter

	// Get current period flow runs
	const { data: currentFlowRuns = [] } = useSuspenseQuery(
		buildFilterFlowRunsQuery(workQueueFilter, 30000),
	);

	// Get previous period flow runs if filter exists - simplified for now
	const { data: previousFlowRuns = [] } = useSuspenseQuery(
		buildFilterFlowRunsQuery({ sort: "ID_DESC", offset: 0, limit: 0 }, 30000),
	);

	// Calculate completion percentages
	const completePercent = useMemo(() => {
		if (currentFlowRuns.length === 0) return null;

		const completedRuns = currentFlowRuns.filter(
			(run) => run.state_type === "COMPLETED",
		).length;

		return Math.round((completedRuns / currentFlowRuns.length) * 100);
	}, [currentFlowRuns]);

	const previousCompletePercent = useMemo(() => {
		if (previousFlowRuns.length === 0) return null;

		const completedRuns = previousFlowRuns.filter(
			(run) => run.state_type === "COMPLETED",
		).length;

		return Math.round((completedRuns / previousFlowRuns.length) * 100);
	}, [previousFlowRuns]);

	// Calculate percentage change
	const percentChange = useMemo(() => {
		if (
			!previousCompletePercent ||
			!completePercent ||
			previousCompletePercent === completePercent
		) {
			return undefined;
		}

		const changePercent = completePercent - previousCompletePercent;

		return {
			change: Math.abs(changePercent).toFixed(1),
			direction: changePercent > 0 ? "+" : "-",
		};
	}, [completePercent, previousCompletePercent]);

	if (!completePercent) {
		return (
			<span
				className="dashboard-work-pool-flow-runs-completeness__none text-muted-foreground"
				data-testid="dashboard-work-pool-flow-runs-completeness"
			>
				N/A
			</span>
		);
	}

	return (
		<span
			className="inline-flex gap-1 items-center dashboard-work-pool-flow-runs-completeness"
			data-testid="dashboard-work-pool-flow-runs-completeness"
		>
			<span>{completePercent}%</span>
			{percentChange && (
				<TooltipProvider>
					<Tooltip>
						<TooltipTrigger asChild>
							<span
								className={cn(
									"cursor-help text-xs whitespace-nowrap dashboard-work-pool-flow-runs-completeness__difference",
									percentChange.direction === "-"
										? "dashboard-work-pool-flow-runs-completeness__difference--negative text-red-600"
										: "dashboard-work-pool-flow-runs-completeness__difference--positive text-green-600",
								)}
							>
								{percentChange.direction}
								{percentChange.change}
							</span>
						</TooltipTrigger>
						<TooltipContent>
							<p>
								Percent change over time period: {percentChange.direction}
								{percentChange.change}%
							</p>
						</TooltipContent>
					</Tooltip>
				</TooltipProvider>
			)}
		</span>
	);
};

/**
 * DashboardWorkPoolCard - Individual work pool card component
 */
const DashboardWorkPoolCard = ({
	workPool,
	filter,
}: {
	workPool: WorkPool;
	filter: DashboardFilter;
}) => {
	return (
		<div
			className="border border-default rounded-lg dashboard-work-pool-card"
			data-testid={`work-pool-card-${workPool.id}`}
		>
			{/* Header */}
			<div
				className="flex items-center gap-4 p-3 border-b border-default flex-wrap dashboard-work-pool-card__header"
				data-testid="dashboard-work-pool-card-header"
			>
				<div
					className="flex flex-grow items-center gap-2 dashboard-work-pool-card__name"
					data-testid="dashboard-work-pool-card-name"
				>
					<Link
						to="/work-pools/work-pool/$workPoolName"
						params={{ workPoolName: workPool.name }}
					>
						{workPool.name}
					</Link>
					<StatusCircle
						status={
							workPool.is_paused
								? "paused"
								: workPool.status === "READY"
									? "ready"
									: "not_ready"
						}
						size="md"
					/>
				</div>
				<FlowRunsBarChart workPool={workPool} filter={filter} mini />
				<DashboardWorkPoolFlowRunsTotal workPool={workPool} filter={filter} />
			</div>

			{/* Details Grid */}
			<dl
				className="p-3 grid grid-cols-2 sm:grid-cols-4 gap-y-2 dashboard-work-pool-card__details"
				data-testid="dashboard-work-pool-card-details"
			>
				<DashboardWorkPoolCardDetail
					label="Polled"
					data-testid="dashboard-work-pool-card-detail-polled"
				>
					<WorkPoolLastPolled workPool={workPool} />
				</DashboardWorkPoolCardDetail>

				<DashboardWorkPoolCardDetail
					label="Work Queues"
					data-testid="dashboard-work-pool-card-detail-work-queues"
				>
					<WorkPoolQueueStatusArray workPool={workPool} />
				</DashboardWorkPoolCardDetail>

				<DashboardWorkPoolCardDetail
					label="Late runs"
					data-testid="dashboard-work-pool-card-detail-late-runs"
				>
					<DashboardWorkPoolLateCount workPool={workPool} filter={filter} />
				</DashboardWorkPoolCardDetail>

				<DashboardWorkPoolCardDetail
					label="Completed"
					data-testid="dashboard-work-pool-card-detail-completed"
				>
					<DashboardWorkPoolFlowRunCompleteness
						workPool={workPool}
						filter={filter}
					/>
				</DashboardWorkPoolCardDetail>
			</dl>
		</div>
	);
};

/**
 * DashboardWorkPoolsCard - Main container component
 */
export const DashboardWorkPoolsCard = ({
	filter,
}: {
	filter: DashboardFilter;
}) => {
	const { data: workPools = [] } = useSuspenseQuery(
		buildFilterWorkPoolsQuery({ offset: 0 }, { enabled: true }),
	);

	// Filter to show only active (non-paused) work pools
	const activeWorkPools = workPools.filter((workPool) => !workPool.is_paused);

	const showEmptyMsg = workPools.length > 0 && activeWorkPools.length === 0;

	return (
		<Card
			className="dashboard-work-pools-card"
			data-testid="dashboard-work-pools-card"
		>
			<CardHeader className="dashboard-work-pools-card__heading">
				<CardTitle>Work Pools</CardTitle>
			</CardHeader>
			<CardContent>
				{activeWorkPools.length > 0 ? (
					<div
						className="flex flex-col gap-4 dashboard-work-pools-card__list"
						data-testid="work-pools-list"
					>
						{activeWorkPools.map((workPool) => (
							<DashboardWorkPoolCard
								key={workPool.id}
								workPool={workPool}
								filter={filter}
							/>
						))}
					</div>
				) : (
					<div className="text-center text-muted-foreground text-sm my-8 dashboard-work-pools-card__empty">
						{showEmptyMsg ? (
							<>
								<p>No active work pools available</p>
								<Link to="/work-pools" className="text-primary hover:underline">
									View all work pools
								</Link>
							</>
						) : workPools.length === 0 ? (
							<>
								<p>No active work pools available</p>
								<Link to="/work-pools" className="text-primary hover:underline">
									View all work pools
								</Link>
							</>
						) : null}
					</div>
				)}
			</CardContent>
		</Card>
	);
};
