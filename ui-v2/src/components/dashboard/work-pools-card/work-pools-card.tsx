import { useQueries, useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { differenceInSeconds, max, subSeconds } from "date-fns";
import { useMemo } from "react";
import { categorizeError } from "@/api/error-utils";
import {
	buildAverageLatenessFlowRunsQuery,
	buildCountFlowRunsQuery,
	buildFilterFlowRunsQuery,
	type FlowRunsCountFilter,
	type FlowRunsFilter,
} from "@/api/flow-runs";
import { getQueryService } from "@/api/service";
import { buildListWorkPoolQueuesQuery } from "@/api/work-pool-queues";
import {
	buildFilterWorkPoolsQuery,
	buildListWorkPoolWorkersQuery,
	type WorkPool,
} from "@/api/work-pools";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CardErrorState } from "@/components/ui/card-error-state";
import { FlowRunActivityBarChart } from "@/components/ui/flow-run-activity-bar-graph";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { WorkPoolIconText } from "@/components/work-pools/work-pool-icon-text";
import { WorkPoolQueueStatusIcon } from "@/components/work-pools/work-pool-queue-status-icon";
import { WorkPoolStatusIcon } from "@/components/work-pools/work-pool-status-icon";
import { useNow } from "@/hooks/use-now";
import {
	cn,
	formatDateTimeRelative,
	secondsToApproximateString,
} from "@/utils";
import { WorkPoolsCardSkeleton } from "./work-pools-card-skeleton";

type DashboardWorkPoolsCardProps = {
	filter?: {
		startDate?: string;
		endDate?: string;
	};
};

export const DashboardWorkPoolsCard = ({
	filter,
}: DashboardWorkPoolsCardProps) => {
	const workPoolsQuery = useQuery(buildFilterWorkPoolsQuery({ offset: 0 }));

	// Handle error state
	if (workPoolsQuery.isError) {
		return (
			<CardErrorState
				error={categorizeError(
					workPoolsQuery.error,
					"Failed to load work pools",
				)}
				onRetry={() => void workPoolsQuery.refetch()}
				isRetrying={workPoolsQuery.isRefetching}
			/>
		);
	}

	// Handle loading state
	if (workPoolsQuery.isLoading) {
		return <WorkPoolsCardSkeleton />;
	}

	const workPools = workPoolsQuery.data ?? [];
	const activeWorkPools = workPools.filter((workPool) => !workPool.is_paused);

	const showEmptyMsg = workPools && activeWorkPools.length === 0;

	return (
		<Card>
			<CardHeader>
				<CardTitle className="mb-4">Active Work Pools</CardTitle>
			</CardHeader>
			<CardContent>
				<div className="flex flex-col gap-4">
					{activeWorkPools.map((workPool) => (
						<DashboardWorkPoolCard
							key={workPool.id}
							workPool={workPool}
							filter={filter}
						/>
					))}
				</div>
				{showEmptyMsg && (
					<div className="my-8 text-center text-sm text-muted-foreground">
						<p>No active work pools</p>
						<Link
							to="/work-pools"
							className="text-primary underline-offset-4 hover:underline"
						>
							View all work pools
						</Link>
					</div>
				)}
			</CardContent>
		</Card>
	);
};

type DashboardWorkPoolCardProps = {
	workPool: WorkPool;
	filter?: {
		startDate?: string;
		endDate?: string;
	};
};

const DashboardWorkPoolCard = ({
	workPool,
	filter,
}: DashboardWorkPoolCardProps) => {
	// Build flow runs filter for work pool statistics
	const flowRunsFilter: FlowRunsFilter | undefined = useMemo(
		() =>
			filter?.startDate && filter?.endDate
				? {
						sort: "ID_DESC",
						offset: 0,
						work_pools: {
							operator: "and_",
							id: { any_: [workPool.id] },
						},
						flow_runs: {
							operator: "and_",
							start_time: {
								after_: filter.startDate,
								before_: filter.endDate,
							},
						},
					}
				: undefined,
		[filter?.startDate, filter?.endDate, workPool.id],
	);

	return (
		<div className="rounded-xl border border-border">
			<div className="flex flex-wrap items-center gap-4 border-b border-border p-3">
				<div className="flex flex-grow items-center gap-2">
					<WorkPoolIconText workPoolName={workPool.name} />
					<WorkPoolStatusIcon status={workPool.status ?? "READY"} />
				</div>
				<WorkPoolMiniBarChart workPool={workPool} filter={filter} />
				<DashboardWorkPoolFlowRunsTotal
					workPool={workPool}
					filter={flowRunsFilter}
				/>
			</div>
			<dl className="grid grid-cols-2 gap-y-2 p-3 sm:grid-cols-4">
				<DashboardWorkPoolCardDetail label="Polled">
					<WorkPoolLastPolled workPool={workPool} />
				</DashboardWorkPoolCardDetail>

				<DashboardWorkPoolCardDetail label="Work Queues">
					<WorkPoolQueueStatusArray workPool={workPool} />
				</DashboardWorkPoolCardDetail>

				<DashboardWorkPoolCardDetail label="Late runs">
					<div className="inline-flex items-center gap-1">
						<DashboardWorkPoolLateCount
							workPool={workPool}
							filter={flowRunsFilter}
						/>
						<WorkPoolAverageLateTime
							workPool={workPool}
							filter={flowRunsFilter}
						/>
					</div>
				</DashboardWorkPoolCardDetail>

				<DashboardWorkPoolCardDetail label="Completed">
					<WorkPoolFlowRunCompleteness
						workPool={workPool}
						filter={flowRunsFilter}
					/>
				</DashboardWorkPoolCardDetail>
			</dl>
		</div>
	);
};

type DashboardWorkPoolCardDetailProps = {
	label: string;
	children: React.ReactNode;
};

const DashboardWorkPoolCardDetail = ({
	label,
	children,
}: DashboardWorkPoolCardDetailProps) => {
	return (
		<div className="flex flex-col items-center">
			<dt className="text-xs text-muted-foreground">{label}</dt>
			<dd className="mt-1">{children}</dd>
		</div>
	);
};

type WorkPoolLastPolledProps = {
	workPool: WorkPool;
};

const WorkPoolLastPolled = ({ workPool }: WorkPoolLastPolledProps) => {
	const now = useNow({ interval: 1000 });
	const { data: workers } = useQuery(
		buildListWorkPoolWorkersQuery(workPool.name),
	);

	if (!workers) {
		return <span className="text-sm text-muted-foreground">—</span>;
	}

	const lastWorkerHeartbeat =
		workers.length > 0
			? max(
					workers
						.filter((worker) => worker.last_heartbeat_time)
						.map((worker) => new Date(worker.last_heartbeat_time as string)),
				)
			: null;

	if (!lastWorkerHeartbeat) {
		return <span className="text-sm text-muted-foreground">N/A</span>;
	}

	const relativeTime = formatDateTimeRelative(lastWorkerHeartbeat, now);

	return <span className="text-sm">{relativeTime}</span>;
};

type WorkPoolQueueStatusArrayProps = {
	workPool: WorkPool;
};

const MAX_WORK_QUEUES = 50;

const WorkPoolQueueStatusArray = ({
	workPool,
}: WorkPoolQueueStatusArrayProps) => {
	const { data: workPoolQueues } = useQuery(
		buildListWorkPoolQueuesQuery(workPool.name),
	);

	if (!workPoolQueues) {
		return <span className="text-sm text-muted-foreground">—</span>;
	}

	const showTooMany = workPoolQueues.length > MAX_WORK_QUEUES;
	const displayQueues = showTooMany
		? workPoolQueues.slice(0, MAX_WORK_QUEUES)
		: workPoolQueues;

	if (workPoolQueues.length === 0) {
		return <span className="text-sm text-muted-foreground">N/A</span>;
	}

	if (showTooMany) {
		return (
			<span className="text-xs text-muted-foreground">
				Too many to show here.
			</span>
		);
	}

	return (
		<div className="flex min-h-[1.5rem] flex-wrap items-center gap-1">
			{displayQueues.map((queue) => (
				<WorkPoolQueueStatusIcon key={queue.id} queue={queue} />
			))}
		</div>
	);
};

type WorkPoolFlowRunCompletenessProps = {
	workPool: WorkPool;
	filter?: FlowRunsFilter;
};

const WorkPoolFlowRunCompleteness = ({
	workPool,
	filter,
}: WorkPoolFlowRunCompletenessProps) => {
	// Calculate previous period filter by shifting the time window back
	const previousPeriodFilter: FlowRunsFilter | null = useMemo(() => {
		const startTime = filter?.flow_runs?.start_time;
		if (!filter || !startTime?.after_ || !startTime?.before_) {
			return null;
		}

		const startDate = new Date(startTime.after_);
		const endDate = new Date(startTime.before_);
		const timeSpanInSeconds = differenceInSeconds(endDate, startDate);

		return {
			...filter,
			sort: filter.sort ?? "ID_DESC",
			flow_runs: {
				...filter.flow_runs,
				operator: filter.flow_runs?.operator ?? "and_",
				start_time: {
					after_: subSeconds(startDate, timeSpanInSeconds).toISOString(),
					before_: subSeconds(endDate, timeSpanInSeconds).toISOString(),
				},
			},
		};
	}, [filter]);

	// Build filter for all runs (completed, failed, crashed)
	const allRunsFilter: FlowRunsCountFilter = useMemo(
		() => ({
			...filter,
			work_pools: {
				operator: "and_",
				id: { any_: [workPool.id] },
			},
			flow_runs: {
				operator: "and_",
				...filter?.flow_runs,
				state: {
					operator: "and_",
					type: {
						any_: ["COMPLETED", "FAILED", "CRASHED"],
					},
				},
			},
		}),
		[filter, workPool.id],
	);

	// Build filter for completed runs only
	const completedRunsFilter: FlowRunsCountFilter = useMemo(
		() => ({
			...filter,
			work_pools: {
				operator: "and_",
				id: { any_: [workPool.id] },
			},
			flow_runs: {
				operator: "and_",
				...filter?.flow_runs,
				state: {
					operator: "and_",
					type: {
						any_: ["COMPLETED"],
					},
				},
			},
		}),
		[filter, workPool.id],
	);

	// Build filters for previous period
	const previousAllRunsFilter: FlowRunsCountFilter | null = useMemo(
		() =>
			previousPeriodFilter
				? {
						...previousPeriodFilter,
						work_pools: {
							operator: "and_",
							id: { any_: [workPool.id] },
						},
						flow_runs: {
							operator: "and_",
							...previousPeriodFilter?.flow_runs,
							state: {
								operator: "and_",
								type: {
									any_: ["COMPLETED", "FAILED", "CRASHED"],
								},
							},
						},
					}
				: null,
		[previousPeriodFilter, workPool.id],
	);

	const previousCompletedRunsFilter: FlowRunsCountFilter | null = useMemo(
		() =>
			previousPeriodFilter
				? {
						...previousPeriodFilter,
						work_pools: {
							operator: "and_",
							id: { any_: [workPool.id] },
						},
						flow_runs: {
							operator: "and_",
							...previousPeriodFilter?.flow_runs,
							state: {
								operator: "and_",
								type: {
									any_: ["COMPLETED"],
								},
							},
						},
					}
				: null,
		[previousPeriodFilter, workPool.id],
	);

	const { data: allRunsCount } = useQuery(
		buildCountFlowRunsQuery(allRunsFilter, 30000),
	);

	const { data: completedRunsCount } = useQuery(
		buildCountFlowRunsQuery(completedRunsFilter, 30000),
	);

	const { data: previousAllRunsCount } = useQuery({
		...buildCountFlowRunsQuery(previousAllRunsFilter ?? allRunsFilter, 30000),
		enabled: previousAllRunsFilter !== null,
	});

	const { data: previousCompletedRunsCount } = useQuery({
		...buildCountFlowRunsQuery(
			previousCompletedRunsFilter ?? completedRunsFilter,
			30000,
		),
		enabled: previousCompletedRunsFilter !== null,
	});

	if (allRunsCount === undefined || completedRunsCount === undefined) {
		return <span className="text-sm text-muted-foreground">—</span>;
	}

	if (!allRunsCount || allRunsCount === 0) {
		return <span className="text-sm text-muted-foreground">N/A</span>;
	}

	// Calculate percentage with 2 decimal places to match Vue implementation
	const decimal = completedRunsCount / allRunsCount;
	const completePercent = Math.round((decimal + Number.EPSILON) * 10000) / 100;

	// Calculate percent change from previous period
	let percentChange: { change: string; direction: "+" | "-" } | null = null;
	if (
		previousAllRunsCount &&
		previousAllRunsCount > 0 &&
		previousCompletedRunsCount !== undefined
	) {
		const prevDecimal = previousCompletedRunsCount / previousAllRunsCount;
		const previousCompletePercent =
			Math.round((prevDecimal + Number.EPSILON) * 10000) / 100;
		if (previousCompletePercent !== completePercent) {
			const change = Math.abs(completePercent - previousCompletePercent);
			percentChange = {
				change: change.toFixed(1),
				direction: completePercent > previousCompletePercent ? "+" : "-",
			};
		}
	}

	return (
		<span className="inline-flex items-center gap-1">
			<span className="text-sm">{completePercent}%</span>
			{percentChange && (
				<TooltipProvider>
					<Tooltip>
						<TooltipTrigger asChild>
							<span
								className={cn(
									"cursor-help whitespace-nowrap text-xs",
									percentChange.direction === "+"
										? "text-green-600"
										: "text-red-600",
								)}
							>
								{percentChange.direction}
								{percentChange.change}
							</span>
						</TooltipTrigger>
						<TooltipContent>
							<p>
								{percentChange.direction}
								{percentChange.change}% change over time period
							</p>
						</TooltipContent>
					</Tooltip>
				</TooltipProvider>
			)}
		</span>
	);
};

type DashboardWorkPoolLateCountProps = {
	workPool: WorkPool;
	filter?: FlowRunsFilter;
};

const DashboardWorkPoolLateCount = ({
	workPool,
	filter,
}: DashboardWorkPoolLateCountProps) => {
	const lateFlowRunsFilter: FlowRunsCountFilter = useMemo(
		() => ({
			...filter,
			work_pools: {
				operator: "and_",
				name: { any_: [workPool.name] },
			},
			flow_runs: {
				operator: "and_",
				...filter?.flow_runs,
				state: {
					operator: "and_",
					name: {
						any_: ["Late"],
					},
				},
			},
		}),
		[filter, workPool.name],
	);

	const { data: lateFlowRunsCount } = useQuery(
		buildCountFlowRunsQuery(lateFlowRunsFilter, 30000),
	);

	if (lateFlowRunsCount === undefined) {
		return <span className="text-sm text-muted-foreground">—</span>;
	}

	const lateCount = lateFlowRunsCount ?? 0;

	return (
		<span className={cn("text-sm", lateCount < 1 && "text-muted-foreground")}>
			{lateCount}
		</span>
	);
};

type WorkPoolAverageLateTimeProps = {
	workPool: WorkPool;
	filter?: FlowRunsFilter;
};

const WorkPoolAverageLateTime = ({
	workPool,
	filter,
}: WorkPoolAverageLateTimeProps) => {
	const flowRunsFilter: FlowRunsFilter = useMemo(
		() => ({
			...filter,
			sort: "ID_DESC",
			offset: 0,
			work_pools: {
				operator: "and_",
				id: { any_: [workPool.id] },
			},
		}),
		[filter, workPool.id],
	);

	const { data: lateness } = useQuery(
		buildAverageLatenessFlowRunsQuery(flowRunsFilter, 30000),
	);

	if (lateness === undefined || !lateness) {
		return null;
	}

	const formattedDuration = secondsToApproximateString(Math.round(lateness));

	return (
		<span className="whitespace-nowrap text-xs text-muted-foreground">
			({formattedDuration} avg.)
		</span>
	);
};

type DashboardWorkPoolFlowRunsTotalProps = {
	workPool: WorkPool;
	filter?: FlowRunsFilter;
};

const DashboardWorkPoolFlowRunsTotal = ({
	workPool,
	filter,
}: DashboardWorkPoolFlowRunsTotalProps) => {
	const allRunsCountFilter: FlowRunsCountFilter = useMemo(
		() => ({
			...filter,
			work_pools: {
				operator: "and_",
				name: { any_: [workPool.name] },
			},
			flow_runs: {
				operator: "and_",
				...filter?.flow_runs,
				state: {
					operator: "and_",
					type: {
						any_: ["COMPLETED", "FAILED", "CRASHED"],
					},
				},
			},
		}),
		[filter, workPool.name],
	);

	const { data: count } = useQuery(
		buildCountFlowRunsQuery(allRunsCountFilter, 30000),
	);

	return (
		<div className="inline-flex items-end gap-1 text-sm">
			<span className="font-semibold">
				{count !== undefined ? count.toLocaleString() : "—"}
			</span>
			<span className="text-muted-foreground">total</span>
		</div>
	);
};

type WorkPoolMiniBarChartProps = {
	workPool: WorkPool;
	filter?: {
		startDate?: string;
		endDate?: string;
	};
};

const WorkPoolMiniBarChart = ({
	workPool,
	filter,
}: WorkPoolMiniBarChartProps) => {
	const NUMBER_OF_BARS = 24;

	// Build filter for flow runs in this work pool
	const flowRunsBarChartFilter: FlowRunsFilter | undefined = useMemo(
		() =>
			filter?.startDate && filter?.endDate
				? {
						limit: NUMBER_OF_BARS,
						sort: "START_TIME_DESC",
						offset: 0,
						work_pools: {
							operator: "and_",
							id: { any_: [workPool.id] },
						},
						flow_runs: {
							operator: "and_",
							start_time: {
								after_: filter.startDate,
								before_: filter.endDate,
							},
						},
					}
				: undefined,
		[filter?.startDate, filter?.endDate, workPool.id],
	);

	const { data: flowRuns } = useQuery({
		...buildFilterFlowRunsQuery(
			flowRunsBarChartFilter ?? { sort: "ID_DESC", offset: 0 },
			30000,
		),
		enabled: !!flowRunsBarChartFilter,
	});

	// Fetch deployment and flow data for each flow run to enable tooltips
	// Always call useQueries, but with empty array if no flow runs
	const enrichmentQueries = useQueries({
		queries: (flowRuns ?? []).map((flowRun) => ({
			queryKey: [
				"flowRunEnrichment",
				flowRun.id,
				flowRun.deployment_id,
				flowRun.flow_id,
			],
			queryFn: async () => {
				const queryService = await getQueryService();

				const [deploymentRes, flowRes] = await Promise.all([
					flowRun.deployment_id
						? queryService.GET("/deployments/{id}", {
								params: { path: { id: flowRun.deployment_id } },
							})
						: Promise.resolve({ data: null }),
					flowRun.flow_id
						? queryService.GET("/flows/{id}", {
								params: { path: { id: flowRun.flow_id } },
							})
						: Promise.resolve({ data: null }),
				]);

				return {
					deployment: deploymentRes.data ?? null,
					flow: flowRes.data ?? null,
				};
			},
			staleTime: 30000,
		})),
	});

	// Check if all enrichment queries are loaded
	const allEnrichmentsLoaded = enrichmentQueries.every((q) => q.data);

	// Don't render the bar chart if no filter is set
	if (!filter?.startDate || !filter?.endDate) {
		return <div className="h-8 w-48 shrink-0" />;
	}

	// Show loading state while enriching (only if there are flow runs to enrich)
	if (flowRuns && flowRuns.length > 0 && !allEnrichmentsLoaded) {
		return <div className="h-8 w-48 shrink-0" />;
	}

	// Build enriched flow runs with optional deployment/flow data
	// Bars should render for all flow runs; enrichment is only used for tooltips
	const enrichedFlowRuns = (flowRuns ?? []).map((flowRun, index) => {
		const enrichment = enrichmentQueries[index]?.data;
		return {
			...flowRun,
			deployment: enrichment?.deployment ?? undefined,
			flow: enrichment?.flow ?? undefined,
		};
	});

	const startDate = new Date(filter.startDate);
	const endDate = new Date(filter.endDate);

	return (
		<div className="h-8 w-48 shrink-0 flex items-end">
			<FlowRunActivityBarChart
				chartId={`work-pool-${workPool.id}`}
				enrichedFlowRuns={enrichedFlowRuns}
				startDate={startDate}
				endDate={endDate}
				barWidth={6}
				numberOfBars={NUMBER_OF_BARS}
				className="h-full w-full"
			/>
		</div>
	);
};
