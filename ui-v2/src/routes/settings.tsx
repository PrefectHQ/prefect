import { buildGetSettingsQuery, buildGetVersionQuery } from "@/api/admin";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/settings")({
	component: RouteComponent,
	loader: ({ context }) =>
		Promise.all([
			context.queryClient.ensureQueryData(buildGetSettingsQuery()),
			context.queryClient.ensureQueryData(buildGetVersionQuery()),
		]),
	wrapInSuspense: true,
});

function RouteComponent() {
	return "🚧🚧 Pardon our dust! 🚧🚧";
}
