import { useSuspenseQueries } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { useCallback, useMemo } from "react";
import { z } from "zod";
import { buildFilterDeploymentsQuery } from "@/api/deployments";
import {
	buildCountFlowRunsQuery,
	buildFilterFlowRunsQuery,
	type FlowRunsFilter,
} from "@/api/flow-runs";
import {
	buildDeploymentsCountByFlowQuery,
	buildFLowDetailsQuery,
} from "@/api/flows";
import {
	buildCountTaskRunsQuery,
	buildTaskRunsHistoryQuery,
} from "@/api/task-runs";
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
} from "@/components/flows/detail/flow-stats-summary";

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
		"runs.page": z.number().int().nonnegative().optional().default(0),
		"runs.limit": z.number().int().positive().max(100).optional().default(10),
		"runs.sort": z
			.enum(["START_TIME_DESC", "START_TIME_ASC", "EXPECTED_START_TIME_DESC"])
			.optional()
			.default("START_TIME_DESC"),
		"runs.flowRuns.nameLike": z.string().optional(),
		"runs.flowRuns.state.name": z.array(z.string()).optional(),
		type: z.enum(["span", "range"]).optional(),
		seconds: z.number().int().positive().optional(),
		startDateTime: z.date().optional(),
		endDateTime: z.date().optional(),
		"deployments.page": z.number().int().nonnegative().optional().default(0),
		"deployments.limit": z.number().int().positive().optional().default(10),
	})
	.optional()
	.default({});

const filterFlowRunsBySearchParams = (
	search: z.infer<typeof searchParams>,
): FlowRunsFilter => {
	const filter: FlowRunsFilter = {
		sort: search["runs.sort"],
		limit: search["runs.limit"],
		offset: search["runs.page"] * search["runs.limit"],
		flow_runs: {
			operator: "and_",
			state: {
				operator: "and_",
				name: {
					any_: search["runs.flowRuns.state.name"],
				},
			},
			name: {
				like_: search["runs.flowRuns.nameLike"],
			},
		},
	};
	return filter;
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
					"runs.page": 0,
				}),
			});
		},
		[navigate],
	);

	return { selectedStates, onSelectFilter };
};

const FlowDetailRoute = () => {
	const { id } = Route.useParams();
	const search = Route.useSearch();
	const { selectedStates, onSelectFilter } = useStateFilter();
	const [{ data: flow }, { data: flowRuns }, { data: deployments }] =
		useSuspenseQueries({
			queries: [
				buildFLowDetailsQuery(id),
				buildFilterFlowRunsQuery({
					...filterFlowRunsBySearchParams(search),
					flows: { operator: "and_", id: { any_: [id] } },
				}),
				buildFilterDeploymentsQuery({
					sort: "CREATED_DESC",
					offset: search["deployments.page"] * search["deployments.limit"],
					limit: search["deployments.limit"],
					flows: { operator: "and_", id: { any_: [id] } },
				}),
			],
		});

	return (
		<FlowDetail
			flow={flow}
			flowRuns={flowRuns}
			deployments={deployments}
			tab={search.tab}
			selectedStates={selectedStates}
			onSelectFilter={onSelectFilter}
		/>
	);
};

export const Route = createFileRoute("/flows/flow/$id")({
	component: FlowDetailRoute,
	validateSearch: zodValidator(searchParams),
	loaderDeps: ({ search }) => search,
	loader: ({ params: { id }, context, deps }) => {
		const REFETCH_INTERVAL = 30_000;

		void context.queryClient.prefetchQuery(buildFLowDetailsQuery(id));
		void context.queryClient.prefetchQuery(
			buildFilterFlowRunsQuery({
				...filterFlowRunsBySearchParams(deps),
				flows: { operator: "and_", id: { any_: [id] } },
			}),
		);
		void context.queryClient.prefetchQuery(
			buildCountFlowRunsQuery({
				flows: { operator: "and_", id: { any_: [id] } },
			}),
		);
		void context.queryClient.prefetchQuery(
			buildFilterDeploymentsQuery({
				sort: "CREATED_DESC",
				offset: deps["runs.page"] * deps["runs.limit"],
				limit: deps["runs.limit"],
				flows: { operator: "and_", id: { any_: [id] } },
			}),
		);
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
	},
	wrapInSuspense: true,
});
