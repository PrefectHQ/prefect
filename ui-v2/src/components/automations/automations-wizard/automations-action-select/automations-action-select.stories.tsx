import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "@storybook/test";
import { useState } from "react";
import {
	type AutomationActions,
	AutomationsActionSelect,
} from "./automations-action-select";

const meta = {
	title: "Components/Automations/Wizard/AutomationsActionSelect",
	component: AutomationsActionSelect,
	args: { onValueChange: fn() },
	render: function ComponentExmaple() {
		const [action, setAction] = useState<AutomationActions>();
		return <AutomationsActionSelect onValueChange={setAction} value={action} />;
	},
} satisfies Meta<typeof AutomationsActionSelect>;

export default meta;

export const story: StoryObj = { name: "AutomationsActionSelect" };
