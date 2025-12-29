import {
	useQuery,
	useQueryClient,
	useSuspenseQueries,
} from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { useCallback, useEffect, useMemo } from "react";
import { z } from "zod";
import { buildPaginateDeploymentsQuery } from "@/api/deployments";
import {
	buildCountFlowRunsQuery,
	buildFilterFlowRunsQuery,
	buildPaginateFlowRunsQuery,
	type FlowRunsPaginateFilter,
} from "@/api/flow-runs";
import {
	buildDeploymentsCountByFlowQuery,
	buildFLowDetailsQuery,
} from "@/api/flows";
import type { components } from "@/api/prefect";
import {
	buildCountTaskRunsQuery,
	buildGetFlowRunsTaskRunsCountQuery,
	buildTaskRunsHistoryQuery,
} from "@/api/task-runs";
import {
	type PaginationState,
	SORT_FILTERS,
	type SortFilters,
} from "@/components/flow-runs/flow-runs-list";
import type { FlowRunState } from "@/components/flow-runs/flow-runs-list/flow-runs-filters/state-filters.constants";
import FlowDetail from "@/components/flows/detail";
import {
	buildCompletedTaskRunsCountFilter,
	buildFailedTaskRunsCountFilter,
	buildFlowRunsCountFilterForHistory,
	buildFlowRunsHistoryFilter,
	buildRunningTaskRunsCountFilter,
	buildTaskRunsHistoryFilterForFlow,
	buildTotalTaskRunsCountFilter,
} from "@/components/flows/detail/flow-stats-summary/query-filters";
import { usePageTitle } from "@/hooks/use-page-title";

// Route for /flows/flow/$id

// This file contains the route definition and loader function for the /flows/flow/$id route.

// 1. searchParams defined as a zod schema for validating and typechecking the search query.
// 2. filterFlowRunsBySearchParams function that takes a search object and returns a filter for flow runs.
// 3. Route definition using createFileRoute function:
//    - It uses useSuspenseQueries to fetch data for the flow, flow runs, deployments, and related counts.
//    - Passes the fetched data to the FlowDetail component.
//    - Includes a loader function to prefetch data on the server side.

const searchParams = z
	.object({
		tab: z.enum(["runs", "deployments", "details"]).optional().default("runs"),
		"runs.page": z.number().int().positive().optional().default(1),
		"runs.limit": z.number().int().positive().max(100).optional().default(10),
		"runs.sort": z.enum(SORT_FILTERS).optional().default("START_TIME_DESC"),
		"runs.flowRuns.nameLike": z.string().optional().default(""),
		"runs.flowRuns.state.name": z.array(z.string()).optional(),
		type: z.enum(["span", "range"]).optional(),
		seconds: z.number().int().positive().optional(),
		startDateTime: z.date().optional(),
		endDateTime: z.date().optional(),
		"deployments.page": z.number().int().positive().optional().default(1),
		"deployments.limit": z.number().int().positive().optional().default(10),
		"deployments.nameLike": z.string().optional(),
		"deployments.tags": z.array(z.string()).optional(),
		"deployments.sort": z
			.enum(["CREATED_DESC", "UPDATED_DESC", "NAME_ASC", "NAME_DESC"])
			.optional()
			.default("NAME_ASC"),
	})
	.optional()
	.default({});

type SearchParams = z.infer<typeof searchParams>;

const buildPaginationBody = (
	search: SearchParams,
	flowId: string,
): FlowRunsPaginateFilter => {
	const flowRunSearch = search["runs.flowRuns.nameLike"];
	const stateFilters = search["runs.flowRuns.state.name"] ?? [];

	const hasFilters = flowRunSearch || stateFilters.length > 0;
	const flowRunsFilter = hasFilters
		? {
				operator: "and_" as const,
				...(flowRunSearch && {
					name: { like_: flowRunSearch },
				}),
				...(stateFilters.length > 0 && {
					state: {
						operator: "and_" as const,
						name: { any_: stateFilters },
					},
				}),
			}
		: undefined;

	return {
		page: search["runs.page"],
		limit: search["runs.limit"],
		sort: search["runs.sort"],
		flow_runs: flowRunsFilter,
		flows: { operator: "and_" as const, id: { any_: [flowId] } },
	};
};

const usePagination = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const pagination: PaginationState = useMemo(
		() => ({
			page: search["runs.page"],
			limit: search["runs.limit"],
		}),
		[search["runs.page"], search["runs.limit"]],
	);

	const onPaginationChange = useCallback(
		(newPagination: PaginationState) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					"runs.page": newPagination.page,
					"runs.limit": newPagination.limit,
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
				search: (prev) => ({ ...prev, "runs.sort": sort, "runs.page": 1 }),
				replace: true,
			});
		},
		[navigate],
	);

	return [search["runs.sort"], onSortChange] as const;
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
					"runs.flowRuns.nameLike": flowRunSearch,
					"runs.page": 1,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	return [search["runs.flowRuns.nameLike"], onFlowRunSearchChange] as const;
};

const useStateFilter = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const selectedStates = useMemo(
		() => new Set((search["runs.flowRuns.state.name"] || []) as FlowRunState[]),
		[search["runs.flowRuns.state.name"]],
	);

	const onSelectFilter = useCallback(
		(states: Set<FlowRunState>) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					"runs.flowRuns.state.name": Array.from(states),
					"runs.page": 1,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	return { selectedStates, onSelectFilter };
};

const useDeploymentSearch = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const onDeploymentSearchChange = useCallback(
		(deploymentSearch: string) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					"deployments.nameLike": deploymentSearch || undefined,
					"deployments.page": 1,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	return [search["deployments.nameLike"], onDeploymentSearchChange] as const;
};

const useDeploymentTagsFilter = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const onDeploymentTagsChange = useCallback(
		(tags: string[]) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					"deployments.tags": tags.length > 0 ? tags : undefined,
					"deployments.page": 1,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	return [search["deployments.tags"] ?? [], onDeploymentTagsChange] as const;
};

const useDeploymentSort = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const onDeploymentSortChange = useCallback(
		(sort: components["schemas"]["DeploymentSort"]) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					"deployments.sort": sort,
					"deployments.page": 1,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	return [search["deployments.sort"], onDeploymentSortChange] as const;
};

const useDeploymentPagination = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const deploymentPagination = useMemo(
		() => ({
			page: search["deployments.page"],
			limit: search["deployments.limit"],
		}),
		[search["deployments.page"], search["deployments.limit"]],
	);

	const onDeploymentPaginationChange = useCallback(
		(newPagination: { page: number; limit: number }) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					"deployments.page": newPagination.page,
					"deployments.limit": newPagination.limit,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	return [deploymentPagination, onDeploymentPaginationChange] as const;
};

const FlowDetailRoute = () => {
	const queryClient = useQueryClient();
	const { id } = Route.useParams();
	const search = Route.useSearch();

	// Navigation hooks for flow runs
	const [pagination, onPaginationChange] = usePagination();
	const [sort, onSortChange] = useSort();
	const [flowRunSearch, onFlowRunSearchChange] = useFlowRunSearch();
	const { selectedStates, onSelectFilter } = useStateFilter();

	// Navigation hooks for deployments
	const [deploymentSearch, onDeploymentSearchChange] = useDeploymentSearch();
	const [deploymentTags, onDeploymentTagsChange] = useDeploymentTagsFilter();
	const [deploymentSort, onDeploymentSortChange] = useDeploymentSort();
	const [deploymentPagination, onDeploymentPaginationChange] =
		useDeploymentPagination();

	// Suspense queries for stable data (flow)
	const [{ data: flow }] = useSuspenseQueries({
		queries: [buildFLowDetailsQuery(id)],
	});

	// Use useQuery for deployments to leverage placeholderData: keepPreviousData
	// This prevents the page from suspending when search/filter changes
	const { data: deploymentsPage } = useQuery(
		buildPaginateDeploymentsQuery({
			sort: search["deployments.sort"],
			page: search["deployments.page"],
			limit: search["deployments.limit"],
			flows: { operator: "and_", id: { any_: [id] } },
			deployments: {
				operator: "and_",
				flow_or_deployment_name: { like_: search["deployments.nameLike"] },
				tags: { operator: "and_", all_: search["deployments.tags"] || [] },
			},
		}),
	);

	// Set page title based on flow name
	usePageTitle(flow?.name ? `Flow: ${flow.name}` : "Flow");

	// Use useQuery for paginated flow runsto leverage placeholderData: keepPreviousData
	// This prevents the page from suspending when search/filter changes
	const { data: flowRunsPage } = useQuery(
		buildPaginateFlowRunsQuery(buildPaginationBody(search, id), 30_000),
	);

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

	// Prefetch handler for pagination hover
	const onPrefetchPage = useCallback(
		(page: number) => {
			const filter = buildPaginationBody(
				{
					...search,
					"runs.page": page,
				},
				id,
			);
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
		[queryClient, search, id],
	);

	return (
		<FlowDetail
			flow={flow}
			flowRuns={flowRuns}
			flowRunsCount={flowRunsPage?.count ?? 0}
			flowRunsPages={flowRunsPage?.pages ?? 0}
			deployments={deploymentsPage?.results ?? []}
			deploymentsCount={deploymentsPage?.count ?? 0}
			deploymentsPages={deploymentsPage?.pages ?? 0}
			tab={search.tab}
			pagination={pagination}
			onPaginationChange={onPaginationChange}
			onPrefetchPage={onPrefetchPage}
			sort={sort}
			onSortChange={onSortChange}
			flowRunSearch={flowRunSearch}
			onFlowRunSearchChange={onFlowRunSearchChange}
			selectedStates={selectedStates}
			onSelectFilter={onSelectFilter}
			deploymentSearch={deploymentSearch}
			onDeploymentSearchChange={onDeploymentSearchChange}
			deploymentTags={deploymentTags}
			onDeploymentTagsChange={onDeploymentTagsChange}
			deploymentSort={deploymentSort}
			onDeploymentSortChange={onDeploymentSortChange}
			deploymentPagination={deploymentPagination}
			onDeploymentPaginationChange={onDeploymentPaginationChange}
		/>
	);
};

export const Route = createFileRoute("/flows/flow/$id")({
	component: FlowDetailRoute,
	validateSearch: zodValidator(searchParams),
	loaderDeps: ({ search }) => ({
		flowRunsDeps: search,
	}),
	loader: ({ params: { id }, context, deps }) => {
		const REFETCH_INTERVAL = 30_000;

		// Prefetch flow details
		void context.queryClient.prefetchQuery(buildFLowDetailsQuery(id));

		// Prefetch paginated flow runs without blocking (uses keepPreviousData)
		void context.queryClient.prefetchQuery(
			buildPaginateFlowRunsQuery(
				buildPaginationBody(deps.flowRunsDeps, id),
				30_000,
			),
		);

		// Prefetch deployments with filter parameters
		void context.queryClient.prefetchQuery(
			buildPaginateDeploymentsQuery({
				sort: deps.flowRunsDeps["deployments.sort"],
				page: deps.flowRunsDeps["deployments.page"],
				limit: deps.flowRunsDeps["deployments.limit"],
				flows: { operator: "and_", id: { any_: [id] } },
				deployments: {
					operator: "and_",
					flow_or_deployment_name: {
						like_: deps.flowRunsDeps["deployments.nameLike"],
					},
					tags: {
						operator: "and_",
						all_: deps.flowRunsDeps["deployments.tags"] || [],
					},
				},
			}),
		);

		// Prefetch deployments count
		void context.queryClient.prefetchQuery(
			buildDeploymentsCountByFlowQuery([id]),
		);

		// Prefetch FlowStatsSummary queries
		// FlowRunsHistoryCard queries
		void context.queryClient.prefetchQuery(
			buildFilterFlowRunsQuery(
				buildFlowRunsHistoryFilter(id, 60),
				REFETCH_INTERVAL,
			),
		);
		void context.queryClient.prefetchQuery(
			buildCountFlowRunsQuery(
				buildFlowRunsCountFilterForHistory(id),
				REFETCH_INTERVAL,
			),
		);

		// CumulativeTaskRunsCard queries
		void context.queryClient.prefetchQuery(
			buildCountTaskRunsQuery(
				buildTotalTaskRunsCountFilter(id),
				REFETCH_INTERVAL,
			),
		);
		void context.queryClient.prefetchQuery(
			buildCountTaskRunsQuery(
				buildCompletedTaskRunsCountFilter(id),
				REFETCH_INTERVAL,
			),
		);
		void context.queryClient.prefetchQuery(
			buildCountTaskRunsQuery(
				buildFailedTaskRunsCountFilter(id),
				REFETCH_INTERVAL,
			),
		);
		void context.queryClient.prefetchQuery(
			buildCountTaskRunsQuery(
				buildRunningTaskRunsCountFilter(id),
				REFETCH_INTERVAL,
			),
		);
		void context.queryClient.prefetchQuery(
			buildTaskRunsHistoryQuery(
				buildTaskRunsHistoryFilterForFlow(id),
				REFETCH_INTERVAL,
			),
		);

		// Background async chain: prefetch task run counts for each flow run
		// This prevents suspense when FlowRunCard renders
		void (async () => {
			const pageData = await context.queryClient.ensureQueryData(
				buildPaginateFlowRunsQuery(
					buildPaginationBody(deps.flowRunsDeps, id),
					30_000,
				),
			);
			const flowRunIds = pageData?.results?.map((run) => run.id) ?? [];
			if (flowRunIds.length > 0) {
				void context.queryClient.prefetchQuery(
					buildGetFlowRunsTaskRunsCountQuery(flowRunIds),
				);
			}
		})();

		// Ensure flow details are loaded (critical data)
		return context.queryClient.ensureQueryData(buildFLowDetailsQuery(id));
	},
	wrapInSuspense: true,
});
