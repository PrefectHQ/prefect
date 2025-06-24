import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import { fn } from "storybook/test";
import {
	AutomationsTriggerTemplateSelect,
	type TemplateTriggers,
} from "./automations-trigger-template-select";

const meta = {
	title: "Components/Automations/Wizard/AutomationsTriggerTemplateSelect",
	component: AutomationsTriggerTemplateSelect,
	args: { onValueChange: fn() },
	render: function ComponentExmaple() {
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
