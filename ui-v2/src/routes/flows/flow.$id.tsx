import { useSuspenseQueries } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router"; // Import createFileRoute function from @tanstack/react-router
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";
import type { components } from "@/api/prefect";
import FlowDetail from "@/components/flows/detail";
import { FlowQuery } from "@/components/flows/queries";

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
): components["schemas"]["Body_read_flow_runs_flow_runs_filter_post"] => {
	const filter: components["schemas"]["Body_read_flow_runs_flow_runs_filter_post"] =
		{
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

const FlowDetailRoute = () => {
	const { id } = Route.useParams();
	const search = Route.useSearch();
	const flowQuery = new FlowQuery(id);
	const [
		{ data: flow },
		{ data: flowRuns },
		{ data: activity },
		{ data: deployments },
	] = useSuspenseQueries({
		queries: [
			flowQuery.getQueryParams(),
			flowQuery.getFlowRunsQueryParams(filterFlowRunsBySearchParams(search)),
			flowQuery.getLatestFlowRunsQueryParams(60),
			flowQuery.getDeploymentsQueryParams({
				sort: "CREATED_DESC",
				offset: search["deployments.page"] * search["deployments.limit"],
				limit: search["deployments.limit"],
			}),
		],
	});

	return (
		<FlowDetail
			flow={flow}
			flowRuns={flowRuns}
			deployments={deployments}
			activity={activity}
			tab={search.tab}
		/>
	);
};

export const Route = createFileRoute("/flows/flow/$id")({
	component: FlowDetailRoute,
	validateSearch: zodValidator(searchParams),
	loaderDeps: ({ search }) => search,
	loader: async ({ params: { id }, context, deps }) => {
		const flow = new FlowQuery(id);
		return await Promise.all([
			context.queryClient.ensureQueryData(flow.getQueryParams()),
			context.queryClient.ensureQueryData(
				flow.getFlowRunsQueryParams(filterFlowRunsBySearchParams(deps)),
			),
			context.queryClient.ensureQueryData(flow.getFlowRunsCountQueryParams()),
			context.queryClient.ensureQueryData(
				flow.getDeploymentsQueryParams({
					sort: "CREATED_DESC",
					offset: deps["runs.page"] * deps["runs.limit"],
					limit: deps["runs.limit"],
				}),
			),
			context.queryClient.ensureQueryData(
				flow.getDeploymentsCountQueryParams(),
			),
		]);
	},
	wrapInSuspense: true,
});
