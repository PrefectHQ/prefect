import { useState } from "react";
import { useFormContext } from "react-hook-form";
import type { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import {
	AutomationsTriggerTemplateSelect,
	type TriggerTemplate,
} from "@/components/automations/automations-wizard/automations-trigger-template-select";
import { FlowRunStateTriggerFields } from "./flow-run-state-trigger-fields";
import { getDefaultTriggerForTemplate } from "./trigger-step-utils";

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
			return (
				<div className="text-muted-foreground">
					Deployment status trigger fields coming soon
				</div>
			);
		case "work-pool-status":
			return (
				<div className="text-muted-foreground">
					Work pool status trigger fields coming soon
				</div>
			);
		case "work-queue-status":
			return (
				<div className="text-muted-foreground">
					Work queue status trigger fields coming soon
				</div>
			);
		case "custom":
			return (
				<div className="text-muted-foreground">
					Custom trigger fields coming soon
				</div>
			);
		default:
			return null;
	}
};
