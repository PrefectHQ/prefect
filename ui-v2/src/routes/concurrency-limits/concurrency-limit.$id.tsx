import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute(
	"/concurrency-limits/concurrency-limit/$id",
)({
	component: RouteComponent,
});

function RouteComponent() {
	const { id } = Route.useParams();
	return `🚧🚧 Pardon our dust! 🚧🚧: ${id}`;
}
