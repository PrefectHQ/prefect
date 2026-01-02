import type { Meta, StoryObj } from "@storybook/react";

import { TriggerDetailsCustom } from "./trigger-details-custom";

const meta = {
	title: "Components/Automations/TriggerDetails/TriggerDetailsCustom",
	component: TriggerDetailsCustom,
} satisfies Meta<typeof TriggerDetailsCustom>;

export default meta;

export const Story: StoryObj = {
	name: "TriggerDetailsCustom",
};
