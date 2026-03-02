import { useSuspenseQuery } from "@tanstack/react-query";
import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { type ArtifactsFilter, buildListArtifactsQuery } from "@/api/artifacts";
import { useFilterArtifactsFlowTaskRuns } from "@/api/artifacts/use-get-artifacts-flow-task-runs/use-get-artifacts-flow-task-runs";
import { categorizeError } from "@/api/error-utils";
import { ArtifactsKeyPage } from "@/components/artifacts/key/artifacts-key-page";
import { PrefectLoading } from "@/components/ui/loading";
import { RouteErrorState } from "@/components/ui/route-error-state";

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
	errorComponent: function ArtifactDetailErrorComponent({
		error,
		reset,
	}: ErrorComponentProps) {
		const serverError = categorizeError(error, "Failed to load artifact");
		if (
			serverError.type !== "server-error" &&
			serverError.type !== "client-error"
		) {
			throw error;
		}
		return (
			<div className="flex flex-col gap-4">
				<div>
					<h1 className="text-2xl font-semibold">Artifact</h1>
				</div>
				<RouteErrorState error={serverError} onRetry={reset} />
			</div>
		);
	},
	wrapInSuspense: true,
	pendingComponent: PrefectLoading,
});
