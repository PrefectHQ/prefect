import { createFileRoute } from "@tanstack/react-router";
import { buildListAutomationsQuery } from "@/api/automations";
import { AutomationsPage } from "@/components/automations/automations-page";

// nb: Currently there is no filtering or search params used on this page
export const Route = createFileRoute("/automations/")({
	component: AutomationsPage,
	loader: ({ context }) =>
		context.queryClient.ensureQueryData(buildListAutomationsQuery()),
	wrapInSuspense: true,
});
