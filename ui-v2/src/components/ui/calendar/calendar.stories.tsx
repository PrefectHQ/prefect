import type { Meta, StoryObj } from "@storybook/react";

import { Calendar } from ".";

const meta = {
	title: "UI/Calendar",
	component: Calendar,
	parameters: {
		layout: "centered",
	},
	args: {
		mode: "single",
		className: "rounded-md border shadow",
	},
} satisfies Meta<typeof Calendar>;

export default meta;

type Story = StoryObj<typeof meta>;

export const story: Story = { name: "Calendar" };
