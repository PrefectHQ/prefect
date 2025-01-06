import type { Meta, StoryObj } from "@storybook/react";

import { fn } from "@storybook/test";
import { ActionStep } from "./action-step";

const meta = {
	title: "Components/Automations/Wizard/ActionStep",
	component: ActionStep,
	args: { onSubmit: fn() },
} satisfies Meta;

export default meta;

export const story: StoryObj = { name: "ActionStep" };
