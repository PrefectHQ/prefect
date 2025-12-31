import type { Meta, StoryObj } from "@storybook/react";
import { type ComponentProps, useState } from "react";
import { fn } from "storybook/test";
import { DurationInput } from "./duration-input";

export default {
	title: "Components/Automations/Wizard/DurationInput",
	component: DurationInput,
	args: {
		value: 60,
		onChange: fn(),
		min: 0,
		disabled: false,
	},
	render: function Render(args: ComponentProps<typeof DurationInput>) {
		const [value, setValue] = useState(args.value);

		return (
			<div className="w-64">
				<DurationInput
					{...args}
					value={value}
					onChange={(newValue) => {
						setValue(newValue);
						args.onChange(newValue);
					}}
				/>
				<p className="mt-4 text-sm text-muted-foreground">
					Value in seconds: {value}
				</p>
			</div>
		);
	},
} satisfies Meta<typeof DurationInput>;

type Story = StoryObj<typeof DurationInput>;

export const Default: Story = {};

export const InSeconds: Story = {
	args: { value: 30 },
};

export const InMinutes: Story = {
	args: { value: 120 },
};

export const InHours: Story = {
	args: { value: 7200 },
};

export const InDays: Story = {
	args: { value: 172800 },
};

export const WithMinimum: Story = {
	args: { value: 3600, min: 60 },
};

export const Disabled: Story = {
	args: { value: 60, disabled: true },
};

export const ZeroValue: Story = {
	args: { value: 0 },
};
