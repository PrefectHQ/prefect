import {
	useQuery,
	useQueryClient,
	useSuspenseQueries,
} from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { useCallback, useEffect, useMemo, useRef } from "react";
import { z } from "zod";
import {
	buildCountFlowRunsQuery,
	buildFlowRunHistoryQuery,
	buildPaginateFlowRunsQuery,
	type FlowRunHistoryFilter,
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
	useApplyDefaultFilterOnMount,
	useRunsSavedFilters,
} from "@/components/runs/use-runs-saved-filters";
import {
	TASK_RUN_SORT_FILTERS,
	type TaskRunSortFilters,
} from "@/components/task-runs/task-runs-list";
import { mapValueToRange } from "@/components/ui/date-range-select";
import { useLocalStorage } from "@/hooks/use-local-storage";
import { useRunsFilters } from "@/hooks/use-runs-filters";

const searchParams = z.object({
	tab: z.enum(["flow-runs", "task-runs"]).optional().default("flow-runs"),
	// Flow runs pagination params
	page: z.number().int().positive().optional().default(1).catch(1),
	limit: z.number().int().positive().optional().catch(undefined),
	sort: z.enum(SORT_FILTERS).optional().default("START_TIME_DESC"),
	"hide-subflows": z.boolean().optional().default(false),
	"flow-run-search": z.string().optional().default(""),
	state: z.string().optional().default(""),
	flows: z.string().optional().default(""),
	deployments: z.string().optional().default(""),
	"work-pools": z.string().optional().default(""),
	tags: z.string().optional().default(""),
	range: z.enum(DATE_RANGE_PRESETS).optional(),
	start: z.string().optional(),
	end: z.string().optional(),
	// Task runs pagination params
	"task-runs-page": z.number().int().positive().optional().default(1).catch(1),
	"task-runs-limit": z.number().int().positive().optional().catch(undefined),
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

// Helper to parse deployments string to array of deployment IDs
const parseDeploymentsFilter = (deploymentsString: string): string[] => {
	if (!deploymentsString) return [];
	return deploymentsString.split(",").filter((s) => s.trim().length > 0);
};

// Helper to parse work pools string to array of work pool names
const parseWorkPoolsFilter = (workPoolsString: string): string[] => {
	if (!workPoolsString) return [];
	return workPoolsString.split(",").filter((s) => s.trim().length > 0);
};

// Helper to parse tags string to array of tag strings
const parseTagsFilter = (tagsString: string): string[] => {
	if (!tagsString) return [];
	return tagsString.split(",").filter((s) => s.trim().length > 0);
};

const buildPaginationBody = (search?: SearchParams): FlowRunsPaginateFilter => {
	const hideSubflows = search?.["hide-subflows"];
	const flowRunSearch = search?.["flow-run-search"];
	const stateFilters = parseStateFilter(search?.state ?? "");
	const flowsFilter = parseFlowsFilter(search?.flows ?? "");
	const deploymentsFilter = parseDeploymentsFilter(search?.deployments ?? "");
	const workPoolsFilter = parseWorkPoolsFilter(search?.["work-pools"] ?? "");
	const tagsFilter = parseTagsFilter(search?.tags ?? "");
	const dateRangeFilter = getDateRangeFilter(search);

	// Map state names to state types for the API filter
	const stateNames = stateFilters.length > 0 ? stateFilters : undefined;
	const flowIds = flowsFilter.length > 0 ? flowsFilter : undefined;
	const deploymentIds =
		deploymentsFilter.length > 0 ? deploymentsFilter : undefined;
	const workPoolNames =
		workPoolsFilter.length > 0 ? workPoolsFilter : undefined;

	// Build flow_runs filter only if we have filters to apply
	const hasFilters =
		hideSubflows ||
		flowRunSearch ||
		stateNames ||
		flowIds ||
		deploymentIds ||
		tagsFilter.length > 0 ||
		dateRangeFilter;
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
				...(tagsFilter.length > 0 && {
					tags: { operator: "and_" as const, any_: tagsFilter },
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

	// Build deployments filter for filtering by deployment_id
	const deploymentsFilterBody = deploymentIds
		? { operator: "and_" as const, id: { any_: deploymentIds } }
		: undefined;

	// Build work_pools filter for filtering by work pool name
	const workPoolsFilterBody = workPoolNames
		? { operator: "and_" as const, name: { any_: workPoolNames } }
		: undefined;

	return {
		page: search?.page ?? 1,
		limit: search?.limit ?? 100,
		sort: search?.sort ?? "START_TIME_DESC",
		flow_runs: flowRunsFilter,
		flows: flowsFilterBody,
		deployments: deploymentsFilterBody,
		work_pools: workPoolsFilterBody,
	};
};

const buildTaskRunsPaginationBody = (
	search?: SearchParams,
): TaskRunsPaginateFilter => {
	const taskRunSearch = search?.["task-run-search"];
	const stateFilters = parseStateFilter(search?.state ?? "");
	const flowsFilter = parseFlowsFilter(search?.flows ?? "");
	const deploymentsFilter = parseDeploymentsFilter(search?.deployments ?? "");
	const tagsFilter = parseTagsFilter(search?.tags ?? "");
	const dateRangeFilter = getDateRangeFilter(search);

	// Build task_runs filter only if we have task-specific filters to apply
	const taskRunsFilter = taskRunSearch
		? {
				operator: "and_" as const,
				name: { like_: taskRunSearch },
			}
		: undefined;

	// Build flow_runs filter from shared filters (state, tags, date range)
	// These filters apply to the flow runs that the task runs belong to
	const stateNames = stateFilters.length > 0 ? stateFilters : undefined;
	const hasFlowRunsFilters =
		stateNames || tagsFilter.length > 0 || dateRangeFilter;
	const flowRunsFilter = hasFlowRunsFilters
		? {
				operator: "and_" as const,
				...(stateNames && {
					state: {
						operator: "and_" as const,
						name: { any_: stateNames },
					},
				}),
				...(tagsFilter.length > 0 && {
					tags: { operator: "and_" as const, any_: tagsFilter },
				}),
				...(dateRangeFilter && {
					expected_start_time: dateRangeFilter,
				}),
			}
		: undefined;

	// Build flows filter for filtering by flow_id
	const flowIds = flowsFilter.length > 0 ? flowsFilter : undefined;
	const flowsFilterBody = flowIds
		? { operator: "and_" as const, id: { any_: flowIds } }
		: undefined;

	// Build deployments filter for filtering by deployment_id
	const deploymentIds =
		deploymentsFilter.length > 0 ? deploymentsFilter : undefined;
	const deploymentsFilterBody = deploymentIds
		? { operator: "and_" as const, id: { any_: deploymentIds } }
		: undefined;

	// Note: work_pools filter is NOT supported by the task_runs/paginate endpoint

	return {
		page: search?.["task-runs-page"] ?? 1,
		limit: search?.["task-runs-limit"] ?? 100,
		sort: search?.["task-runs-sort"] ?? "EXPECTED_START_TIME_DESC",
		task_runs: taskRunsFilter,
		flow_runs: flowRunsFilter,
		flows: flowsFilterBody,
		deployments: deploymentsFilterBody,
	};
};

const buildHistoryFilter = (search?: SearchParams): FlowRunHistoryFilter => {
	const hideSubflows = search?.["hide-subflows"];
	const stateFilters = parseStateFilter(search?.state ?? "");
	const flowsFilter = parseFlowsFilter(search?.flows ?? "");
	const deploymentsFilter = parseDeploymentsFilter(search?.deployments ?? "");
	const workPoolsFilter = parseWorkPoolsFilter(search?.["work-pools"] ?? "");
	const tagsFilter = parseTagsFilter(search?.tags ?? "");
	const dateRangeFilter = getDateRangeFilter(search);

	// Map state names to state types for the API filter
	const stateNames = stateFilters.length > 0 ? stateFilters : undefined;
	const flowIds = flowsFilter.length > 0 ? flowsFilter : undefined;
	const deploymentIds =
		deploymentsFilter.length > 0 ? deploymentsFilter : undefined;
	const workPoolNames =
		workPoolsFilter.length > 0 ? workPoolsFilter : undefined;

	// Build flow_runs filter only if we have filters to apply
	const hasFilters =
		hideSubflows || stateNames || tagsFilter.length > 0 || dateRangeFilter;
	const flowRunsFilter = hasFilters
		? {
				operator: "and_" as const,
				...(hideSubflows && {
					parent_task_run_id: { operator: "and_" as const, is_null_: true },
				}),
				...(stateNames && {
					state: {
						operator: "and_" as const,
						name: { any_: stateNames },
					},
				}),
				...(tagsFilter.length > 0 && {
					tags: { operator: "and_" as const, any_: tagsFilter },
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

	// Build deployments filter for filtering by deployment_id
	const deploymentsFilterBody = deploymentIds
		? { operator: "and_" as const, id: { any_: deploymentIds } }
		: undefined;

	// Build work_pools filter for filtering by work pool name
	const workPoolsFilterBody = workPoolNames
		? { operator: "and_" as const, name: { any_: workPoolNames } }
		: undefined;

	return {
		sort: "EXPECTED_START_TIME_DESC",
		limit: 1000,
		offset: 0,
		flow_runs: flowRunsFilter,
		flows: flowsFilterBody,
		deployments: deploymentsFilterBody,
		work_pools: workPoolsFilterBody,
	};
};

export const Route = createFileRoute("/runs/")({
	validateSearch: zodValidator(searchParams),
	component: RouteComponent,
	loaderDeps: ({ search }) => ({
		flowRunsDeps: buildPaginationBody(search),
		taskRunsDeps: buildTaskRunsPaginationBody(search),
		historyDeps: buildHistoryFilter(search),
	}),
	loader: ({ deps, context }) => {
		// Prefetch all queries without blocking the loader
		// This allows the component to render immediately and use placeholderData
		void context.queryClient.prefetchQuery(buildCountFlowRunsQuery());
		void context.queryClient.prefetchQuery(buildCountTaskRunsQuery());
		void context.queryClient.prefetchQuery(
			buildPaginateFlowRunsQuery(deps.flowRunsDeps, 30_000),
		);
		void context.queryClient.prefetchQuery(
			buildPaginateTaskRunsQuery(deps.taskRunsDeps, 30_000),
		);
		void context.queryClient.prefetchQuery(
			buildFlowRunHistoryQuery(deps.historyDeps, 30_000),
		);

		// Background async chain: prefetch task run counts for each flow run
		// This prevents suspense when FlowRunCard renders
		void (async () => {
			const pageData = await context.queryClient.ensureQueryData(
				buildPaginateFlowRunsQuery(deps.flowRunsDeps, 30_000),
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
			limit: search.limit ?? 100,
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

// Task runs hooks
const useTaskRunsPagination = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const pagination: PaginationState = useMemo(
		() => ({
			page: search["task-runs-page"] ?? 1,
			limit: search["task-runs-limit"] ?? 100,
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

const useTaskRunsSort = () => {
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
	const navigate = Route.useNavigate();

	// localStorage persistence for pagination limits (separate keys for flow runs and task runs)
	const [storedFlowRunsLimit, setStoredFlowRunsLimit] = useLocalStorage(
		"workspace-flow-runs-list-limit",
		100,
	);
	const [storedTaskRunsLimit, setStoredTaskRunsLimit] = useLocalStorage(
		"workspace-task-runs-list-limit",
		100,
	);

	// Track if we've done the initial URL sync to avoid re-running on every render
	const hasInitializedRef = useRef(false);

	// On mount - if URL limit is undefined (not explicitly set), use localStorage value
	useEffect(() => {
		if (hasInitializedRef.current) return;
		hasInitializedRef.current = true;

		const needsFlowRunsLimit = search.limit === undefined;
		const needsTaskRunsLimit = search["task-runs-limit"] === undefined;

		if (needsFlowRunsLimit || needsTaskRunsLimit) {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					...(needsFlowRunsLimit && { limit: storedFlowRunsLimit }),
					...(needsTaskRunsLimit && {
						"task-runs-limit": storedTaskRunsLimit,
					}),
				}),
				replace: true,
			});
		}
	}, [
		navigate,
		search.limit,
		search["task-runs-limit"],
		storedFlowRunsLimit,
		storedTaskRunsLimit,
	]);

	// When flow runs URL limit changes (user interaction), save to localStorage
	useEffect(() => {
		if (search.limit !== undefined && search.limit !== storedFlowRunsLimit) {
			setStoredFlowRunsLimit(search.limit);
		}
	}, [search.limit, storedFlowRunsLimit, setStoredFlowRunsLimit]);

	// When task runs URL limit changes (user interaction), save to localStorage
	useEffect(() => {
		if (
			search["task-runs-limit"] !== undefined &&
			search["task-runs-limit"] !== storedTaskRunsLimit
		) {
			setStoredTaskRunsLimit(search["task-runs-limit"]);
		}
	}, [search["task-runs-limit"], storedTaskRunsLimit, setStoredTaskRunsLimit]);

	// Flow runs hooks
	const [pagination, onPaginationChange] = usePagination();
	const [sort, onSortChange] = useSort();
	const [hideSubflows, onHideSubflowsChange] = useHideSubflows();
	const [tab, onTabChange] = useTab();
	const [flowRunSearch, onFlowRunSearchChange] = useFlowRunSearch();
	// Consolidated filter state
	const {
		states: selectedStates,
		flows: selectedFlows,
		deployments: selectedDeployments,
		workPools: selectedWorkPools,
		tags: selectedTags,
		dateRange,
		onStatesChange: onStateFilterChange,
		onFlowsChange: onFlowFilterChange,
		onDeploymentsChange: onDeploymentFilterChange,
		onWorkPoolsChange: onWorkPoolFilterChange,
		onTagsChange: onTagsFilterChange,
		onDateRangeChange,
	} = useRunsFilters();
	// Task runs hooks
	const [taskRunsPagination, onTaskRunsPaginationChange] =
		useTaskRunsPagination();
	const [taskRunsSort, onTaskRunsSortChange] = useTaskRunsSort();
	const [taskRunSearch, onTaskRunSearchChange] = useTaskRunSearch();

	// Saved filters hook
	const {
		currentFilter,
		savedFiltersForMenu,
		onSelectFilter,
		onSaveFilter,
		onDeleteFilter,
		onSetDefault,
		onRemoveDefault,
		isSaveDialogOpen,
		closeSaveDialog,
		confirmSave,
	} = useRunsSavedFilters();

	// Apply default filter on initial page load (if one is set and no filters are active)
	useApplyDefaultFilterOnMount();

	// Use useSuspenseQueries for unfiltered count queries (stable keys, won't cause suspense on search change)
	// These are used to determine if the app has ANY runs at all (for empty state)
	const [{ data: flowRunsCountAll }, { data: taskRunsCountAll }] =
		useSuspenseQueries({
			queries: [buildCountFlowRunsQuery(), buildCountTaskRunsQuery()],
		});

	// Use useQuery for paginated flow runs to leverage placeholderData: keepPreviousData
	// This prevents the page from suspending when search/filter changes
	const { data: flowRunsPage } = useQuery(
		buildPaginateFlowRunsQuery(buildPaginationBody(search), 30_000),
	);

	// Use useQuery for paginated task runs to leverage placeholderData: keepPreviousData
	const { data: taskRunsPage } = useQuery(
		buildPaginateTaskRunsQuery(buildTaskRunsPaginationBody(search), 30_000),
	);

	// Use useQuery for flow run history (scatter plot) to leverage placeholderData: keepPreviousData
	// This prevents the scatter plot from flickering when search/filter changes
	const { data: flowRunHistory } = useQuery(
		buildFlowRunHistoryQuery(buildHistoryFilter(search), 30_000),
	);

	const flowRuns = flowRunsPage?.results ?? [];
	const taskRuns = taskRunsPage?.results ?? [];

	// Extract date range from search params for the scatter plot
	const scatterPlotDateRange = useMemo(() => {
		const dateRangeFilter = getDateRangeFilter(search);
		return {
			startDate: dateRangeFilter?.after_
				? new Date(dateRangeFilter.after_)
				: undefined,
			endDate: dateRangeFilter?.before_
				? new Date(dateRangeFilter.before_)
				: undefined,
		};
	}, [search]);

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

	const onTaskRunsPrefetchPage = useCallback(
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

	const onClearTaskRunFilters = useCallback(() => {
		onTaskRunSearchChange("");
	}, [onTaskRunSearchChange]);

	return (
		<RunsPage
			tab={tab}
			onTabChange={onTabChange}
			flowRunsCount={flowRunsPage?.count ?? 0}
			taskRunsCount={taskRunsPage?.count ?? 0}
			hasAnyFlowRuns={(flowRunsCountAll ?? 0) > 0}
			hasAnyTaskRuns={(taskRunsCountAll ?? 0) > 0}
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
			selectedDeployments={selectedDeployments}
			onDeploymentFilterChange={onDeploymentFilterChange}
			selectedTags={selectedTags}
			onTagsFilterChange={onTagsFilterChange}
			selectedWorkPools={selectedWorkPools}
			onWorkPoolFilterChange={onWorkPoolFilterChange}
			dateRange={dateRange}
			onDateRangeChange={onDateRangeChange}
			// Scatter plot props
			flowRunHistory={flowRunHistory ?? []}
			scatterPlotDateRange={scatterPlotDateRange}
			// Task runs props
			taskRuns={taskRuns}
			taskRunsPages={taskRunsPage?.pages ?? 0}
			taskRunsPagination={taskRunsPagination}
			onTaskRunsPaginationChange={onTaskRunsPaginationChange}
			onTaskRunsPrefetchPage={onTaskRunsPrefetchPage}
			taskRunsSort={taskRunsSort}
			onTaskRunsSortChange={onTaskRunsSortChange}
			taskRunSearch={taskRunSearch}
			onTaskRunSearchChange={onTaskRunSearchChange}
			onClearTaskRunFilters={onClearTaskRunFilters}
			// Saved filters props
			currentFilter={currentFilter}
			savedFilters={savedFiltersForMenu}
			onSelectFilter={onSelectFilter}
			onSaveFilter={onSaveFilter}
			onDeleteFilter={onDeleteFilter}
			onSetDefault={onSetDefault}
			onRemoveDefault={onRemoveDefault}
			isSaveDialogOpen={isSaveDialogOpen}
			onCloseSaveDialog={closeSaveDialog}
			onConfirmSave={confirmSave}
		/>
	);
}
