import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "@storybook/test";

import { DetailsStep } from "./details-step";

const meta = {
	title: "Components/Automations/Wizard/DetailsStep",
	component: DetailsStep,
	args: { onPrevious: fn(), onSave: fn() },
} satisfies Meta;

export default meta;

export const story: StoryObj = { name: "DetailsStep" };
