import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { toast } from "sonner";
import { z } from "zod";
import { useCreateAutomation } from "@/api/automations";
import type { components } from "@/api/prefect";
import { AutomationsCreateHeader } from "@/components/automations/automations-create-header";
import {
	AutomationWizard,
	type AutomationWizardSchemaType,
} from "@/components/automations/automations-wizard";

type AutomationCreate = components["schemas"]["AutomationCreate"];

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
	const { createAutomation, isPending } = useCreateAutomation();
	const navigate = useNavigate();

	const handleSubmit = (values: AutomationWizardSchemaType) => {
		const automationData: AutomationCreate = {
			name: values.name,
			description: values.description ?? "",
			enabled: true,
			trigger: values.trigger,
			actions: values.actions,
		};

		createAutomation(automationData, {
			onSuccess: () => {
				toast.success("Automation created successfully");
				void navigate({ to: "/automations" });
			},
			onError: (error) => {
				toast.error(`Failed to create automation: ${error.message}`);
			},
		});
	};

	return (
		<div className="flex flex-col gap-4">
			<AutomationsCreateHeader />
			<AutomationWizard onSubmit={handleSubmit} isSubmitting={isPending} />
		</div>
	);
}
