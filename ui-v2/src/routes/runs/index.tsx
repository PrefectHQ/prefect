import {
	useQuery,
	useQueryClient,
	useSuspenseQueries,
} from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { useCallback, useEffect, useMemo } from "react";
import { z } from "zod";
import {
	buildCountFlowRunsQuery,
	buildPaginateFlowRunsQuery,
	type FlowRunsPaginateFilter,
} from "@/api/flow-runs";
import {
	buildCountTaskRunsQuery,
	buildGetFlowRunsTaskRunsCountQuery,
	buildPaginateTaskRunsQuery,
	type TaskRunsPaginateFilter,
} from "@/api/task-runs";
import {
	DATE_RANGE_PRESETS,
	type DateRangeUrlState,
	FLOW_RUN_STATES,
	type FlowRunState,
	type PaginationState,
	SORT_FILTERS,
	type SortFilters,
	urlStateToDateRangeValue,
} from "@/components/flow-runs/flow-runs-list";
import { RunsPage } from "@/components/runs/runs-page";
import {
	TASK_RUN_SORT_FILTERS,
	type TaskRunSortFilters,
} from "@/components/task-runs/task-runs-list";
import { mapValueToRange } from "@/components/ui/date-range-select";

const searchParams = z.object({
	tab: z.enum(["flow-runs", "task-runs"]).optional().default("flow-runs"),
	// Flow runs URL state
	page: z.number().int().positive().optional().default(1).catch(1),
	limit: z.number().int().positive().optional().default(10).catch(10),
	sort: z.enum(SORT_FILTERS).optional().default("START_TIME_DESC"),
	"hide-subflows": z.boolean().optional().default(false),
	"flow-run-search": z.string().optional().default(""),
	state: z.string().optional().default(""),
	flows: z.string().optional().default(""),
	range: z.enum(DATE_RANGE_PRESETS).optional(),
	start: z.string().optional(),
	end: z.string().optional(),
	// Task runs URL state
	"task-runs-page": z.number().int().positive().optional().default(1).catch(1),
	"task-runs-limit": z
		.number()
		.int()
		.positive()
		.optional()
		.default(10)
		.catch(10),
	"task-runs-sort": z
		.enum(TASK_RUN_SORT_FILTERS)
		.optional()
		.default("EXPECTED_START_TIME_DESC"),
	"task-run-search": z.string().optional().default(""),
});

type SearchParams = z.infer<typeof searchParams>;

// Helper to parse state string to array of FlowRunState
const parseStateFilter = (stateString: string): FlowRunState[] => {
	if (!stateString) return [];
	return stateString
		.split(",")
		.filter((s): s is FlowRunState =>
			FLOW_RUN_STATES.includes(s as FlowRunState),
		);
};

// Helper to get date range from search params
const getDateRangeFilter = (
	search?: SearchParams,
): { after_?: string; before_?: string } | undefined => {
	if (!search) return undefined;

	const dateRangeUrlState: DateRangeUrlState = {
		range: search.range,
		start: search.start,
		end: search.end,
	};

	const dateRangeValue = urlStateToDateRangeValue(dateRangeUrlState);
	if (!dateRangeValue) return undefined;

	const range = mapValueToRange(dateRangeValue);
	if (!range) return undefined;

	return {
		after_: range.startDate.toISOString(),
		before_: range.endDate.toISOString(),
	};
};

// Helper to parse flows string to array of flow IDs
const parseFlowsFilter = (flowsString: string): string[] => {
	if (!flowsString) return [];
	return flowsString.split(",").filter((s) => s.trim().length > 0);
};

const buildTaskRunsPaginationBody = (
	search?: SearchParams,
): TaskRunsPaginateFilter => {
	const taskRunSearch = search?.["task-run-search"];

	// Build task_runs filter only if we have filters to apply
	const hasFilters = taskRunSearch;
	const taskRunsFilter = hasFilters
		? {
				operator: "and_" as const,
				...(taskRunSearch && {
					name: { like_: taskRunSearch },
				}),
			}
		: undefined;

	return {
		page: search?.["task-runs-page"] ?? 1,
		limit: search?.["task-runs-limit"] ?? 10,
		sort: search?.["task-runs-sort"] ?? "EXPECTED_START_TIME_DESC",
		task_runs: taskRunsFilter,
	};
};

const buildPaginationBody = (search?: SearchParams): FlowRunsPaginateFilter => {
	const hideSubflows = search?.["hide-subflows"];
	const flowRunSearch = search?.["flow-run-search"];
	const stateFilters = parseStateFilter(search?.state ?? "");
	const flowsFilter = parseFlowsFilter(search?.flows ?? "");
	const dateRangeFilter = getDateRangeFilter(search);

	// Map state names to state types for the API filter
	const stateNames = stateFilters.length > 0 ? stateFilters : undefined;
	const flowIds = flowsFilter.length > 0 ? flowsFilter : undefined;

	// Build flow_runs filter only if we have filters to apply
	const hasFilters =
		hideSubflows || flowRunSearch || stateNames || flowIds || dateRangeFilter;
	const flowRunsFilter = hasFilters
		? {
				operator: "and_" as const,
				...(hideSubflows && {
					parent_task_run_id: { operator: "and_" as const, is_null_: true },
				}),
				...(flowRunSearch && {
					name: { like_: flowRunSearch },
				}),
				...(stateNames && {
					state: {
						operator: "and_" as const,
						name: { any_: stateNames },
					},
				}),
				...(dateRangeFilter && {
					expected_start_time: dateRangeFilter,
				}),
			}
		: undefined;

	// Build flows filter for filtering by flow_id
	const flowsFilterBody = flowIds
		? { operator: "and_" as const, id: { any_: flowIds } }
		: undefined;

	return {
		page: search?.page ?? 1,
		limit: search?.limit ?? 10,
		sort: search?.sort ?? "START_TIME_DESC",
		flow_runs: flowRunsFilter,
		flows: flowsFilterBody,
	};
};

export const Route = createFileRoute("/runs/")({
	validateSearch: zodValidator(searchParams),
	component: RouteComponent,
	loaderDeps: ({ search }) => ({
		flowRuns: buildPaginationBody(search),
		taskRuns: buildTaskRunsPaginationBody(search),
	}),
	loader: ({ deps, context }) => {
		// Prefetch all queries without blocking the loader
		// This allows the component to render immediately and use placeholderData
		void context.queryClient.prefetchQuery(buildCountFlowRunsQuery());
		void context.queryClient.prefetchQuery(buildCountTaskRunsQuery());
		void context.queryClient.prefetchQuery(
			buildPaginateFlowRunsQuery(deps.flowRuns, 30_000),
		);
		void context.queryClient.prefetchQuery(
			buildPaginateTaskRunsQuery(deps.taskRuns, 30_000),
		);

		// Background async chain: prefetch task run counts for each flow run
		// This prevents suspense when FlowRunCard renders
		void (async () => {
			const pageData = await context.queryClient.ensureQueryData(
				buildPaginateFlowRunsQuery(deps.flowRuns, 30_000),
			);
			const flowRunIds = pageData?.results?.map((run) => run.id) ?? [];
			if (flowRunIds.length > 0) {
				void context.queryClient.prefetchQuery(
					buildGetFlowRunsTaskRunsCountQuery(flowRunIds),
				);
			}
		})();
	},
	wrapInSuspense: true,
});

const usePagination = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const pagination: PaginationState = useMemo(
		() => ({
			page: search.page ?? 1,
			limit: search.limit ?? 10,
		}),
		[search.page, search.limit],
	);

	const onPaginationChange = useCallback(
		(newPagination: PaginationState) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					page: newPagination.page,
					limit: newPagination.limit,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	return [pagination, onPaginationChange] as const;
};

const useSort = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const onSortChange = useCallback(
		(sort: SortFilters) => {
			void navigate({
				to: ".",
				search: (prev) => ({ ...prev, sort, page: 1 }),
				replace: true,
			});
		},
		[navigate],
	);

	return [search.sort, onSortChange] as const;
};

const useHideSubflows = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const onHideSubflowsChange = useCallback(
		(hideSubflows: boolean) => {
			void navigate({
				to: ".",
				search: (prev) => ({ ...prev, "hide-subflows": hideSubflows, page: 1 }),
				replace: true,
			});
		},
		[navigate],
	);

	return [search["hide-subflows"], onHideSubflowsChange] as const;
};

const useTab = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const onTabChange = useCallback(
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

	return [search.tab, onTabChange] as const;
};

const useFlowRunSearch = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const onFlowRunSearchChange = useCallback(
		(flowRunSearch: string) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					"flow-run-search": flowRunSearch,
					page: 1, // Reset pagination when search changes
				}),
				replace: true,
			});
		},
		[navigate],
	);

	return [search["flow-run-search"], onFlowRunSearchChange] as const;
};

const useStateFilter = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const selectedStates = useMemo(
		() => new Set<FlowRunState>(parseStateFilter(search.state ?? "")),
		[search.state],
	);

	const onStateFilterChange = useCallback(
		(states: Set<FlowRunState>) => {
			const stateArray = Array.from(states);
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					state: stateArray.length > 0 ? stateArray.join(",") : "",
					page: 1, // Reset pagination when filter changes
				}),
				replace: true,
			});
		},
		[navigate],
	);

	return [selectedStates, onStateFilterChange] as const;
};

const useDateRange = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const dateRange: DateRangeUrlState = useMemo(
		() => ({
			range: search.range,
			start: search.start,
			end: search.end,
		}),
		[search.range, search.start, search.end],
	);

	const onDateRangeChange = useCallback(
		(newDateRange: DateRangeUrlState) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					range: newDateRange.range,
					start: newDateRange.start,
					end: newDateRange.end,
					page: 1, // Reset pagination when date range changes
				}),
				replace: true,
			});
		},
		[navigate],
	);

	return [dateRange, onDateRangeChange] as const;
};

const useFlowFilter = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const selectedFlows = useMemo(
		() => new Set<string>(parseFlowsFilter(search.flows ?? "")),
		[search.flows],
	);

	const onFlowFilterChange = useCallback(
		(flows: Set<string>) => {
			const flowsArray = Array.from(flows);
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					flows: flowsArray.length > 0 ? flowsArray.join(",") : "",
					page: 1, // Reset pagination when filter changes
				}),
				replace: true,
			});
		},
		[navigate],
	);

	return [selectedFlows, onFlowFilterChange] as const;
};

// Task runs URL state hooks
const useTaskRunPagination = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const pagination: PaginationState = useMemo(
		() => ({
			page: search["task-runs-page"] ?? 1,
			limit: search["task-runs-limit"] ?? 10,
		}),
		[search["task-runs-page"], search["task-runs-limit"]],
	);

	const onPaginationChange = useCallback(
		(newPagination: PaginationState) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					"task-runs-page": newPagination.page,
					"task-runs-limit": newPagination.limit,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	return [pagination, onPaginationChange] as const;
};

const useTaskRunSort = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const onSortChange = useCallback(
		(sort: TaskRunSortFilters) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					"task-runs-sort": sort,
					"task-runs-page": 1,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	return [search["task-runs-sort"], onSortChange] as const;
};

const useTaskRunSearch = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const onTaskRunSearchChange = useCallback(
		(taskRunSearch: string) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					"task-run-search": taskRunSearch,
					"task-runs-page": 1, // Reset pagination when search changes
				}),
				replace: true,
			});
		},
		[navigate],
	);

	return [search["task-run-search"], onTaskRunSearchChange] as const;
};

function RouteComponent() {
	const queryClient = useQueryClient();
	const search = Route.useSearch();
	// Flow runs URL state
	const [pagination, onPaginationChange] = usePagination();
	const [sort, onSortChange] = useSort();
	const [hideSubflows, onHideSubflowsChange] = useHideSubflows();
	const [tab, onTabChange] = useTab();
	const [flowRunSearch, onFlowRunSearchChange] = useFlowRunSearch();
	const [selectedStates, onStateFilterChange] = useStateFilter();
	const [selectedFlows, onFlowFilterChange] = useFlowFilter();
	const [dateRange, onDateRangeChange] = useDateRange();
	// Task runs URL state
	const [taskRunPagination, onTaskRunPaginationChange] = useTaskRunPagination();
	const [taskRunSort, onTaskRunSortChange] = useTaskRunSort();
	const [taskRunSearch, onTaskRunSearchChange] = useTaskRunSearch();

	// Use useSuspenseQueries for count queries (stable keys, won't cause suspense on search change)
	const [{ data: flowRunsCount }, { data: taskRunsCount }] = useSuspenseQueries(
		{
			queries: [buildCountFlowRunsQuery(), buildCountTaskRunsQuery()],
		},
	);

	// Use useQuery for paginated flow runs to leverage placeholderData: keepPreviousData
	// This prevents the page from suspending when search/filter changes
	const { data: flowRunsPage } = useQuery(
		buildPaginateFlowRunsQuery(buildPaginationBody(search), 30_000),
	);

	// Use useQuery for paginated task runs to leverage placeholderData: keepPreviousData
	const { data: taskRunsPage } = useQuery(
		buildPaginateTaskRunsQuery(buildTaskRunsPaginationBody(search), 30_000),
	);

	const flowRuns = flowRunsPage?.results ?? [];
	const taskRuns = taskRunsPage?.results ?? [];

	// Prefetch task run counts for the current page's flow runs
	// This ensures the data is ready when FlowRunCard renders
	useEffect(() => {
		const flowRunIds = flowRuns.map((run) => run.id);
		if (flowRunIds.length > 0) {
			void queryClient.prefetchQuery(
				buildGetFlowRunsTaskRunsCountQuery(flowRunIds),
			);
		}
	}, [queryClient, flowRuns]);

	const onPrefetchPage = useCallback(
		(page: number) => {
			const filter = buildPaginationBody({
				...search,
				page,
			});
			// Prefetch the page data, then chain prefetch of task run counts
			void (async () => {
				const pageData = await queryClient.ensureQueryData(
					buildPaginateFlowRunsQuery(filter, 30_000),
				);
				const flowRunIds = pageData?.results?.map((run) => run.id) ?? [];
				if (flowRunIds.length > 0) {
					void queryClient.prefetchQuery(
						buildGetFlowRunsTaskRunsCountQuery(flowRunIds),
					);
				}
			})();
		},
		[queryClient, search],
	);

	const onPrefetchTaskRunPage = useCallback(
		(page: number) => {
			const filter = buildTaskRunsPaginationBody({
				...search,
				"task-runs-page": page,
			});
			void queryClient.prefetchQuery(
				buildPaginateTaskRunsQuery(filter, 30_000),
			);
		},
		[queryClient, search],
	);

	return (
		<RunsPage
			tab={tab}
			onTabChange={onTabChange}
			flowRunsCount={flowRunsCount}
			taskRunsCount={taskRunsCount}
			flowRuns={flowRuns}
			flowRunsPages={flowRunsPage?.pages ?? 0}
			pagination={pagination}
			onPaginationChange={onPaginationChange}
			onPrefetchPage={onPrefetchPage}
			sort={sort}
			onSortChange={onSortChange}
			hideSubflows={hideSubflows}
			onHideSubflowsChange={onHideSubflowsChange}
			flowRunSearch={flowRunSearch}
			onFlowRunSearchChange={onFlowRunSearchChange}
			selectedStates={selectedStates}
			onStateFilterChange={onStateFilterChange}
			selectedFlows={selectedFlows}
			onFlowFilterChange={onFlowFilterChange}
			dateRange={dateRange}
			onDateRangeChange={onDateRangeChange}
			// Task runs props
			taskRuns={taskRuns}
			taskRunsPages={taskRunsPage?.pages ?? 0}
			taskRunPagination={taskRunPagination}
			onTaskRunPaginationChange={onTaskRunPaginationChange}
			onPrefetchTaskRunPage={onPrefetchTaskRunPage}
			taskRunSort={taskRunSort}
			onTaskRunSortChange={onTaskRunSortChange}
			taskRunSearch={taskRunSearch}
			onTaskRunSearchChange={onTaskRunSearchChange}
		/>
	);
}
