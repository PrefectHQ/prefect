import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/deployments/deployment_/$id/duplicate")({
	component: RouteComponent,
});

function RouteComponent() {
	return "🚧🚧 Pardon our dust! 🚧🚧";
}
