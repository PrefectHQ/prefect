import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { createFakeAutomation } from "@/mocks";
import { reactQueryDecorator, toastDecorator } from "@/storybook/utils";
import { AutomationsDeleteDialog } from "./automations-delete-dialog";

const meta = {
	title: "Components/Automations/AutomationsDeleteDialog",
	component: AutomationsDeleteDialog,
	decorators: [reactQueryDecorator, toastDecorator],
	args: {
		automation: createFakeAutomation(),
		onOpenChange: fn(),
		onDelete: fn(),
	},
} satisfies Meta<typeof AutomationsDeleteDialog>;

export default meta;

export const story: StoryObj = { name: "AutomationsDeleteDialog" };
