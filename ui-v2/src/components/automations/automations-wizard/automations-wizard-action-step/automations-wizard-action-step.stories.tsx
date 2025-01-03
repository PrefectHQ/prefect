import type { Meta, StoryObj } from "@storybook/react";

import { fn } from "@storybook/test";
import { AutomationsWizardActionStep } from "./automations-wizard-action-step";

const meta = {
	title: "Components/Automations/Wizard/AutomationWizardActionStep",
	component: AutomationsWizardActionStep,
	args: { onSubmit: fn() },
} satisfies Meta;

export default meta;

export const story: StoryObj = { name: "AutomationWizardActionStep" };
