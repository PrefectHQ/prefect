import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { useMemo, useState } from "react";
import { createFakeTaskRun } from "@/mocks";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { TaskRunsList } from "./task-runs-list";
import { TaskRunsRowCount } from "./task-runs-row-count";

const MOCK_DATA = [
	createFakeTaskRun({
		id: "0",
		name: "task-run-0",
		state: {
			type: "SCHEDULED",
			name: "Scheduled",
			id: "0",
			timestamp: new Date().toISOString(),
		},
		tags: ["tag1"],
	}),
	createFakeTaskRun({
		id: "1",
		name: "task-run-1",
		state: {
			type: "COMPLETED",
			name: "Completed",
			id: "1",
			timestamp: new Date().toISOString(),
		},
		tags: ["tag1", "tag2"],
	}),
	createFakeTaskRun({
		id: "2",
		name: "task-run-2",
		state: {
			type: "RUNNING",
			name: "Running",
			id: "2",
			timestamp: new Date().toISOString(),
		},
		tags: [],
	}),
	createFakeTaskRun({
		id: "3",
		name: "task-run-3",
		state: {
			type: "FAILED",
			name: "Failed",
			id: "3",
			timestamp: new Date().toISOString(),
		},
		tags: ["tag3"],
	}),
	createFakeTaskRun({
		id: "4",
		name: "task-run-4",
		state: {
			type: "CANCELLED",
			name: "Cancelled",
			id: "4",
			timestamp: new Date().toISOString(),
		},
		tags: ["tag1", "tag2", "tag3"],
	}),
];

const meta = {
	title: "Components/TaskRuns/TaskRunsList",
	render: () => <TaskRunsListStory />,
	decorators: [routerDecorator, reactQueryDecorator, toastDecorator],
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/task_runs/count"), () => {
					return HttpResponse.json(MOCK_DATA.length);
				}),
				http.delete(buildApiUrl("/task_runs/:id"), () => {
					return HttpResponse.json(null, { status: 204 });
				}),
			],
		},
	},
} satisfies Meta<typeof TaskRunsList>;

export default meta;

export const story: StoryObj = { name: "TaskRunsList" };

const TaskRunsListStory = () => {
	const [selectedRows, setSelectedRows] = useState<Set<string>>(new Set());
	const [search, setSearch] = useState("");

	const taskRuns = useMemo(() => {
		return MOCK_DATA.filter((taskRun) =>
			taskRun.name?.toLocaleLowerCase().includes(search.toLowerCase()),
		);
	}, [search]);

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
		setSearch("");
	};

	return (
		<div className="flex flex-col gap-2">
			<div className="flex items-center justify-between">
				<TaskRunsRowCount
					count={MOCK_DATA.length}
					results={taskRuns}
					selectedRows={selectedRows}
					setSelectedRows={setSelectedRows}
				/>
				<input
					type="text"
					placeholder="Search..."
					value={search}
					onChange={(e) => setSearch(e.target.value)}
					className="border rounded px-2 py-1"
				/>
			</div>

			<TaskRunsList
				taskRuns={taskRuns}
				selectedRows={selectedRows}
				onSelect={handleSelectRow}
				onClearFilters={handleResetFilters}
			/>
		</div>
	);
};

export const EmptyState: StoryObj = {
	name: "Empty State",
	render: () => <TaskRunsList taskRuns={[]} onClearFilters={() => {}} />,
	decorators: [routerDecorator, reactQueryDecorator],
};

export const LoadingState: StoryObj = {
	name: "Loading State",
	render: () => <TaskRunsList taskRuns={undefined} />,
	decorators: [routerDecorator, reactQueryDecorator],
};

export const WithoutSelection: StoryObj = {
	name: "Without Selection",
	render: () => <TaskRunsList taskRuns={MOCK_DATA} />,
	decorators: [routerDecorator, reactQueryDecorator],
};
