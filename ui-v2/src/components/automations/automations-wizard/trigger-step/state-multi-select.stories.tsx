import type { Meta, StoryObj } from "@storybook/react";
import { type ComponentProps, useState } from "react";
import { fn } from "storybook/test";
import {
	STATE_NAMES_WITHOUT_SCHEDULED,
	type StateName,
} from "@/api/flow-runs/constants";
import { StateMultiSelect } from "./state-multi-select";

export default {
	title: "Components/Automations/Wizard/StateMultiSelect",
	component: StateMultiSelect,
	args: {
		selectedStates: [],
		onStateChange: fn(),
		emptyMessage: "Any state",
	},
	render: function Render(args: ComponentProps<typeof StateMultiSelect>) {
		const [selectedStates, setSelectedStates] = useState<StateName[]>(
			args.selectedStates,
		);

		return (
			<div className="w-96">
				<StateMultiSelect
					{...args}
					selectedStates={selectedStates}
					onStateChange={(states) => {
						setSelectedStates(states);
						args.onStateChange(states);
					}}
				/>
				<p className="mt-4 text-sm text-muted-foreground">
					Selected:{" "}
					{selectedStates.length === 0 ? "None" : selectedStates.join(", ")}
				</p>
			</div>
		);
	},
} satisfies Meta<typeof StateMultiSelect>;

type Story = StoryObj<typeof StateMultiSelect>;

export const Default: Story = {};

export const WithSelectedStates: Story = {
	args: { selectedStates: ["Completed", "Failed", "Running"] },
};

export const AllExceptScheduled: Story = {
	args: { selectedStates: [...STATE_NAMES_WITHOUT_SCHEDULED] },
};

export const WithScheduledStates: Story = {
	args: {
		selectedStates: ["Scheduled", "Late", "AwaitingRetry", "Resuming"],
	},
};

export const WithRunningStates: Story = {
	args: { selectedStates: ["Running", "Retrying"] },
};

export const WithCompletedStates: Story = {
	args: { selectedStates: ["Completed", "Cached"] },
};

export const WithFailedStates: Story = {
	args: { selectedStates: ["Failed", "TimedOut", "Crashed"] },
};

export const CustomEmptyMessage: Story = {
	args: { emptyMessage: "Select states..." },
};
