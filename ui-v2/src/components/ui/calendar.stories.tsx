import type { Meta, StoryObj } from "@storybook/react";

import { useState } from "react";
import type { DateRange } from "react-day-picker";
import { Calendar } from "./calendar";

const meta = {
	title: "UI/Calendar",
	component: Calendar,
} satisfies Meta<typeof Calendar>;

export default meta;

type Story = StoryObj<typeof Calendar>;

export const Single: Story = {
	render: function SingleCalendarComponent() {
		const [selected, setSelected] = useState<Date>();
		return (
			<Calendar
				mode="single"
				selected={selected}
				onSelect={setSelected}
				required
			/>
		);
	},
};

export const Range: Story = {
	render: function RangeCalendarComponent() {
		const [selected, setSelected] = useState<DateRange>();
		return (
			<Calendar
				selected={selected}
				onSelect={setSelected}
				mode="range"
				required
			/>
		);
	},
};

export const multiple: Story = {
	render: function MultipleCalendarComponent() {
		const [selected, setSelected] = useState<Date[]>();
		return (
			<Calendar
				mode="multiple"
				selected={selected}
				onSelect={setSelected}
				required
			/>
		);
	},
};
