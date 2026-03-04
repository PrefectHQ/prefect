import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { buildDeploymentDetailsQuery } from "@/api/deployments";
import { categorizeError } from "@/api/error-utils";
import { DeploymentEditPage } from "@/components/deployments/deployment-edit-page";
import { PrefectLoading } from "@/components/ui/loading";
import { RouteErrorState } from "@/components/ui/route-error-state";

export const Route = createFileRoute("/deployments/deployment_/$id/edit")({
	component: function RouteComponent() {
		const { id } = Route.useParams();
		return <DeploymentEditPage id={id} />;
	},
	loader: ({ params, context: { queryClient } }) =>
		queryClient.ensureQueryData(buildDeploymentDetailsQuery(params.id)),
	wrapInSuspense: true,
	pendingComponent: PrefectLoading,
	errorComponent: function DeploymentEditErrorComponent({
		error,
		reset,
	}: ErrorComponentProps) {
		const serverError = categorizeError(error, "Failed to load deployment");
		if (
			serverError.type !== "server-error" &&
			serverError.type !== "client-error"
		) {
			throw error;
		}
		return (
			<div className="flex flex-col gap-4">
				<div>
					<h1 className="text-2xl font-semibold">Edit Deployment</h1>
				</div>
				<RouteErrorState error={serverError} onRetry={reset} />
			</div>
		);
	},
});
