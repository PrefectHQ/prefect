import { useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { max } from "date-fns";
import {
	buildAverageLatenessFlowRunsQuery,
	buildCountFlowRunsQuery,
	type FlowRunsCountFilter,
	type FlowRunsFilter,
} from "@/api/flow-runs";
import { buildListWorkPoolQueuesQuery } from "@/api/work-pool-queues";
import {
	buildFilterWorkPoolsQuery,
	buildListWorkPoolWorkersQuery,
	type WorkPool,
} from "@/api/work-pools";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FormattedDate } from "@/components/ui/formatted-date";
import { WorkPoolQueueStatusIcon } from "@/components/work-pool-queues/work-pool-queue-status-icon";
import { WorkPoolStatusIcon } from "@/components/work-pools/work-pool-status-icon";
import { cn } from "@/utils";
import { secondsToApproximateString } from "@/utils/date";

type DashboardWorkPoolsCardProps = {
	filter?: {
		startDate?: string;
		endDate?: string;
	};
};

export const DashboardWorkPoolsCard = ({
	filter,
}: DashboardWorkPoolsCardProps) => {
	const { data: workPools } = useSuspenseQuery(
		buildFilterWorkPoolsQuery({ offset: 0 }),
	);

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
	const flowRunsFilter: FlowRunsFilter | undefined = filter
		? {
				sort: "ID_DESC",
				offset: 0,
				work_pools: {
					operator: "and_",
					id: { any_: [workPool.id] },
				},
			}
		: undefined;

	return (
		<div className="rounded-xl border border-border">
			<div className="flex flex-wrap items-center gap-4 border-b border-border p-3">
				<div className="flex flex-grow items-center gap-2">
					<Link
						to="/work-pools/work-pool/$workPoolName"
						params={{ workPoolName: workPool.name }}
						className="text-primary underline-offset-4 hover:underline"
					>
						{workPool.name}
					</Link>
					<WorkPoolStatusIcon status={workPool.status ?? "READY"} />
				</div>
				<div className="h-6 w-1/5 shrink-0">
					{/* FlowRunsBarChart placeholder */}
				</div>
				<div>{/* DashboardWorkPoolFlowRunsTotal placeholder */}</div>
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
		<div>
			<dt className="text-xs font-medium text-muted-foreground">{label}</dt>
			<dd className="mt-1">{children}</dd>
		</div>
	);
};

type WorkPoolLastPolledProps = {
	workPool: WorkPool;
};

const WorkPoolLastPolled = ({ workPool }: WorkPoolLastPolledProps) => {
	const { data: workers } = useSuspenseQuery(
		buildListWorkPoolWorkersQuery(workPool.name),
	);

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

	return <FormattedDate date={lastWorkerHeartbeat} className="text-sm" />;
};

type WorkPoolQueueStatusArrayProps = {
	workPool: WorkPool;
};

const MAX_WORK_QUEUES = 50;

const WorkPoolQueueStatusArray = ({
	workPool,
}: WorkPoolQueueStatusArrayProps) => {
	const { data: workPoolQueues } = useSuspenseQuery(
		buildListWorkPoolQueuesQuery(workPool.name),
	);

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
		<div className="inline-flex min-h-[1.5rem] max-w-full flex-wrap items-center justify-center gap-1">
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
	// Build filter for all runs (completed, failed, crashed)
	const allRunsFilter: FlowRunsCountFilter = {
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
	};

	// Build filter for completed runs only
	const completedRunsFilter: FlowRunsCountFilter = {
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
	};

	const { data: allRunsCount } = useSuspenseQuery(
		buildCountFlowRunsQuery(allRunsFilter, 30000),
	);

	const { data: completedRunsCount } = useSuspenseQuery(
		buildCountFlowRunsQuery(completedRunsFilter, 30000),
	);

	if (!allRunsCount || allRunsCount === 0) {
		return <span className="text-sm text-muted-foreground">N/A</span>;
	}

	const completePercent = Math.round((completedRunsCount / allRunsCount) * 100);

	return (
		<span className="inline-flex items-center gap-1">
			<span className="text-sm">{completePercent}%</span>
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
	const lateFlowRunsFilter: FlowRunsCountFilter = {
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
	};

	const { data: lateFlowRunsCount } = useSuspenseQuery(
		buildCountFlowRunsQuery(lateFlowRunsFilter, 30000),
	);

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
}: WorkPoolAverageLateTimeProps) => {
	const flowRunsFilter: FlowRunsFilter = {
		sort: "ID_DESC",
		offset: 0,
		work_pools: {
			operator: "and_",
			id: { any_: [workPool.id] },
		},
	};

	const { data: lateness } = useSuspenseQuery(
		buildAverageLatenessFlowRunsQuery(flowRunsFilter, 30000),
	);

	if (!lateness) {
		return null;
	}

	return (
		<span className="whitespace-nowrap text-xs">
			({secondsToApproximateString(lateness)} avg.)
		</span>
	);
};
