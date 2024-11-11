import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/work-pools")({
	component: RouteComponent,
});

function RouteComponent() {
	return "🚧🚧 Pardon our dust! 🚧🚧";
}
