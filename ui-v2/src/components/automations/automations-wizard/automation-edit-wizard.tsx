import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import type { AutomationWizardSchema } from "./automation-schema";
import { AutomationWizard } from "./automation-wizard";
import { useEditAutomation } from "./use-edit-automation";

type AutomationEditWizardProps = {
	automationId: string;
};

export const AutomationEditWizard = ({
	automationId,
}: AutomationEditWizardProps) => {
	const navigate = useNavigate();

	const { defaultValues, updateAutomation, isPending } = useEditAutomation({
		automationId,
		onSuccess: () => {
			toast.success("Automation updated successfully");
			void navigate({ to: "/automations" });
		},
		onError: (error) => {
			toast.error(`Failed to update automation: ${error.message}`, {
				duration: Number.POSITIVE_INFINITY,
			});
		},
	});

	const handleSubmit = (values: AutomationWizardSchema) => {
		updateAutomation(values);
	};

	return (
		<AutomationWizard
			defaultValues={defaultValues}
			onSubmit={handleSubmit}
			submitLabel="Save"
			isSubmitting={isPending}
		/>
	);
};
