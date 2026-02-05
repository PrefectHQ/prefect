import { createFileRoute } from "@tanstack/react-router";
import { buildDeploymentDetailsQuery } from "@/api/deployments";
import { DeploymentEditPage } from "@/components/deployments/deployment-edit-page";
import { PrefectLoading } from "@/components/ui/loading";

export const Route = createFileRoute("/deployments/deployment_/$id/edit")({
	component: RouteComponent,
	loader: ({ params, context: { queryClient } }) =>
		queryClient.ensureQueryData(buildDeploymentDetailsQuery(params.id)),
	wrapInSuspense: true,
	pendingComponent: PrefectLoading,
});

function RouteComponent() {
	const { id } = Route.useParams();

	return <DeploymentEditPage id={id} />;
}
