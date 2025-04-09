import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/blocks/block_/$id/edit")({
	component: RouteComponent,
});

function RouteComponent() {
	return "🚧🚧 Pardon our dust! 🚧🚧";
}
