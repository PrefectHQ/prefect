import { buildListAutomationsQuery } from "@/hooks/automations";
import { createFileRoute } from "@tanstack/react-router";

// nb: Currently there is no filtering or search params used on this page
export const Route = createFileRoute("/automations/")({
	component: RouteComponent,
	loader: ({ context }) =>
		context.queryClient.ensureQueryData(buildListAutomationsQuery()),
	wrapInSuspense: true,
});

function RouteComponent() {
	return "🚧🚧 Pardon our dust! 🚧🚧";
}
