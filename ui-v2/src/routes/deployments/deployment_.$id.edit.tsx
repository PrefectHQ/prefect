import { buildDeploymentDetailsQuery } from "@/api/deployments";
import { DeploymentForm } from "@/components/deployments/deployment-form";
import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/deployments/deployment_/$id/edit")({
	component: RouteComponent,
	loader: ({ params, context: { queryClient } }) =>
		queryClient.ensureQueryData(buildDeploymentDetailsQuery(params.id)),
	wrapInSuspense: true,
});

function RouteComponent() {
	const { id } = Route.useParams();
	const { data } = useSuspenseQuery(buildDeploymentDetailsQuery(id));

	return <DeploymentForm deployment={data} mode="edit" />;
}
