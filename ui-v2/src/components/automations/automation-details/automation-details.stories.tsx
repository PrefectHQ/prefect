import type { Meta, StoryObj } from "@storybook/react";

import { createFakeAutomation } from "@/mocks";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { AutomationDetails } from "./automation-details";

const meta: Meta<typeof AutomationDetails> = {
	title: "Components/Automations/AutomationDetails",
	decorators: [routerDecorator, reactQueryDecorator],
	component: AutomationDetails,
	args: { data: createFakeAutomation() },
};
export default meta;

export const Page: StoryObj = {
	args: { displayType: "page" },
};

export const Item: StoryObj = {
	args: { displayType: "item" },
};
