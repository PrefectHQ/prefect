import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/runs/flow-run/$id")({
	component: RouteComponent,
});

function RouteComponent() {
	return "🚧🚧 Pardon our dust! 🚧🚧";
}
