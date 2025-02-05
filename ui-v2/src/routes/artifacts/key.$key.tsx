import { ArtifactsFilter, buildListArtifactsQuery } from "@/api/artifacts";
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

		const artifactsList = await context.queryClient.ensureQueryData(
			buildListArtifactsQuery(buildFilterBody(key)),
		);
		return { artifactsList };
	},
	wrapInSuspense: true,
});

function RouteComponent() {
	const { key } = Route.useParams();

	const { artifactsList } = Route.useLoaderData();

	return (
		<div>
			<p>{key}</p>
			{artifactsList.map((artifact) => (
				<div key={artifact.id}>{artifact.updated}</div>
			))}
		</div>
	);
}
