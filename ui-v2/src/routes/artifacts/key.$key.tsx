import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { type ArtifactsFilter, buildListArtifactsQuery } from "@/api/artifacts";
import { useFilterArtifactsFlowTaskRuns } from "@/api/artifacts/use-get-artifacts-flow-task-runs/use-get-artifacts-flow-task-runs";
import { ArtifactsKeyPage } from "@/components/artifacts/key/artifacts-key-page";
import { Skeleton } from "@/components/ui/skeleton";

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
	component: function RouteComponent() {
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
	},
	loader: async ({ context, params }) => {
		const { key } = params;

		const artifacts = await context.queryClient.ensureQueryData(
			buildListArtifactsQuery(buildFilterBody(key)),
		);

		return { artifacts };
	},
	wrapInSuspense: true,
	pendingComponent: function ArtifactKeyPageSkeleton() {
		return (
			<div className="flex flex-col gap-4">
				<div className="flex items-center gap-2">
					<Skeleton className="h-4 w-20" />
					<Skeleton className="h-4 w-4" />
					<Skeleton className="h-6 w-40" />
				</div>
				<div className="rounded-lg border p-6 flex flex-col gap-3">
					<Skeleton className="h-5 w-32" />
					<Skeleton className="h-4 w-full" />
					<Skeleton className="h-4 w-3/4" />
					<Skeleton className="h-4 w-1/2" />
				</div>
			</div>
		);
	},
});
