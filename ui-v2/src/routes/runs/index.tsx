import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/runs/")({
	component: RouteComponent,
});

function RouteComponent() {
	return "🚧🚧 Pardon our dust! 🚧🚧";
}
