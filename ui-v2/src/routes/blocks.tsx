import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/blocks")({
	component: RouteComponent,
});

function RouteComponent() {
	return "🚧🚧 Pardon our dust! 🚧🚧";
}
