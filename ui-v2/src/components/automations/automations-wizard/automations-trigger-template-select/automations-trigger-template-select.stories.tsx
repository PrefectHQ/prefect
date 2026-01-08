import { zodResolver } from "@hookform/resolvers/zod";
import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { fn } from "storybook/test";
import { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import { Form } from "@/components/ui/form";
import {
	AutomationsTriggerTemplateSelect,
	type TemplateTriggers,
	TriggerTemplateSelectField,
} from "./automations-trigger-template-select";

const meta = {
	title: "Components/Automations/Wizard/AutomationsTriggerTemplateSelect",
	component: AutomationsTriggerTemplateSelect,
	args: { onValueChange: fn() },
	render: function ComponentExample() {
		const [template, setTemplate] = useState<TemplateTriggers>();
		return (
			<AutomationsTriggerTemplateSelect
				onValueChange={setTemplate}
				value={template}
			/>
		);
	},
} satisfies Meta<typeof AutomationsTriggerTemplateSelect>;

export default meta;

export const story: StoryObj = { name: "AutomationsTriggerTemplateSelect" };

function TriggerTemplateSelectFieldStory() {
	const form = useForm({
		resolver: zodResolver(AutomationWizardSchema),
		defaultValues: {
			actions: [{ type: undefined }],
			trigger: {
				type: "event" as const,
				posture: "Reactive" as const,
				threshold: 1,
				within: 0,
			},
		},
	});

	return (
		<Form {...form}>
			<form>
				<TriggerTemplateSelectField onTemplateChange={fn()} />
			</form>
		</Form>
	);
}

export const FormIntegration: StoryObj = {
	name: "TriggerTemplateSelectField (Form Integration)",
	render: TriggerTemplateSelectFieldStory,
};
