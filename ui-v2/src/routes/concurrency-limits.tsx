import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/concurrency-limits")({
	component: RouteComponent,
});

function RouteComponent() {
	return "🚧🚧 Pardon our dust! 🚧🚧";
}
