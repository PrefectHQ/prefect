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

const searchParams = z.object({
	tab: z
		.enum(["Logs", "Artifacts", "TaskInputs", "Details"])
		.default("Logs")
		.catch("Logs"),
});

export type TaskRunDetailsTabOptions = z.infer<typeof searchParams>["tab"];

function TaskRunErrorComponent({ error, reset }: ErrorComponentProps) {
	const serverError = categorizeError(error, "Failed to load task run");
	return (
		<div className="flex flex-col gap-4">
			<div>
				<h1 className="text-2xl font-semibold">Task Run</h1>
			</div>
			<RouteErrorState error={serverError} onRetry={reset} />
		</div>
	);
}

export const Route = createFileRoute("/runs/task-run/$id")({
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
	errorComponent: TaskRunErrorComponent,
});

function RouteComponent() {
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
}
