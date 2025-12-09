import { useQueryClient, useSuspenseQueries } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { secondsInDay } from "date-fns/constants";
import {
	useCallback,
	useDeferredValue,
	useEffect,
	useMemo,
	useState,
} from "react";
import { z } from "zod";
import { buildFilterDeploymentsQuery } from "@/api/deployments";
import {
	buildCountFlowRunsQuery,
	buildPaginateFlowRunsQuery,
	type FlowRunsPaginateFilter,
} from "@/api/flow-runs";
import { buildListFlowsQuery } from "@/api/flows";
import {
	buildCountTaskRunsQuery,
	buildGetFlowRunsTaskRunsCountQuery,
} from "@/api/task-runs";
import { buildFilterWorkPoolsQuery } from "@/api/work-pools";
import {
	type PaginationState,
	SORT_FILTERS,
	type SortFilters,
} from "@/components/flow-runs/flow-runs-list";
import { RunsPage } from "@/components/runs/runs-page";
import type { DateRangeSelectValue } from "@/components/ui/date-range-select";

// Default date range: Past 7 days
const DEFAULT_DATE_RANGE: DateRangeSelectValue = {
	type: "span",
	seconds: -secondsInDay * 7,
};

// Zod schema for date range select value
const dateRangeSelectValueSchema = z.discriminatedUnion("type", [
	z.object({
		type: z.literal("span"),
		seconds: z.number(),
	}),
	z.object({
		type: z.literal("range"),
		startDate: z.coerce.date(),
		endDate: z.coerce.date(),
	}),
	z.object({
		type: z.literal("around"),
		date: z.coerce.date(),
		quantity: z.number(),
		unit: z.enum(["second", "minute", "hour", "day"]),
	}),
	z.object({
		type: z.literal("period"),
		period: z.literal("Today"),
	}),
]);

const searchParams = z.object({
	tab: z.enum(["flow-runs", "task-runs"]).optional().default("flow-runs"),
	page: z.number().int().positive().optional().default(1).catch(1),
	limit: z.number().int().positive().optional().default(10).catch(10),
	sort: z.enum(SORT_FILTERS).optional().default("START_TIME_DESC"),
	"hide-subflows": z.boolean().optional().default(false),
	// Filter parameters
	"flow-run-search": z.string().optional().catch(""),
	state: z.array(z.string()).optional().catch([]),
	flow: z.array(z.string()).optional().catch([]),
	deployment: z.array(z.string()).optional().catch([]),
	workPool: z.array(z.string()).optional().catch([]),
	tag: z.array(z.string()).optional().catch([]),
	range: dateRangeSelectValueSchema.optional().catch(DEFAULT_DATE_RANGE),
});

type SearchParams = z.infer<typeof searchParams>;

/**
 * Converts a DateRangeSelectValue to start/end dates for API filtering
 */
const getDateRangeForFilter = (
	range: DateRangeSelectValue | undefined,
): { startDate: Date; endDate: Date } | null => {
	if (!range) return null;

	const now = new Date();

	switch (range.type) {
		case "span": {
			const endDate = now;
			const startDate = new Date(now.getTime() + range.seconds * 1000);
			return range.seconds < 0
				? { startDate, endDate }
				: { startDate: endDate, endDate: startDate };
		}
		case "range":
			return { startDate: range.startDate, endDate: range.endDate };
		case "around": {
			const multiplier =
				range.unit === "second"
					? 1000
					: range.unit === "minute"
						? 60 * 1000
						: range.unit === "hour"
							? 60 * 60 * 1000
							: 24 * 60 * 60 * 1000;
			const offset = range.quantity * multiplier;
			return {
				startDate: new Date(range.date.getTime() - offset),
				endDate: new Date(range.date.getTime() + offset),
			};
		}
		case "period":
			if (range.period === "Today") {
				const startDate = new Date(now);
				startDate.setHours(0, 0, 0, 0);
				const endDate = new Date(now);
				endDate.setHours(23, 59, 59, 999);
				return { startDate, endDate };
			}
			return null;
		default:
			return null;
	}
};

const buildPaginationBody = (search?: SearchParams): FlowRunsPaginateFilter => {
	const dateRange = getDateRangeForFilter(search?.range);

	// Build flow_runs filter with all conditions
	const flowRunsFilter: FlowRunsPaginateFilter["flow_runs"] = {
		operator: "and_",
		// Hide subflows filter
		parent_task_run_id: search?.["hide-subflows"]
			? { operator: "and_", is_null_: true }
			: undefined,
		// Search by name
		name: search?.["flow-run-search"]
			? { like_: search["flow-run-search"] }
			: undefined,
		// State filter
		state: search?.state?.length ? { name: { any_: search.state } } : undefined,
		// Deployment filter
		deployment_id: search?.deployment?.length
			? { any_: search.deployment }
			: undefined,
		// Date range filter
		expected_start_time: dateRange
			? {
					after_: dateRange.startDate.toISOString(),
					before_: dateRange.endDate.toISOString(),
				}
			: undefined,
		// Tags filter
		tags: search?.tag?.length
			? { operator: "and_", all_: search.tag }
			: undefined,
	};

	return {
		page: search?.page ?? 1,
		limit: search?.limit ?? 10,
		sort: search?.sort ?? "START_TIME_DESC",
		flow_runs: flowRunsFilter,
		// Flow filter
		flows: search?.flow?.length
			? { operator: "and_", id: { any_: search.flow } }
			: undefined,
		// Work pool filter
		work_pools: search?.workPool?.length
			? { operator: "and_", name: { any_: search.workPool } }
			: undefined,
	};
};

export const Route = createFileRoute("/runs/")({
	validateSearch: zodValidator(searchParams),
	component: RouteComponent,
	loaderDeps: ({ search }) => buildPaginationBody(search),
	loader: ({ deps, context }) => {
		// Prefetch all queries without blocking the loader
		// This allows the component to render immediately and use placeholderData
		void context.queryClient.prefetchQuery(buildCountFlowRunsQuery());
		void context.queryClient.prefetchQuery(buildCountTaskRunsQuery());
		void context.queryClient.prefetchQuery(
			buildPaginateFlowRunsQuery(deps, 30_000),
		);

		// Prefetch filter data for comboboxes
		void context.queryClient.prefetchQuery(
			buildListFlowsQuery({ offset: 0, sort: "NAME_ASC" }),
		);
		void context.queryClient.prefetchQuery(
			buildFilterDeploymentsQuery({ offset: 0, sort: "NAME_ASC" }),
		);
		void context.queryClient.prefetchQuery(
			buildFilterWorkPoolsQuery({ offset: 0 }),
		);

		// Background async chain: prefetch task run counts for each flow run
		// This prevents suspense when FlowRunCard renders
		void (async () => {
			const pageData = await context.queryClient.ensureQueryData(
				buildPaginateFlowRunsQuery(deps, 30_000),
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

/**
 * Hook to manage flow runs filters with URL state
 */
const useFlowRunsFilters = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	// Local state for debounced search input
	const [localSearch, setLocalSearch] = useState(
		search["flow-run-search"] ?? "",
	);
	const deferredSearch = useDeferredValue(localSearch);

	// Update URL when deferred search changes
	const onSearchChange = useCallback(
		(value: string) => {
			setLocalSearch(value);
			// Debounce the URL update
			const timeoutId = setTimeout(() => {
				void navigate({
					to: ".",
					search: (prev) => ({
						...prev,
						"flow-run-search": value || undefined,
						page: 1,
					}),
					replace: true,
				});
			}, 1200);
			return () => clearTimeout(timeoutId);
		},
		[navigate],
	);

	const onStateChange = useCallback(
		(states: string[]) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					state: states.length > 0 ? states : undefined,
					page: 1,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	const onFlowChange = useCallback(
		(flows: string[]) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					flow: flows.length > 0 ? flows : undefined,
					page: 1,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	const onDeploymentChange = useCallback(
		(deployments: string[]) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					deployment: deployments.length > 0 ? deployments : undefined,
					page: 1,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	const onWorkPoolChange = useCallback(
		(workPools: string[]) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					workPool: workPools.length > 0 ? workPools : undefined,
					page: 1,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	const onTagChange = useCallback(
		(tags: string[]) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					tag: tags.length > 0 ? tags : undefined,
					page: 1,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	const onDateRangeChange = useCallback(
		(range: DateRangeSelectValue) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					range,
					page: 1,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	const onClearFilters = useCallback(() => {
		void navigate({
			to: ".",
			search: (prev) => ({
				...prev,
				"flow-run-search": undefined,
				state: undefined,
				flow: undefined,
				deployment: undefined,
				workPool: undefined,
				tag: undefined,
				range: DEFAULT_DATE_RANGE,
				page: 1,
			}),
			replace: true,
		});
		setLocalSearch("");
	}, [navigate]);

	const hasActiveFilters = useMemo(() => {
		return (
			!!search["flow-run-search"] ||
			(search.state?.length ?? 0) > 0 ||
			(search.flow?.length ?? 0) > 0 ||
			(search.deployment?.length ?? 0) > 0 ||
			(search.workPool?.length ?? 0) > 0 ||
			(search.tag?.length ?? 0) > 0 ||
			(search.range &&
				JSON.stringify(search.range) !== JSON.stringify(DEFAULT_DATE_RANGE))
		);
	}, [search]);

	return {
		search: localSearch,
		deferredSearch,
		state: search.state ?? [],
		flow: search.flow ?? [],
		deployment: search.deployment ?? [],
		workPool: search.workPool ?? [],
		tag: search.tag ?? [],
		range: search.range ?? DEFAULT_DATE_RANGE,
		hasActiveFilters,
		onSearchChange,
		onStateChange,
		onFlowChange,
		onDeploymentChange,
		onWorkPoolChange,
		onTagChange,
		onDateRangeChange,
		onClearFilters,
	};
};

function RouteComponent() {
	const queryClient = useQueryClient();
	const search = Route.useSearch();
	const [pagination, onPaginationChange] = usePagination();
	const [sort, onSortChange] = useSort();
	const [hideSubflows, onHideSubflowsChange] = useHideSubflows();
	const [tab, onTabChange] = useTab();
	const filters = useFlowRunsFilters();

	const [
		{ data: flowRunsCount },
		{ data: taskRunsCount },
		{ data: flowRunsPage },
		{ data: flows },
		{ data: deployments },
		{ data: workPools },
	] = useSuspenseQueries({
		queries: [
			buildCountFlowRunsQuery(),
			buildCountTaskRunsQuery(),
			buildPaginateFlowRunsQuery(buildPaginationBody(search), 30_000),
			buildListFlowsQuery({ offset: 0, sort: "NAME_ASC" }),
			buildFilterDeploymentsQuery({ offset: 0, sort: "NAME_ASC" }),
			buildFilterWorkPoolsQuery({ offset: 0 }),
		],
	});

	const flowRuns = flowRunsPage?.results ?? [];

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
			filters={filters}
			flows={flows ?? []}
			deployments={deployments ?? []}
			workPools={workPools ?? []}
		/>
	);
}
