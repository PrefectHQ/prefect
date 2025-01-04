import { ActionType } from "@/components/automations/automations-wizard/types";
import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import { AutomationsActionSelect } from "./automations-action-select";

const meta = {
	title: "Components/Automations/Wizard/AutomationsActionSelect",
	component: AutomationsActionSelect,
	render: function ComponentExmaple() {
		const [type, setType] = useState<ActionType>();
		const [actionFields, setActionFields] = useState<Record<string, unknown>>(
			{},
		);
		return (
			<AutomationsActionSelect
				actionFields={actionFields}
				onActionFieldsChange={setActionFields}
				actionType={type}
				onChangeActionType={setType}
			/>
		);
	},
} satisfies Meta<typeof AutomationsActionSelect>;

export default meta;

export const story: StoryObj = { name: "AutomationsActionSelect" };
