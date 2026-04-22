import { useSuspenseQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { buildGetAutomationQuery } from "@/api/automations";
import { AutomationsEditHeader } from "./automations-edit-header";
import type { AutomationWizardSchema } from "./automations-wizard/automation-schema";
import { AutomationWizard } from "./automations-wizard/automation-wizard";
import { useEditAutomation } from "./automations-wizard/use-edit-automation";

type AutomationEditPageProps = {
	id: string;
};

export const AutomationEditPage = ({ id }: AutomationEditPageProps) => {
	const navigate = useNavigate();
	const { data: automation } = useSuspenseQuery(buildGetAutomationQuery(id));

	const { defaultValues, updateAutomation, isPending } = useEditAutomation({
		automationId: id,
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
		<div className="flex flex-col gap-4">
			<AutomationsEditHeader automation={automation} />
			<AutomationWizard
				defaultValues={defaultValues}
				isEditMode
				onSubmit={handleSubmit}
				submitLabel="Save"
				isSubmitting={isPending}
			/>
		</div>
	);
};
