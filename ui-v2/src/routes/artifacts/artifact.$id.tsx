import { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import { ArtifactDetailPage } from "@/components/artifacts/artifact/artifact-detail-page";
import { ensureUseArtifactsServiceGetArtifactsByIdData } from "@/openapi/queries/ensureQueryData";
import { useArtifactsServiceGetArtifactsByIdSuspense, useFlowRunsServiceGetFlowRunsByIdSuspense, useTaskRunsServiceGetTaskRunsByIdSuspense } from "@/openapi/queries/suspense";
import { createFileRoute } from "@tanstack/react-router";
import { useMemo } from "react";
import { z } from "zod";

export const Route = createFileRoute("/artifacts/artifact/$id")({
	component: RouteComponent,
	params: z.object({
		id: z.string(),
	}),
	loader: async ({ context, params }) => {

		await ensureUseArtifactsServiceGetArtifactsByIdData(context.queryClient, params);

	},
	wrapInSuspense: true,
});

function RouteComponent() {
	const params = Route.useParams();

	const { data: artifact } = useArtifactsServiceGetArtifactsByIdSuspense(params);

	const { data: flowRun } = useFlowRunsServiceGetFlowRunsByIdSuspense({ id: artifact.flow_run_id ?? "" });
	const { data: taskRun } = useTaskRunsServiceGetTaskRunsByIdSuspense({ id: artifact.task_run_id ?? "" });

	const artifactWithMetadata = useMemo(() => {
		return {
			...artifact,
			flow_run: flowRun,
			task_run: taskRun,
		}
	}, [artifact, flowRun, taskRun]);
	// const artifactWithMetadata = useGetArtifactFlowTaskRuns(id);

	return <ArtifactDetailPage artifact={(artifact as ArtifactWithFlowRunAndTaskRun) ?? artifactWithMetadata} />;
}

