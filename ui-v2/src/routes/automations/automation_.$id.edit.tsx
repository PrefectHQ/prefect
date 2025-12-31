import { createFileRoute } from "@tanstack/react-router";

import { buildGetAutomationQuery } from "@/api/automations";
import { AutomationEditPage } from "@/components/automations/automation-edit-page";

export const Route = createFileRoute("/automations/automation_/$id/edit")({
	component: RouteComponent,
	loader: ({ context, params }) =>
		context.queryClient.ensureQueryData(buildGetAutomationQuery(params.id)),
	wrapInSuspense: true,
});

function RouteComponent() {
	const { id } = Route.useParams();
	return <AutomationEditPage id={id} />;
}
