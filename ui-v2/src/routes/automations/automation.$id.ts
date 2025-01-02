import { createFileRoute } from "@tanstack/react-router";

import { buildGetAutomationQuery } from "@/hooks/automations";

export const Route = createFileRoute("/automations/automation/$id")({
	component: RouteComponent,
	loader: ({ context, params }) =>
		context.queryClient.ensureQueryData(buildGetAutomationQuery(params.id)),
	wrapInSuspense: true,
});

function RouteComponent() {
	return "🚧🚧 Pardon our dust! 🚧🚧";
}
