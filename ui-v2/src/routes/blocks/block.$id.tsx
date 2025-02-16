import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/blocks/block/$id")({
	component: RouteComponent,
});

function RouteComponent() {
	return "🚧🚧 Pardon our duafafst! 🚧🚧";
}
