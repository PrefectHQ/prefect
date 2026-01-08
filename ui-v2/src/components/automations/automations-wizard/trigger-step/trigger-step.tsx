import { useCallback, useEffect, useState } from "react";
import { useFormContext } from "react-hook-form";
import { z } from "zod";
import {
	type AutomationWizardSchema,
	type Trigger,
	TriggerSchema,
} from "@/components/automations/automations-wizard/automation-schema";
import {
	type TriggerTemplate,
	TriggerTemplateSelectField,
} from "@/components/automations/automations-wizard/automations-trigger-template-select";
import { CustomTriggerFields } from "./custom-trigger-fields";
import { DeploymentStatusTriggerFields } from "./deployment-status-trigger-fields";
import { FlowRunStateTriggerFields } from "./flow-run-state-trigger-fields";
import { type FormMode, FormModeToggle } from "./form-mode-toggle";
import { TriggerJsonInput } from "./trigger-json-input";
import { getDefaultTriggerForTemplate } from "./trigger-step-utils";
import { WorkPoolStatusTriggerFields } from "./work-pool-status-trigger-fields";
import { WorkQueueStatusTriggerFields } from "./work-queue-status-trigger-fields";

export const TriggerStep = () => {
	const form = useFormContext<AutomationWizardSchema>();
	const triggerTemplate = form.watch("triggerTemplate");
	const trigger = form.watch("trigger");

	const [mode, setMode] = useState<FormMode>("Form");
	const [jsonString, setJsonString] = useState<string>("");
	const [jsonError, setJsonError] = useState<string | undefined>(undefined);

	// Serialize trigger to JSON string
	const serializeTrigger = useCallback(() => {
		return JSON.stringify(trigger, null, 2);
	}, [trigger]);

	// Update jsonString when trigger changes (while in Form mode)
	useEffect(() => {
		if (mode === "Form") {
			setJsonString(serializeTrigger());
		}
	}, [mode, serializeTrigger]);

	// Validate and parse JSON string
	const validateAndParseJson = useCallback(
		(json: string): { valid: boolean; trigger?: Trigger; error?: string } => {
			try {
				const parsed: unknown = JSON.parse(json);
				const validatedTrigger = TriggerSchema.parse(parsed);
				return { valid: true, trigger: validatedTrigger };
			} catch (e) {
				if (e instanceof SyntaxError) {
					return { valid: false, error: "Invalid JSON syntax" };
				}
				if (e instanceof z.ZodError) {
					return {
						valid: false,
						error: e.errors[0]?.message ?? "Invalid trigger configuration",
					};
				}
				return { valid: false, error: "Unknown error" };
			}
		},
		[],
	);

	// Handle mode change with validation
	const handleModeChange = useCallback(
		(newMode: FormMode) => {
			if (mode === newMode) {
				return;
			}

			if (newMode === "Form") {
				// Switching from JSON to Form - validate and sync JSON to form
				const result = validateAndParseJson(jsonString);
				if (!result.valid) {
					setJsonError(result.error);
					return; // Block switch if JSON is invalid
				}
				// Update form with parsed trigger
				if (result.trigger) {
					form.setValue("trigger", result.trigger);
				}
				setJsonError(undefined);
			} else {
				// Switching from Form to JSON - serialize current trigger
				setJsonString(serializeTrigger());
				setJsonError(undefined);
			}

			setMode(newMode);
		},
		[mode, jsonString, validateAndParseJson, form, serializeTrigger],
	);

	// Handle JSON input changes - immediately sync valid JSON to form
	const handleJsonChange = useCallback(
		(value: string) => {
			setJsonString(value);

			// Try to parse and validate the JSON
			const result = validateAndParseJson(value);
			if (result.valid && result.trigger) {
				// Valid JSON - sync to form immediately
				form.setValue("trigger", result.trigger);
				setJsonError(undefined);
			}
			// Don't set error on every keystroke - only on blur or mode switch
		},
		[validateAndParseJson, form],
	);

	const handleTemplateChange = (value: TriggerTemplate) => {
		const newTrigger = getDefaultTriggerForTemplate(value);
		form.setValue("trigger", newTrigger);
		// Reset JSON string when template changes
		setJsonString(JSON.stringify(newTrigger, null, 2));
		setJsonError(undefined);
	};

	return (
		<div className="space-y-6">
			<TriggerTemplateSelectField onTemplateChange={handleTemplateChange} />
			{triggerTemplate && (
				<FormModeToggle
					value={mode}
					onValueChange={handleModeChange}
					formContent={<TriggerTemplateFields template={triggerTemplate} />}
					jsonContent={
						<TriggerJsonInput
							value={jsonString}
							onChange={handleJsonChange}
							error={jsonError}
						/>
					}
				/>
			)}
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
