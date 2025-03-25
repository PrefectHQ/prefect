import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/blocks/catalog")({
	component: RouteComponent,
});

function RouteComponent() {
	return "🚧🚧 Pardon our dust! 🚧🚧";
}
