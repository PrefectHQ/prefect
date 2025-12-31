import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import { DurationInput } from "./index";

const meta = {
	title: "Components/UI/DurationInput",
	component: DurationInput,
} satisfies Meta<typeof DurationInput>;

export default meta;

type Story = StoryObj<typeof meta>;

function DurationInputStory({
	initialValue = 0,
	min,
	disabled,
}: {
	initialValue?: number;
	min?: number;
	disabled?: boolean;
}) {
	const [value, setValue] = useState(initialValue);

	return (
		<div className="w-80 space-y-4">
			<DurationInput
				value={value}
				onChange={setValue}
				min={min}
				disabled={disabled}
			/>
			<p className="text-sm text-muted-foreground">
				Current value: {value} seconds
			</p>
		</div>
	);
}

export const Default: Story = {
	render: () => <DurationInputStory />,
};

export const WithInitialSeconds: Story = {
	render: () => <DurationInputStory initialValue={30} />,
};

export const WithInitialMinutes: Story = {
	render: () => <DurationInputStory initialValue={120} />,
};

export const WithInitialHours: Story = {
	render: () => <DurationInputStory initialValue={7200} />,
};

export const WithInitialDays: Story = {
	render: () => <DurationInputStory initialValue={172800} />,
};

export const WithMinimumSeconds: Story = {
	render: () => <DurationInputStory initialValue={60} min={1} />,
};

export const WithMinimumMinutes: Story = {
	render: () => <DurationInputStory initialValue={3600} min={60} />,
};

export const Disabled: Story = {
	render: () => <DurationInputStory initialValue={300} disabled />,
};
