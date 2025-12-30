import { useFormContext } from "react-hook-form";
import type { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import {
	type TriggerTemplate,
	TriggerTemplateSelectField,
} from "@/components/automations/automations-wizard/automations-trigger-template-select";
import { CustomTriggerFields } from "./custom-trigger-fields";
import { DeploymentStatusTriggerFields } from "./deployment-status-trigger-fields";
import { FlowRunStateTriggerFields } from "./flow-run-state-trigger-fields";
import { getDefaultTriggerForTemplate } from "./trigger-step-utils";
import { WorkPoolStatusTriggerFields } from "./work-pool-status-trigger-fields";
import { WorkQueueStatusTriggerFields } from "./work-queue-status-trigger-fields";

export const TriggerStep = () => {
	const form = useFormContext<AutomationWizardSchema>();
	const triggerTemplate = form.watch("triggerTemplate");

	const handleTemplateChange = (value: TriggerTemplate) => {
		form.setValue("trigger", getDefaultTriggerForTemplate(value));
	};

	return (
		<div className="space-y-6">
			<TriggerTemplateSelectField onTemplateChange={handleTemplateChange} />
			{triggerTemplate && <TriggerTemplateFields template={triggerTemplate} />}
		</div>
	);
};

type TriggerTemplateFieldsProps = {
	template: TriggerTemplate;
};

const TriggerTemplateFields = ({ template }: TriggerTemplateFieldsProps) => {
	switch (template) {
		case "flow-run-state":
			return <FlowRunStateTriggerFields />;
		case "deployment-status":
			return <DeploymentStatusTriggerFields />;
		case "work-pool-status":
			return <WorkPoolStatusTriggerFields />;
		case "work-queue-status":
			return <WorkQueueStatusTriggerFields />;
		case "custom":
			return <CustomTriggerFields />;
		default:
			return null;
	}
};
