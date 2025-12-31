import type { Meta, StoryObj } from "@storybook/react";
import { type ComponentProps, useState } from "react";
import { fn } from "storybook/test";
import { DurationInput } from "./index";

export default {
	title: "Components/UI/DurationInput",
	component: DurationInput,
	args: {
		value: 0,
		onChange: fn(),
	},
	render: function Render(args: ComponentProps<typeof DurationInput>) {
		const [value, setValue] = useState(args.value);

		return (
			<div className="w-80 space-y-4">
				<DurationInput
					{...args}
					value={value}
					onChange={(seconds) => {
						setValue(seconds);
						args.onChange(seconds);
					}}
				/>
				<p className="text-sm text-muted-foreground">
					Current value: {value} seconds
				</p>
			</div>
		);
	},
} satisfies Meta<typeof DurationInput>;

type Story = StoryObj<typeof DurationInput>;

export const Default: Story = {};

export const WithInitialSeconds: Story = {
	args: { value: 30 },
};

export const WithInitialMinutes: Story = {
	args: { value: 120 },
};

export const WithInitialHours: Story = {
	args: { value: 7200 },
};

export const WithInitialDays: Story = {
	args: { value: 172800 },
};

export const WithMinimumSeconds: Story = {
	args: { value: 60, min: 1 },
};

export const WithMinimumMinutes: Story = {
	args: { value: 3600, min: 60 },
};

export const Disabled: Story = {
	args: { value: 300, disabled: true },
};
