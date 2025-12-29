import { useState } from "react";
import { useFormContext } from "react-hook-form";
import type { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import {
	AutomationsTriggerTemplateSelect,
	type TriggerTemplate,
} from "@/components/automations/automations-wizard/automations-trigger-template-select";
import { CustomTriggerFields } from "./custom-trigger-fields";
import { DeploymentStatusTriggerFields } from "./deployment-status-trigger-fields";
import { FlowRunStateTriggerFields } from "./flow-run-state-trigger-fields";
import { getDefaultTriggerForTemplate } from "./trigger-step-utils";
import { WorkPoolStatusTriggerFields } from "./work-pool-status-trigger-fields";
import { WorkQueueStatusTriggerFields } from "./work-queue-status-trigger-fields";

export const TriggerStep = () => {
	const form = useFormContext<AutomationWizardSchema>();
	const [template, setTemplate] = useState<TriggerTemplate>();

	const handleTemplateChange = (value: TriggerTemplate) => {
		setTemplate(value);
		form.setValue("trigger", getDefaultTriggerForTemplate(value));
	};

	return (
		<div className="space-y-6">
			<AutomationsTriggerTemplateSelect
				value={template}
				onValueChange={handleTemplateChange}
			/>
			{template && <TriggerTemplateFields template={template} />}
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
