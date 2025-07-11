import { createFileRoute } from "@tanstack/react-router";
import { buildDeploymentDetailsQuery } from "@/api/deployments";
import { DeploymentDuplicatePage } from "@/components/deployments/deployment-duplicate-page";

export const Route = createFileRoute("/deployments/deployment_/$id/duplicate")({
	component: RouteComponent,
	loader: ({ params, context: { queryClient } }) =>
		queryClient.ensureQueryData(buildDeploymentDetailsQuery(params.id)),
	wrapInSuspense: true,
});

function RouteComponent() {
	const { id } = Route.useParams();
	return <DeploymentDuplicatePage id={id} />;
}
