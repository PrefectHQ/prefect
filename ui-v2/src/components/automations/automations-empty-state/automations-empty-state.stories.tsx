import type { Meta, StoryObj } from "@storybook/react";
import { routerDecorator } from "@/storybook/utils";

import { AutomationsEmptyState } from "./automations-empty-state";

const meta = {
	title: "Components/Automations/AutomationsEmptyState",
	component: AutomationsEmptyState,
	decorators: [routerDecorator],
} satisfies Meta<typeof AutomationsEmptyState>;

export default meta;

export const Story: StoryObj = {
	name: "AutomationsEmptyState",
};
