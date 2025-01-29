import { routerDecorator, toastDecorator } from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";

import { createFakeAutomation } from "@/mocks";
import { fn } from "@storybook/test";
import { AutomationsActionsMenu } from "./automations-actions-menu";

const MOCK_DATA = createFakeAutomation();

const meta = {
	title: "Components/Automations/AutomationsActionsMenu",
	component: AutomationsActionsMenu,
	decorators: [routerDecorator, toastDecorator],
	args: {
		id: MOCK_DATA.id,
		onDelete: fn(),
	},
} satisfies Meta<typeof AutomationsActionsMenu>;

export default meta;

export const Story: StoryObj = {
	name: "AutomationsActionsMenu",
};
