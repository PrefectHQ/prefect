import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import { createFakeState, createFakeTaskRun } from "@/mocks";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { TaskRunsRowCount } from "./task-runs-row-count";

const MOCK_DATA = [
	createFakeTaskRun({
		id: "task-1",
		name: "extract-data",
		flow_run_id: null,
		state: createFakeState({ type: "COMPLETED", name: "Completed" }),
		state_type: "COMPLETED",
		state_name: "Completed",
	}),
	createFakeTaskRun({
		id: "task-2",
		name: "transform-data",
		flow_run_id: null,
		state: createFakeState({ type: "COMPLETED", name: "Completed" }),
		state_type: "COMPLETED",
		state_name: "Completed",
	}),
	createFakeTaskRun({
		id: "task-3",
		name: "load-data",
		flow_run_id: null,
		state: createFakeState({ type: "RUNNING", name: "Running" }),
		state_type: "RUNNING",
		state_name: "Running",
	}),
	createFakeTaskRun({
		id: "task-4",
		name: "validate-output",
		flow_run_id: null,
		state: createFakeState({ type: "SCHEDULED", name: "Scheduled" }),
		state_type: "SCHEDULED",
		state_name: "Scheduled",
	}),
	createFakeTaskRun({
		id: "task-5",
		name: "send-notification",
		flow_run_id: null,
		state: createFakeState({ type: "FAILED", name: "Failed" }),
		state_type: "FAILED",
		state_name: "Failed",
	}),
];

const meta = {
	title: "Components/TaskRuns/TaskRunsRowCount",
	component: TaskRunsRowCount,
	decorators: [routerDecorator, reactQueryDecorator, toastDecorator],
} satisfies Meta<typeof TaskRunsRowCount>;

export default meta;
type Story = StoryObj<typeof TaskRunsRowCount>;

export const CountOnly: Story = {
	args: {
		count: 5,
	},
};

export const CountOnlySingular: Story = {
	args: {
		count: 1,
	},
};

export const CountOnlyZero: Story = {
	args: {
		count: 0,
	},
};

export const SelectableNoSelection: Story = {
	render: () => <SelectableStory initialSelection={new Set()} />,
};

export const SelectableSomeSelected: Story = {
	render: () => (
		<SelectableStory initialSelection={new Set(["task-1", "task-2"])} />
	),
};

export const SelectableAllSelected: Story = {
	render: () => (
		<SelectableStory
			initialSelection={
				new Set(["task-1", "task-2", "task-3", "task-4", "task-5"])
			}
		/>
	),
};

type SelectableStoryProps = {
	initialSelection: Set<string>;
};

const SelectableStory = ({ initialSelection }: SelectableStoryProps) => {
	const [selectedRows, setSelectedRows] =
		useState<Set<string>>(initialSelection);

	return (
		<div className="flex flex-col gap-4">
			<TaskRunsRowCount
				count={MOCK_DATA.length}
				results={MOCK_DATA}
				selectedRows={selectedRows}
				setSelectedRows={setSelectedRows}
			/>
			<div className="text-sm text-muted-foreground">
				Debug: Selected IDs: {Array.from(selectedRows).join(", ") || "none"}
			</div>
		</div>
	);
};

export const Interactive: Story = {
	render: () => <InteractiveStory />,
};

const InteractiveStory = () => {
	const [selectedRows, setSelectedRows] = useState<Set<string>>(new Set());

	return (
		<div className="flex flex-col gap-4">
			<div className="text-sm font-medium">
				Try clicking the checkbox to toggle all, or the delete button when rows
				are selected.
			</div>
			<TaskRunsRowCount
				count={MOCK_DATA.length}
				results={MOCK_DATA}
				selectedRows={selectedRows}
				setSelectedRows={setSelectedRows}
			/>
			<div className="text-sm text-muted-foreground">
				Selected: {selectedRows.size} of {MOCK_DATA.length}
			</div>
		</div>
	);
};
