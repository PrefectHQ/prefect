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
import { Skeleton } from "@/components/ui/skeleton";

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
	component: function RouteComponent() {
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
	},
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
	pendingComponent: function FlowRunDetailSkeleton() {
		return (
			<div className="flex flex-col gap-4">
				<div className="flex items-center gap-2">
					<Skeleton className="h-4 w-16" />
					<Skeleton className="h-4 w-4" />
					<Skeleton className="h-6 w-56" />
					<Skeleton className="h-6 w-20 ml-2" />
				</div>
				<div className="rounded-lg border" style={{ height: 200 }}>
					<Skeleton className="h-full w-full" />
				</div>
				<div className="flex gap-2 border-b">
					<Skeleton className="h-9 w-24" />
					<Skeleton className="h-9 w-24" />
					<Skeleton className="h-9 w-24" />
					<Skeleton className="h-9 w-24" />
					<Skeleton className="h-9 w-24" />
				</div>
				<div className="flex flex-col gap-2">
					<Skeleton className="h-4 w-full" />
					<Skeleton className="h-4 w-full" />
					<Skeleton className="h-4 w-full" />
					<Skeleton className="h-4 w-full" />
					<Skeleton className="h-4 w-full" />
					<Skeleton className="h-4 w-full" />
					<Skeleton className="h-4 w-full" />
					<Skeleton className="h-4 w-full" />
				</div>
			</div>
		);
	},
	errorComponent: function FlowRunErrorComponent({
		error,
		reset,
	}: ErrorComponentProps) {
		const serverError = categorizeError(error, "Failed to load flow run");
		return (
			<div className="flex flex-col gap-4">
				<div>
					<h1 className="text-2xl font-semibold">Flow Run</h1>
				</div>
				<RouteErrorState error={serverError} onRetry={reset} />
			</div>
		);
	},
	notFoundComponent: FlowRunNotFound,
});
