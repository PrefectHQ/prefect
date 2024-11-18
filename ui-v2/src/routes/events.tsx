import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/events")({
	component: RouteComponent,
});

function RouteComponent() {
	return "🚧🚧 Pardon our dust! 🚧🚧";
}
