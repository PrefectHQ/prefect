import { useSuspenseQuery } from "@tanstack/react-query";
import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";
import { buildGetArtifactQuery } from "@/api/artifacts";
import { useGetArtifactFlowTaskRuns } from "@/api/artifacts/use-get-artifacts-flow-task-runs/use-get-artifacts-flow-task-runs";
import { categorizeError } from "@/api/error-utils";
import { ArtifactDetailPage } from "@/components/artifacts/artifact/artifact-detail-page";
import { RouteErrorState } from "@/components/ui/route-error-state";

/**
 * Schema for validating URL search parameters for the Artifact Detail page
 * @property {"Artifact" | "Details" | "Raw"} tab used to designate which tab view to display
 */
const searchParams = z.object({
	tab: z.enum(["Artifact", "Details", "Raw"]).default("Artifact"),
});

export type ArtifactDetailTabOptions = z.infer<typeof searchParams>["tab"];

export const Route = createFileRoute("/artifacts/artifact/$id")({
	validateSearch: zodValidator(searchParams),
	component: function RouteComponent() {
		const { id } = Route.useParams();

		const { data: artifact } = useSuspenseQuery(buildGetArtifactQuery(id));

		const artifactWithMetadata = useGetArtifactFlowTaskRuns(id);

		return <ArtifactDetailPage artifact={artifactWithMetadata ?? artifact} />;
	},
	loader: async ({ context, params }) => {
		const { id } = params;

		const artifact = await context.queryClient.ensureQueryData(
			buildGetArtifactQuery(id),
		);

		return { artifact };
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
});
