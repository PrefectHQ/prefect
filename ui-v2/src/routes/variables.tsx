import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/variables")({
	component: RouteComponent,
});

function RouteComponent() {
	return "🚧🚧 Pardon our dust! 🚧🚧";
}
