import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/deployments")({
	component: RouteComponent,
});

function RouteComponent() {
	return "🚧🚧 Pardon our dust! 🚧🚧";
}
