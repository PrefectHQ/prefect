import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";
import { buildListArtifactsQuery } from "@/api/artifacts";
import { buildInfiniteFilterLogsQuery } from "@/api/logs";
import { buildGetTaskRunDetailsQuery } from "@/api/task-runs";
import { TaskRunDetailsPage } from "@/components/task-runs/task-run-details-page";

const searchParams = z.object({
	tab: z
		.enum(["Logs", "Artifacts", "TaskInputs", "Details"])
		.default("Logs")
		.catch("Logs"),
});

export type TaskRunDetailsTabOptions = z.infer<typeof searchParams>["tab"];

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
