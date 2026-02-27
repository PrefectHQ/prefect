import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";
import { buildListArtifactsQuery } from "@/api/artifacts";
import { categorizeError } from "@/api/error-utils";
import { buildInfiniteFilterLogsQuery } from "@/api/logs";
import { buildGetTaskRunDetailsQuery } from "@/api/task-runs";
import { TaskRunDetailsPage } from "@/components/task-runs/task-run-details-page";
import { RouteErrorState } from "@/components/ui/route-error-state";
import { Skeleton } from "@/components/ui/skeleton";

const searchParams = z.object({
	tab: z
		.enum(["Logs", "Artifacts", "TaskInputs", "Details"])
		.default("Logs")
		.catch("Logs"),
});

export type TaskRunDetailsTabOptions = z.infer<typeof searchParams>["tab"];

export const Route = createFileRoute("/runs/task-run/$id")({
	validateSearch: zodValidator(searchParams),
	component: function RouteComponent() {
		const { id } = Route.useParams();
		const { tab } = Route.useSearch();
		const navigate = useNavigate();

		const onTabChange = (tab: TaskRunDetailsTabOptions) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					tab,
				}),
			});
		};

		return <TaskRunDetailsPage id={id} tab={tab} onTabChange={onTabChange} />;
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
					task_run_id: {
						any_: [params.id],
					},
				},
			}),
		);

		void queryClient.prefetchQuery(
			buildListArtifactsQuery({
				artifacts: {
					operator: "and_",
					task_run_id: {
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

		// ----- Critical data
		await queryClient.ensureQueryData(buildGetTaskRunDetailsQuery(params.id));
	},
	wrapInSuspense: true,
	pendingComponent: function TaskRunDetailSkeleton() {
		return (
			<div className="flex flex-col gap-4">
				<div className="flex items-center gap-2">
					<Skeleton className="h-4 w-16" />
					<Skeleton className="h-4 w-4" />
					<Skeleton className="h-4 w-4" />
					<Skeleton className="h-6 w-48" />
					<Skeleton className="h-6 w-20 ml-2" />
				</div>
				<div className="flex gap-2 border-b">
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
	errorComponent: function TaskRunErrorComponent({
		error,
		reset,
	}: ErrorComponentProps) {
		const serverError = categorizeError(error, "Failed to load task run");
		return (
			<div className="flex flex-col gap-4">
				<div>
					<h1 className="text-2xl font-semibold">Task Run</h1>
				</div>
				<RouteErrorState error={serverError} onRetry={reset} />
			</div>
		);
	},
});
