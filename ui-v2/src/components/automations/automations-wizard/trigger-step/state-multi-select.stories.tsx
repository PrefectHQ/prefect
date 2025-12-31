import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import {
	STATE_NAMES_WITHOUT_SCHEDULED,
	type StateName,
} from "@/api/flow-runs/constants";
import { StateMultiSelect } from "./state-multi-select";

const meta = {
	title: "Components/Automations/Wizard/StateMultiSelect",
	component: StateMultiSelect,
} satisfies Meta<typeof StateMultiSelect>;

export default meta;

type Story = StoryObj<typeof meta>;

function StateMultiSelectStory({
	initialStates = [],
	emptyMessage = "Any state",
}: {
	initialStates?: StateName[];
	emptyMessage?: string;
}) {
	const [selectedStates, setSelectedStates] =
		useState<StateName[]>(initialStates);

	return (
		<div className="w-96">
			<StateMultiSelect
				selectedStates={selectedStates}
				onStateChange={setSelectedStates}
				emptyMessage={emptyMessage}
			/>
			<p className="mt-4 text-sm text-muted-foreground">
				Selected:{" "}
				{selectedStates.length === 0 ? "None" : selectedStates.join(", ")}
			</p>
		</div>
	);
}

export const Default: Story = {
	render: () => <StateMultiSelectStory />,
};

export const WithSelectedStates: Story = {
	render: () => (
		<StateMultiSelectStory initialStates={["Completed", "Failed", "Running"]} />
	),
};

export const AllExceptScheduled: Story = {
	render: () => (
		<StateMultiSelectStory initialStates={[...STATE_NAMES_WITHOUT_SCHEDULED]} />
	),
};

export const WithScheduledStates: Story = {
	render: () => (
		<StateMultiSelectStory
			initialStates={["Scheduled", "Late", "AwaitingRetry", "Resuming"]}
		/>
	),
};

export const WithRunningStates: Story = {
	render: () => (
		<StateMultiSelectStory initialStates={["Running", "Retrying"]} />
	),
};

export const WithCompletedStates: Story = {
	render: () => (
		<StateMultiSelectStory initialStates={["Completed", "Cached"]} />
	),
};

export const WithFailedStates: Story = {
	render: () => (
		<StateMultiSelectStory initialStates={["Failed", "TimedOut", "Crashed"]} />
	),
};

export const CustomEmptyMessage: Story = {
	render: () => <StateMultiSelectStory emptyMessage="Select states..." />,
};
