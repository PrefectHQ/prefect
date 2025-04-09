import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/blocks/catalog_/$slug_/create")({
	component: RouteComponent,
});

function RouteComponent() {
	return "🚧🚧 Pardon our dust! 🚧🚧";
}
