import { useFormContext } from "react-hook-form";
import type { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import { FormControl, FormField, FormItem } from "@/components/ui/form";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

const TEMPLATE_TRIGGERS = {
	"deployment-status": "Deployment status",
	"flow-run-state": "Flow run state",
	"work-pool-status": "Work pool status",
	"work-queue-status": "Work queue status",
	custom: "Custom",
} as const;

export type TemplateTriggers = keyof typeof TEMPLATE_TRIGGERS;

// Type alias for consistency with ticket specification
export type TriggerTemplate = TemplateTriggers;

type AutomationsTriggerTemplateSelectProps = {
	onValueChange: (value: TemplateTriggers) => void;
	value?: TemplateTriggers;
};

export const AutomationsTriggerTemplateSelect = ({
	onValueChange,
	value,
}: AutomationsTriggerTemplateSelectProps) => {
	return (
		<div className="space-y-2">
			<Label htmlFor="automations-trigger-template-select">
				Trigger Template
			</Label>
			<Select value={value} onValueChange={onValueChange}>
				<SelectTrigger
					id="automations-trigger-template-select"
					className="w-full"
				>
					<SelectValue placeholder="Select template" />
				</SelectTrigger>
				<SelectContent>
					<SelectGroup>
						{Object.keys(TEMPLATE_TRIGGERS).map((key) => (
							<SelectItem key={key} value={key}>
								{TEMPLATE_TRIGGERS[key as TemplateTriggers]}
							</SelectItem>
						))}
					</SelectGroup>
				</SelectContent>
			</Select>
		</div>
	);
};

type TriggerTemplateSelectFieldProps = {
	onTemplateChange?: (template: TriggerTemplate) => void;
};

export const TriggerTemplateSelectField = ({
	onTemplateChange,
}: TriggerTemplateSelectFieldProps) => {
	const form = useFormContext<AutomationWizardSchema>();

	return (
		<FormField
			control={form.control}
			name="triggerTemplate"
			render={({ field }) => (
				<FormItem>
					<FormControl>
						<AutomationsTriggerTemplateSelect
							value={field.value}
							onValueChange={(value) => {
								field.onChange(value);
								onTemplateChange?.(value);
							}}
						/>
					</FormControl>
				</FormItem>
			)}
		/>
	);
};
