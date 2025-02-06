import { buildDeploymentDetailsQuery } from "@/api/deployments";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/deployments/deployment/$id")({
	component: RouteComponent,
	loader: ({ context, params }) =>
		context.queryClient.ensureQueryData(buildDeploymentDetailsQuery(params.id)),
	wrapInSuspense: true,
});

function RouteComponent() {
	return "🚧🚧 Pardon our dust! 🚧🚧";
}
