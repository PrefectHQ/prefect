import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";
import { UiVersionSwitchCard } from "./ui-version-switch-card";

const meta: Meta<typeof UiVersionSwitchCard> = {
	title: "Components/UI Version Switch/Card",
	component: UiVersionSwitchCard,
	args: {
		onSwitch: fn(),
	},
	parameters: {
		layout: "padded",
	},
};

export default meta;
type Story = StoryObj<typeof UiVersionSwitchCard>;

export const Default: Story = {};
