import type { Meta, StoryObj } from "@storybook/react";

import { fn } from "@storybook/test";
import { DateTimePicker } from "./date-time-picker";

const meta = {
	title: "UI/DateTimePicker",
	component: DateTimePicker,
	args: { onValueChange: fn(), value: new Date().toISOString() },
} satisfies Meta<typeof DateTimePicker>;

export default meta;

export const Story: StoryObj = {
	name: "DateTimePicker",
};
