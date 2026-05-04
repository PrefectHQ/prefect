import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { UiVersionSwitchDialog } from "./ui-version-switch-dialog";

const meta: Meta<typeof UiVersionSwitchDialog> = {
	title: "Components/UI Version Switch/Dialog",
	component: UiVersionSwitchDialog,
	args: {
		open: true,
		onOpenChange: fn(),
		onSkipFeedback: fn(),
		onSubmitFeedback: fn(),
	},
	parameters: {
		layout: "centered",
	},
};

export default meta;
type Story = StoryObj<typeof UiVersionSwitchDialog>;

export const Default: Story = {};
