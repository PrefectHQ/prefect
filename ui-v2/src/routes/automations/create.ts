import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/automations/create")({
	component: RouteComponent,
});

function RouteComponent() {
	return "🚧🚧 Pardon our dust! 🚧🚧";
}
