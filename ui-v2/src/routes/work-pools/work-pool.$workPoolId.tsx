import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/work-pools/work-pool/$workPoolId")({
	component: RouteComponent,
});

function RouteComponent() {
	return "🚧🚧 Pardon our dust! 🚧🚧";
}
