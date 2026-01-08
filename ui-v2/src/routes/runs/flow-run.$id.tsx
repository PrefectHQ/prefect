import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute, notFound, useNavigate } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";
import { buildListArtifactsQuery } from "@/api/artifacts";
import { categorizeError } from "@/api/error-utils";
import { buildGetFlowRunDetailsQuery } from "@/api/flow-runs";
import { buildInfiniteFilterLogsQuery } from "@/api/logs";
import { buildPaginateTaskRunsQuery } from "@/api/task-runs";
import { FlowRunDetailsPage } from "@/components/flow-runs/flow-run-details-page";
import { FlowRunNotFound } from "@/components/flow-runs/flow-run-not-found";
import { RouteErrorState } from "@/components/ui/route-error-state";

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

function FlowRunErrorComponent({ error, reset }: ErrorComponentProps) {
	const serverError = categorizeError(error, "Failed to load flow run");
	return (
		<div className="flex flex-col gap-4">
			<div>
				<h1 className="text-2xl font-semibold">Flow Run</h1>
			</div>
			<RouteErrorState error={serverError} onRetry={reset} />
		</div>
	);
}

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
		try {
			await queryClient.ensureQueryData(buildGetFlowRunDetailsQuery(params.id));
		} catch (error) {
			// Only treat "not found" errors as 404, rethrow other errors
			if (error instanceof Error && /not found/i.test(error.message)) {
				// eslint-disable-next-line @typescript-eslint/only-throw-error
				throw notFound();
			}
			throw error;
		}
	},
	wrapInSuspense: true,
	errorComponent: FlowRunErrorComponent,
	notFoundComponent: FlowRunNotFound,
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
