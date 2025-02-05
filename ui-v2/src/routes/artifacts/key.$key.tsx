import { ArtifactsFilter, buildListArtifactsQuery } from "@/api/artifacts";
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
		return { artifacts };
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
