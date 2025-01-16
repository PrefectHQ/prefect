import { createFileRoute } from "@tanstack/react-router";

import { buildGetAutomationQuery } from "@/api/automations";
import { AutomationPage } from "@/components/automations/automation-page";

export const Route = createFileRoute("/automations/automation/$id")({
	component: RouteComponent,
	loader: ({ context, params }) =>
		context.queryClient.ensureQueryData(buildGetAutomationQuery(params.id)),
	wrapInSuspense: true,
});

function RouteComponent() {
	const { id } = Route.useParams();
	return <AutomationPage id={id} />;
}
