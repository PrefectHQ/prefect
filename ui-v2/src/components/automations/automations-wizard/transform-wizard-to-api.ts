import type { components } from "@/api/prefect";
import type { AutomationWizardSchema } from "./automation-schema";

type AutomationCreate = components["schemas"]["AutomationCreate"];

export const transformWizardToApiPayload = (
	values: AutomationWizardSchema,
): AutomationCreate => {
	return {
		name: values.name,
		description: values.description ?? "",
		enabled: true,
		trigger: values.trigger,
		actions: values.actions,
	};
};
