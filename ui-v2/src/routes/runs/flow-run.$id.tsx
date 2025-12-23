import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";
import { buildListArtifactsQuery } from "@/api/artifacts";
import { buildGetFlowRunDetailsQuery } from "@/api/flow-runs";
import { buildInfiniteFilterLogsQuery } from "@/api/logs";
import { buildPaginateTaskRunsQuery } from "@/api/task-runs";
import { FlowRunDetailsPage } from "@/components/flow-runs/flow-run-details-page";

const searchParams = z.object({
	tab: z
		.enum([
			"Logs",
			"TaskRuns",
			"SubflowRuns",
			"Artifacts",
			"Details",
			"Parameters",
			"JobVariables",
		])
		.default("Logs")
		.catch("Logs"),
});

export type FlowRunDetailsTabOptions = z.infer<typeof searchParams>["tab"];

export const Route = createFileRoute("/runs/flow-run/$id")({
	validateSearch: zodValidator(searchParams),
	component: RouteComponent,
	loader: async ({ params, context: { queryClient } }) => {
		// ----- Deferred data
		void queryClient.prefetchInfiniteQuery(
			buildInfiniteFilterLogsQuery({
				limit: 50,
				sort: "TIMESTAMP_ASC",
				logs: {
					operator: "and_",
					level: {
						ge_: 0,
					},
					flow_run_id: {
						any_: [params.id],
					},
				},
			}),
		);

		void queryClient.prefetchQuery(
			buildListArtifactsQuery({
				artifacts: {
					operator: "and_",
					flow_run_id: {
						any_: [params.id],
					},
					type: {
						not_any_: ["result"],
					},
				},
				sort: "ID_DESC",
				offset: 0,
			}),
		);

		void queryClient.prefetchQuery(
			buildPaginateTaskRunsQuery({
				page: 1,
				sort: "EXPECTED_START_TIME_DESC",
				flow_runs: {
					operator: "and_",
					id: {
						any_: [params.id],
					},
				},
			}),
		);

		// ----- Critical data
		await queryClient.ensureQueryData(buildGetFlowRunDetailsQuery(params.id));
	},
	wrapInSuspense: true,
});

function RouteComponent() {
	const { id } = Route.useParams();
	const { tab } = Route.useSearch();
	const navigate = useNavigate();

	const onTabChange = (tab: FlowRunDetailsTabOptions) => {
		void navigate({
			to: ".",
			search: (prev) => ({
				...prev,
				tab,
			}),
		});
	};

	return <FlowRunDetailsPage id={id} tab={tab} onTabChange={onTabChange} />;
}
