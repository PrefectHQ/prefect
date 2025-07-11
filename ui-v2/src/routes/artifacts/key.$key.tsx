import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { type ArtifactsFilter, buildListArtifactsQuery } from "@/api/artifacts";
import { useFilterArtifactsFlowTaskRuns } from "@/api/artifacts/use-get-artifacts-flow-task-runs/use-get-artifacts-flow-task-runs";
import { ArtifactsKeyPage } from "@/components/artifacts/key/artifacts-key-page";

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
		const { key } = params;

		const artifacts = await context.queryClient.ensureQueryData(
			buildListArtifactsQuery(buildFilterBody(key)),
		);

		return { artifacts };
	},
	wrapInSuspense: true,
});

function RouteComponent() {
	const { key } = Route.useParams();

	const { data: artifacts } = useSuspenseQuery(
		buildListArtifactsQuery(buildFilterBody(key)),
	);

	const artifactWithMetadata = useFilterArtifactsFlowTaskRuns(
		buildFilterBody(key),
	);
	return (
		<div>
			<ArtifactsKeyPage
				artifactKey={key} // can't use "key" as it is a reserved word
				artifacts={artifactWithMetadata ?? artifacts}
			/>
		</div>
	);
}
