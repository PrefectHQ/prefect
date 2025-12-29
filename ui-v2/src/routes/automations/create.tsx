import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";
import { AutomationsCreateHeader } from "@/components/automations/automations-create-header";
import { AutomationWizard } from "@/components/automations/automations-wizard";

// Keep existing search params schema for future pre-population support
const searchParams = z.object({
	actions: z.record(z.unknown()).optional(),
});

export const Route = createFileRoute("/automations/create")({
	component: RouteComponent,
	validateSearch: zodValidator(searchParams),
	wrapInSuspense: true,
});

function RouteComponent() {
	return (
		<div className="flex flex-col gap-4">
			<AutomationsCreateHeader />
			<AutomationWizard />
		</div>
	);
}
