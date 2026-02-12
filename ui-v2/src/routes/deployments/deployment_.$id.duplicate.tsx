import { createFileRoute } from "@tanstack/react-router";
import { buildDeploymentDetailsQuery } from "@/api/deployments";
import { DeploymentDuplicatePage } from "@/components/deployments/deployment-duplicate-page";
import { PrefectLoading } from "@/components/ui/loading";

export const Route = createFileRoute("/deployments/deployment_/$id/duplicate")({
	component: RouteComponent,
	loader: ({ params, context: { queryClient } }) =>
		queryClient.ensureQueryData(buildDeploymentDetailsQuery(params.id)),
	wrapInSuspense: true,
	pendingComponent: PrefectLoading,
});

export function RouteComponent() {
	const { id } = Route.useParams();
	return <DeploymentDuplicatePage id={id} />;
}
