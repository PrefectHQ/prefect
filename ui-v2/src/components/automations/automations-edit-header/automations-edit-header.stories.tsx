import type { Meta, StoryObj } from "@storybook/react";
import { createFakeAutomation } from "@/mocks/create-fake-automation";
import { routerDecorator } from "@/storybook/utils";
import { AutomationsEditHeader } from "./automations-edit-header";

const meta = {
	title: "Components/Automations/AutomationsEditHeader",
	component: AutomationsEditHeader,
	decorators: [routerDecorator],
	parameters: {
		layout: "padded",
	},
} satisfies Meta<typeof AutomationsEditHeader>;

export default meta;
type Story = StoryObj<typeof AutomationsEditHeader>;

export const Default: Story = {
	args: {
		automation: createFakeAutomation({ name: "my-automation" }),
	},
};

export const LongName: Story = {
	args: {
		automation: createFakeAutomation({
			name: "very-long-automation-name-that-might-wrap-or-truncate-in-the-breadcrumb",
		}),
	},
};
