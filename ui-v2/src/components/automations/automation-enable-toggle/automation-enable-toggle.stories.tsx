import { createFakeAutomation } from "@/mocks";
import { reactQueryDecorator, toastDecorator } from "@/storybook/utils";
import type { Meta, StoryObj } from "@storybook/react";
import { AutomationEnableToggle } from "./automation-enable-toggle";

const MOCK_DATA = createFakeAutomation();

const meta = {
	title: "Components/Automations/AutomationEnableToggle",
	component: AutomationEnableToggle,
	decorators: [reactQueryDecorator, toastDecorator],
	args: { data: MOCK_DATA },
} satisfies Meta<typeof AutomationEnableToggle>;

export default meta;

export const Story: StoryObj = {
	name: "AutomationEnableToggle",
};
