import { createFileRoute } from "@tanstack/react-router";

import { buildGetAutomationQuery } from "@/api/automations";
import { AutomationDetails } from "@/components/automations/automation-details";
import { useSuspenseQuery } from "@tanstack/react-query";

export const Route = createFileRoute("/automations/automation/$id")({
	component: RouteComponent,
	loader: ({ context, params }) =>
		context.queryClient.ensureQueryData(buildGetAutomationQuery(params.id)),
	wrapInSuspense: true,
});

function RouteComponent() {
	const { id } = Route.useParams();
	const { data } = useSuspenseQuery(buildGetAutomationQuery(id));
	return <AutomationDetails data={data} displayType="page" />;
}
