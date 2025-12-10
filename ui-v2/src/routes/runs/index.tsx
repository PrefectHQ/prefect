import { useQueryClient, useSuspenseQueries } from "@tanstack/react-query";
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
} from "@/api/task-runs";
import {
	type PaginationState,
	SORT_FILTERS,
	type SortFilters,
} from "@/components/flow-runs/flow-runs-list";
import { RunsPage } from "@/components/runs/runs-page";

const searchParams = z.object({
	tab: z.enum(["flow-runs", "task-runs"]).optional().default("flow-runs"),
	page: z.number().int().positive().optional().default(1).catch(1),
	limit: z.number().int().positive().optional().default(10).catch(10),
	sort: z.enum(SORT_FILTERS).optional().default("START_TIME_DESC"),
	"hide-subflows": z.boolean().optional().default(false),
	"flow-run-search": z.string().optional().default(""),
});

type SearchParams = z.infer<typeof searchParams>;

const buildPaginationBody = (search?: SearchParams): FlowRunsPaginateFilter => {
	const hideSubflows = search?.["hide-subflows"];
	const flowRunSearch = search?.["flow-run-search"];

	// Build flow_runs filter only if we have filters to apply
	const hasFilters = hideSubflows || flowRunSearch;
	const flowRunsFilter = hasFilters
		? {
				operator: "and_" as const,
				...(hideSubflows && {
					parent_task_run_id: { operator: "and_" as const, is_null_: true },
				}),
				...(flowRunSearch && {
					name: { like_: flowRunSearch },
				}),
			}
		: undefined;

	return {
		page: search?.page ?? 1,
		limit: search?.limit ?? 10,
		sort: search?.sort ?? "START_TIME_DESC",
		flow_runs: flowRunsFilter,
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

function RouteComponent() {
	const queryClient = useQueryClient();
	const search = Route.useSearch();
	const [pagination, onPaginationChange] = usePagination();
	const [sort, onSortChange] = useSort();
	const [hideSubflows, onHideSubflowsChange] = useHideSubflows();
	const [tab, onTabChange] = useTab();
	const [flowRunSearch, onFlowRunSearchChange] = useFlowRunSearch();

	const [
		{ data: flowRunsCount },
		{ data: taskRunsCount },
		{ data: flowRunsPage },
	] = useSuspenseQueries({
		queries: [
			buildCountFlowRunsQuery(),
			buildCountTaskRunsQuery(),
			buildPaginateFlowRunsQuery(buildPaginationBody(search), 30_000),
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
			flowRunSearch={flowRunSearch}
			onFlowRunSearchChange={onFlowRunSearchChange}
		/>
	);
}
