import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { buildGetArtifactQuery } from "@/api/artifacts";
import { useGetArtifactFlowTaskRuns } from "@/api/artifacts/use-get-artifacts-flow-task-runs/use-get-artifacts-flow-task-runs";
import { ArtifactDetailPage } from "@/components/artifacts/artifact/artifact-detail-page";

export const Route = createFileRoute("/artifacts/artifact/$id")({
	component: RouteComponent,
	loader: async ({ context, params }) => {
		const { id } = params;

		const artifact = await context.queryClient.ensureQueryData(
			buildGetArtifactQuery(id),
		);

		return { artifact };
	},
});

function RouteComponent() {
	const { id } = Route.useParams();

	const { data: artifact } = useSuspenseQuery(buildGetArtifactQuery(id));

	const artifactWithMetadata = useGetArtifactFlowTaskRuns(id);

	return <ArtifactDetailPage artifact={artifactWithMetadata ?? artifact} />;
}
