import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/automations/automation/$id/edit")({
	component: RouteComponent,
});

function RouteComponent() {
	return "🚧🚧 Pardon our dust! 🚧🚧";
}
