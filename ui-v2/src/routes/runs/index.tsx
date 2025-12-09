import { useSuspenseQueries } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { useCallback, useMemo } from "react";
import { z } from "zod";
import {
	buildCountFlowRunsQuery,
	buildPaginateFlowRunsQuery,
	type FlowRunsPaginateFilter,
} from "@/api/flow-runs";
import { buildCountTaskRunsQuery } from "@/api/task-runs";
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
});

type SearchParams = z.infer<typeof searchParams>;

const buildPaginationBody = (
	search?: SearchParams,
): FlowRunsPaginateFilter => ({
	page: search?.page ?? 1,
	limit: search?.limit ?? 10,
	sort: search?.sort ?? "START_TIME_DESC",
	flow_runs: search?.["hide-subflows"]
		? {
				operator: "and_",
				parent_task_run_id: { operator: "and_", is_null_: true },
			}
		: undefined,
});

export const Route = createFileRoute("/runs/")({
	validateSearch: zodValidator(searchParams),
	component: RouteComponent,
	loaderDeps: ({ search }) => buildPaginationBody(search),
	loader: async ({ deps, context }) => {
		// Await count queries - these don't change on pagination so won't cause suspense issues
		const flowRunsCountResult = await context.queryClient.ensureQueryData(
			buildCountFlowRunsQuery(),
		);

		const taskRunsCountResult = await context.queryClient.ensureQueryData(
			buildCountTaskRunsQuery(),
		);

		// Prefetch paginated flow runs without blocking the loader
		// This allows pagination changes to use placeholderData (keepPreviousData)
		// instead of triggering a full route-level Suspense fallback
		void context.queryClient.prefetchQuery(
			buildPaginateFlowRunsQuery(deps, 30_000),
		);

		return {
			flowRunsCountResult,
			taskRunsCountResult,
		};
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

function RouteComponent() {
	const search = Route.useSearch();
	const [pagination, onPaginationChange] = usePagination();
	const [sort, onSortChange] = useSort();
	const [hideSubflows, onHideSubflowsChange] = useHideSubflows();
	const [tab, onTabChange] = useTab();

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
			sort={sort}
			onSortChange={onSortChange}
			hideSubflows={hideSubflows}
			onHideSubflowsChange={onHideSubflowsChange}
		/>
	);
}
