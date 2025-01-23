import { createFileRoute } from "@tanstack/react-router";

import { buildGetAutomationQuery } from "@/api/automations";
import { AutomationDetailsPage } from "@/components/automations/automation-details-page";

export const Route = createFileRoute("/automations/automation/$id")({
	component: RouteComponent,
	loader: ({ context, params }) =>
		context.queryClient.ensureQueryData(buildGetAutomationQuery(params.id)),
	wrapInSuspense: true,
});

function RouteComponent() {
	const { id } = Route.useParams();
	return <AutomationDetailsPage id={id} />;
}
