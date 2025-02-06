import {
	Artifact,
	ArtifactWithFlowRunAndTaskRun,
	ArtifactsFilter,
	buildListArtifactsQuery,
} from "@/api/artifacts";
import { buildListFlowRunsQuery } from "@/api/flow-runs";
import { buildListTaskRunsQuery } from "@/api/task-runs";
import { ArtifactsKeyPage } from "@/components/artifacts/key/artifacts-key-page";
import { createFileRoute } from "@tanstack/react-router";

const buildFilterBody = (key: string): ArtifactsFilter => ({
	artifacts: {
		operator: "and_", // Logical operator for combining filters
		key: {
			like_: key, // Filter by artifact name
		},
	},
	sort: "CREATED_DESC",
	offset: 0,
});

export const Route = createFileRoute("/artifacts/key/$key")({
	component: RouteComponent,
	loader: async ({ context, params }) => {
		console.log("we made it");
		const { key } = params;

		const artifacts = await context.queryClient.ensureQueryData(
			buildListArtifactsQuery(buildFilterBody(key)),
		);

		const flowRunIds = artifacts.map(
			(artifact) => artifact.flow_run_id as string,
		);
		const taskRunIds = artifacts.map(
			(artifact) => artifact.task_run_id as string,
		);

		// Prefetch flow runs
		const flowRuns = await context.queryClient.ensureQueryData(
			buildListFlowRunsQuery({
				flow_runs: {
					operator: "and_",
					id: {
						any_: flowRunIds,
					},
				},
				sort: "ID_DESC",
				offset: 0,
			}),
		);

		// Prefetch task runs
		const taskRuns = await context.queryClient.ensureQueryData(
			buildListTaskRunsQuery({
				task_runs: {
					operator: "and_",
					id: {
						any_: taskRunIds,
					},
				},
				sort: "ID_DESC",
				offset: 0,
			}),
		);

		const artifactsWithMetadata: ArtifactWithFlowRunAndTaskRun[] =
			artifacts.map((artifact: Artifact) => {
				const flowRun = flowRuns.find(
					(flowRun) => flowRun.id === artifact.flow_run_id,
				);
				const taskRun = taskRuns.find(
					(taskRun) => taskRun.id === artifact.task_run_id,
				);

				return {
					...artifact,
					flow_run: flowRun,
					task_run: taskRun,
				};
			});

		return { artifacts: artifactsWithMetadata };
	},
	wrapInSuspense: true,
});

function RouteComponent() {
	const { key } = Route.useParams();

	const { artifacts } = Route.useLoaderData();

	return (
		<div>
			<ArtifactsKeyPage
				artifactKey={key} // can't use "key" as it is a reserved word
				artifacts={artifacts}
			/>
		</div>
	);
}
