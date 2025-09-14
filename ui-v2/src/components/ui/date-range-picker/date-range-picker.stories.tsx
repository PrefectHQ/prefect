import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "storybook/test";

import { DateRangePicker } from "./date-range-picker";

const meta = {
	title: "UI/DateRangePicker",
	component: DateRangePicker,
	args: {
		onValueChange: fn(),
		value: undefined,
	},
} satisfies Meta<typeof DateRangePicker>;

export default meta;

export const Story: StoryObj = {
	name: "DateRangePicker",
};

export const WithInitialValue: StoryObj = {
	name: "WithInitialValue",
	args: {
		value: {
			from: new Date(2025, 2, 5).toISOString(),
			to: new Date(2025, 2, 13).toISOString(),
		},
		defaultMonth: new Date(2025, 2),
	},
};
