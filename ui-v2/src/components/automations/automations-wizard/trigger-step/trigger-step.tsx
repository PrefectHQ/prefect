import { useState } from "react";
import { useFormContext } from "react-hook-form";
import type { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import {
	AutomationsTriggerTemplateSelect,
	type TriggerTemplate,
} from "@/components/automations/automations-wizard/automations-trigger-template-select";
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
			{template && (
				<div className="text-muted-foreground">
					Template selected: {template}
				</div>
			)}
		</div>
	);
};
