import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { Suspense, useCallback, useMemo } from "react";
import { z } from "zod";
import { buildPaginateFlowRunsQuery, type FlowRun } from "@/api/flow-runs";
import { buildListSavedSearchesQuery } from "@/api/saved-searches";
import { buildPaginateTaskRunsQuery, type TaskRun } from "@/api/task-runs";
import {
	FlowRunsPagination,
	type PaginationState,
} from "@/components/flow-runs/flow-runs-list";
import {
	ONE_WEEK_FILTER,
	SavedFilters,
	type SavedFiltersFilter,
} from "@/components/saved-filters";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";
import { Card } from "@/components/ui/card";
import {
	LayoutWell,
	LayoutWellContent,
	LayoutWellHeader,
} from "@/components/ui/layout-well";
import { Skeleton } from "@/components/ui/skeleton";
import { StateBadge } from "@/components/ui/state-badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Typography } from "@/components/ui/typography";

const searchParams = z.object({
	tab: z.enum(["flow-runs", "task-runs"]).optional().default("flow-runs"),
	page: z.number().int().positive().optional().default(1),
	limit: z.number().int().positive().max(100).optional().default(10),
	sort: z
		.enum([
			"START_TIME_DESC",
			"START_TIME_ASC",
			"EXPECTED_START_TIME_DESC",
			"EXPECTED_START_TIME_ASC",
			"NAME_ASC",
			"NAME_DESC",
		])
		.optional()
		.default("START_TIME_DESC"),
	states: z.array(z.string()).optional(),
	flows: z.array(z.string()).optional(),
	tags: z.array(z.string()).optional(),
	deployments: z.array(z.string()).optional(),
	workPools: z.array(z.string()).optional(),
	workQueues: z.array(z.string()).optional(),
	rangeSeconds: z.number().optional().default(-604800),
});

export const Route = createFileRoute("/runs/")({
	validateSearch: zodValidator(searchParams),
	component: RouteComponent,
	loaderDeps: ({ search }) => search,
	loader: ({ deps: search, context: { queryClient } }) => {
		void queryClient.prefetchQuery(buildListSavedSearchesQuery());

		if (search.tab === "flow-runs") {
			void queryClient.prefetchQuery(
				buildPaginateFlowRunsQuery({
					page: search.page,
					limit: search.limit,
					sort: search.sort,
					flow_runs: buildFlowRunsFilter(search),
				}),
			);
		} else {
			void queryClient.prefetchQuery(
				buildPaginateTaskRunsQuery({
					page: search.page,
					limit: search.limit,
					sort: search.sort,
					task_runs: buildTaskRunsFilter(search),
				}),
			);
		}
	},
	wrapInSuspense: true,
});

function buildFlowRunsFilter(search: z.infer<typeof searchParams>) {
	const filter: Record<string, unknown> = {};

	if (search.states && search.states.length > 0) {
		filter.state = { name: { any_: search.states } };
	}

	if (search.tags && search.tags.length > 0) {
		filter.tags = { all_: search.tags };
	}

	if (search.deployments && search.deployments.length > 0) {
		filter.deployment_id = { any_: search.deployments };
	}

	if (search.workPools && search.workPools.length > 0) {
		filter.work_pool_name = { any_: search.workPools };
	}

	if (search.workQueues && search.workQueues.length > 0) {
		filter.work_queue_name = { any_: search.workQueues };
	}

	if (search.rangeSeconds) {
		const now = new Date();
		const startTime = new Date(now.getTime() + search.rangeSeconds * 1000);
		filter.start_time = { after_: startTime.toISOString() };
	}

	return filter;
}

function buildTaskRunsFilter(search: z.infer<typeof searchParams>) {
	const filter: Record<string, unknown> = {};

	if (search.states && search.states.length > 0) {
		filter.state = { name: { any_: search.states } };
	}

	if (search.tags && search.tags.length > 0) {
		filter.tags = { all_: search.tags };
	}

	if (search.rangeSeconds) {
		const now = new Date();
		const startTime = new Date(now.getTime() + search.rangeSeconds * 1000);
		filter.start_time = { after_: startTime.toISOString() };
	}

	return filter;
}

function RouteComponent() {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const currentFilter = useMemo<SavedFiltersFilter>(
		() => ({
			state: search.states ?? [],
			flow: search.flows ?? [],
			tag: search.tags ?? [],
			deployment: search.deployments ?? [],
			workPool: search.workPools ?? [],
			workQueue: search.workQueues ?? [],
			range: {
				type: "span",
				seconds: search.rangeSeconds ?? ONE_WEEK_FILTER.range.seconds,
			},
		}),
		[search],
	);

	const handleFilterChange = useCallback(
		(filter: SavedFiltersFilter) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					states: filter.state?.length ? filter.state : undefined,
					flows: filter.flow?.length ? filter.flow : undefined,
					tags: filter.tag?.length ? filter.tag : undefined,
					deployments: filter.deployment?.length
						? filter.deployment
						: undefined,
					workPools: filter.workPool?.length ? filter.workPool : undefined,
					workQueues: filter.workQueue?.length ? filter.workQueue : undefined,
					rangeSeconds: filter.range.seconds,
					page: 1,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	const handleTabChange = useCallback(
		(tab: string) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					tab: tab as "flow-runs" | "task-runs",
					page: 1,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	const handlePaginationChange = useCallback(
		(pagination: PaginationState) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					page: pagination.page,
					limit: pagination.limit,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	return (
		<LayoutWell>
			<LayoutWellContent>
				<LayoutWellHeader className="pb-4 md:pb-6">
					<div className="flex flex-col space-y-4 md:space-y-0 md:flex-row md:items-center md:justify-between">
						<div>
							<Breadcrumb>
								<BreadcrumbList>
									<BreadcrumbItem className="text-2xl font-bold text-foreground">
										Runs
									</BreadcrumbItem>
								</BreadcrumbList>
							</Breadcrumb>
						</div>
						<div className="flex items-center gap-2">
							<Suspense fallback={<Skeleton className="h-9 w-[250px]" />}>
								<SavedFilters
									filter={currentFilter}
									onFilterChange={handleFilterChange}
								/>
							</Suspense>
						</div>
					</div>
				</LayoutWellHeader>

				<Tabs value={search.tab} onValueChange={handleTabChange}>
					<TabsList>
						<TabsTrigger value="flow-runs">Flow Runs</TabsTrigger>
						<TabsTrigger value="task-runs">Task Runs</TabsTrigger>
					</TabsList>
					<TabsContent value="flow-runs" className="mt-4">
						<Suspense fallback={<DataTableSkeleton />}>
							<FlowRunsTabContent
								pagination={{ page: search.page, limit: search.limit }}
								onPaginationChange={handlePaginationChange}
							/>
						</Suspense>
					</TabsContent>
					<TabsContent value="task-runs" className="mt-4">
						<Suspense fallback={<DataTableSkeleton />}>
							<TaskRunsTabContent
								pagination={{ page: search.page, limit: search.limit }}
								onPaginationChange={handlePaginationChange}
							/>
						</Suspense>
					</TabsContent>
				</Tabs>
			</LayoutWellContent>
		</LayoutWell>
	);
}

type TabContentProps = {
	pagination: PaginationState;
	onPaginationChange: (pagination: PaginationState) => void;
};

function FlowRunsTabContent({
	pagination,
	onPaginationChange,
}: TabContentProps) {
	const search = Route.useSearch();

	const { data } = useSuspenseQuery(
		buildPaginateFlowRunsQuery({
			page: search.page,
			limit: search.limit,
			sort: search.sort,
			flow_runs: buildFlowRunsFilter(search),
		}),
	);

	const flowRuns = data.results ?? [];
	const count = data.count ?? 0;
	const pages = Math.ceil(count / pagination.limit);

	if (flowRuns.length === 0) {
		return (
			<div className="flex justify-center py-8">
				<Typography>No flow runs found</Typography>
			</div>
		);
	}

	return (
		<div className="space-y-4">
			<ul className="flex flex-col gap-2">
				{flowRuns.map((flowRun: FlowRun) => (
					<li key={flowRun.id}>
						<Link
							to="/runs/flow-run/$id"
							params={{ id: flowRun.id }}
							className="block"
						>
							<Card className="flex flex-col gap-2 p-4 hover:bg-muted/50 transition-colors">
								<div className="flex justify-between items-center">
									<Typography variant="bodySmall" className="font-medium">
										{flowRun.name}
									</Typography>
									{flowRun.state && (
										<StateBadge
											type={flowRun.state.type}
											name={flowRun.state.name}
										/>
									)}
								</div>
								<div className="flex items-center gap-4 text-sm text-muted-foreground">
									{flowRun.start_time && (
										<span>
											Started: {new Date(flowRun.start_time).toLocaleString()}
										</span>
									)}
									{flowRun.total_run_time !== undefined && (
										<span>Duration: {flowRun.total_run_time.toFixed(2)}s</span>
									)}
								</div>
							</Card>
						</Link>
					</li>
				))}
			</ul>
			<FlowRunsPagination
				count={count}
				pages={pages}
				pagination={pagination}
				onChangePagination={onPaginationChange}
			/>
		</div>
	);
}

function TaskRunsTabContent({
	pagination,
	onPaginationChange,
}: TabContentProps) {
	const search = Route.useSearch();

	const { data } = useSuspenseQuery(
		buildPaginateTaskRunsQuery({
			page: search.page,
			limit: search.limit,
			sort: search.sort,
			task_runs: buildTaskRunsFilter(search),
		}),
	);

	const taskRuns = data.results ?? [];
	const count = data.count ?? 0;
	const pages = Math.ceil(count / pagination.limit);

	if (taskRuns.length === 0) {
		return (
			<div className="flex justify-center py-8">
				<Typography>No task runs found</Typography>
			</div>
		);
	}

	return (
		<div className="space-y-4">
			<ul className="flex flex-col gap-2">
				{taskRuns.map((taskRun: TaskRun) => (
					<li key={taskRun.id}>
						<Link
							to="/runs/task-run/$id"
							params={{ id: taskRun.id }}
							className="block"
						>
							<Card className="flex flex-col gap-2 p-4 hover:bg-muted/50 transition-colors">
								<div className="flex justify-between items-center">
									<Typography variant="bodySmall" className="font-medium">
										{taskRun.name}
									</Typography>
									{taskRun.state && (
										<StateBadge
											type={taskRun.state.type}
											name={taskRun.state.name}
										/>
									)}
								</div>
								<div className="flex items-center gap-4 text-sm text-muted-foreground">
									{taskRun.start_time && (
										<span>
											Started: {new Date(taskRun.start_time).toLocaleString()}
										</span>
									)}
									{taskRun.total_run_time !== undefined && (
										<span>Duration: {taskRun.total_run_time.toFixed(2)}s</span>
									)}
								</div>
							</Card>
						</Link>
					</li>
				))}
			</ul>
			<FlowRunsPagination
				count={count}
				pages={pages}
				pagination={pagination}
				onChangePagination={onPaginationChange}
			/>
		</div>
	);
}

function DataTableSkeleton() {
	return (
		<div className="space-y-4">
			<Skeleton className="h-10 w-full" />
			<Skeleton className="h-64 w-full" />
		</div>
	);
}
