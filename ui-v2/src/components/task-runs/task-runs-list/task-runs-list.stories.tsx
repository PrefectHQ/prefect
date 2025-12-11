import type { Meta, StoryObj } from "@storybook/react";
import { useMemo, useState } from "react";
import { fn } from "storybook/test";
import { createFakeState, createFakeTaskRun } from "@/mocks";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { TaskRunsList } from "./task-runs-list";

const MOCK_DATA = [
	createFakeTaskRun({
		id: "0",
		name: "extract-data",
		flow_run_id: null,
		state: createFakeState({ type: "SCHEDULED", name: "Late" }),
		state_type: "SCHEDULED",
		state_name: "Late",
		tags: ["etl", "production"],
	}),
	createFakeTaskRun({
		id: "1",
		name: "transform-data",
		flow_run_id: null,
		state: createFakeState({ type: "COMPLETED", name: "Cached" }),
		state_type: "COMPLETED",
		state_name: "Cached",
		tags: ["etl"],
	}),
	createFakeTaskRun({
		id: "2",
		name: "load-data",
		flow_run_id: null,
		state: createFakeState({ type: "SCHEDULED", name: "Scheduled" }),
		state_type: "SCHEDULED",
		state_name: "Scheduled",
		tags: ["etl", "database"],
	}),
	createFakeTaskRun({
		id: "3",
		name: "validate-output",
		flow_run_id: null,
		state: createFakeState({ type: "COMPLETED", name: "Completed" }),
		state_type: "COMPLETED",
		state_name: "Completed",
		tags: ["validation"],
	}),
	createFakeTaskRun({
		id: "4",
		name: "send-notification",
		flow_run_id: null,
		state: createFakeState({ type: "FAILED", name: "Failed" }),
		state_type: "FAILED",
		state_name: "Failed",
		tags: ["notification"],
	}),
];

const meta = {
	title: "Components/TaskRuns/TaskRunsList",
	component: TaskRunsList,
	decorators: [routerDecorator, reactQueryDecorator, toastDecorator],
} satisfies Meta<typeof TaskRunsList>;

export default meta;
type Story = StoryObj<typeof TaskRunsList>;

export const Default: Story = {
	args: {
		taskRuns: MOCK_DATA,
	},
};

export const Loading: Story = {
	args: {
		taskRuns: undefined,
	},
};

export const Empty: Story = {
	args: {
		taskRuns: [],
	},
};

export const EmptyWithClearFilters: Story = {
	args: {
		taskRuns: [],
		onClearFilters: fn(),
	},
};

export const Selectable: Story = {
	render: () => <SelectableTaskRunsListStory />,
};

const SelectableTaskRunsListStory = () => {
	const [selectedRows, setSelectedRows] = useState<Set<string>>(new Set());

	const addRow = (id: string) =>
		setSelectedRows((curr) => new Set([...Array.from(curr), id]));

	const removeRow = (id: string) =>
		setSelectedRows(
			(curr) => new Set([...Array.from(curr).filter((i) => i !== id)]),
		);

	const handleSelectRow = (id: string, checked: boolean) => {
		if (checked) {
			addRow(id);
		} else {
			removeRow(id);
		}
	};

	const handleResetFilters = () => {
		setSelectedRows(new Set());
	};

	return (
		<div className="flex flex-col gap-2">
			<div className="text-sm text-muted-foreground">
				Selected: {selectedRows.size} of {MOCK_DATA.length}
			</div>
			<TaskRunsList
				taskRuns={MOCK_DATA}
				selectedRows={selectedRows}
				onSelect={handleSelectRow}
				onClearFilters={handleResetFilters}
			/>
		</div>
	);
};

export const WithSearch: Story = {
	render: () => <SearchableTaskRunsListStory />,
};

const SearchableTaskRunsListStory = () => {
	const [search, setSearch] = useState("");

	const filteredTaskRuns = useMemo(() => {
		return MOCK_DATA.filter((taskRun) =>
			taskRun.name?.toLowerCase().includes(search.toLowerCase()),
		);
	}, [search]);

	const handleClearFilters = () => {
		setSearch("");
	};

	return (
		<div className="flex flex-col gap-2">
			<input
				type="text"
				placeholder="Search task runs..."
				value={search}
				onChange={(e) => setSearch(e.target.value)}
				className="border rounded px-2 py-1"
			/>
			<TaskRunsList
				taskRuns={filteredTaskRuns}
				onClearFilters={handleClearFilters}
			/>
		</div>
	);
};

export const SingleItem: Story = {
	args: {
		taskRuns: [MOCK_DATA[0]],
	},
};

export const MixedStates: Story = {
	args: {
		taskRuns: [
			createFakeTaskRun({
				id: "running-1",
				name: "running-task",
				flow_run_id: null,
				state: createFakeState({ type: "RUNNING", name: "Running" }),
				state_type: "RUNNING",
				state_name: "Running",
			}),
			createFakeTaskRun({
				id: "pending-1",
				name: "pending-task",
				flow_run_id: null,
				state: createFakeState({ type: "PENDING", name: "Pending" }),
				state_type: "PENDING",
				state_name: "Pending",
			}),
			createFakeTaskRun({
				id: "crashed-1",
				name: "crashed-task",
				flow_run_id: null,
				state: createFakeState({ type: "CRASHED", name: "Crashed" }),
				state_type: "CRASHED",
				state_name: "Crashed",
			}),
			createFakeTaskRun({
				id: "cancelled-1",
				name: "cancelled-task",
				flow_run_id: null,
				state: createFakeState({ type: "CANCELLED", name: "Cancelled" }),
				state_type: "CANCELLED",
				state_name: "Cancelled",
			}),
			createFakeTaskRun({
				id: "paused-1",
				name: "paused-task",
				flow_run_id: null,
				state: createFakeState({ type: "PAUSED", name: "Paused" }),
				state_type: "PAUSED",
				state_name: "Paused",
			}),
		],
	},
};
