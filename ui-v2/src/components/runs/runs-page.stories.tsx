import { randNumber } from "@ngneat/falso";
import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { useState } from "react";
import type { TaskRunResponse } from "@/api/task-runs";
import {
	createFakeFlowRunWithDeploymentAndFlow,
	createFakeTaskRunResponse,
} from "@/mocks";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import type {
	DateRangeUrlState,
	FlowRunState,
	PaginationState,
	SortFilters,
} from "../flow-runs/flow-runs-list";
import type { TaskRunSortFilters } from "../task-runs/task-runs-list";
import { RunsPage } from "./runs-page";

const MOCK_FLOW_RUNS = [
	createFakeFlowRunWithDeploymentAndFlow({
		id: "0",
		state: { type: "SCHEDULED", name: "Late", id: "0" },
	}),
	createFakeFlowRunWithDeploymentAndFlow({
		id: "1",
		state: { type: "COMPLETED", name: "Cached", id: "0" },
	}),
	createFakeFlowRunWithDeploymentAndFlow({
		id: "2",
		state: { type: "SCHEDULED", name: "Scheduled", id: "0" },
	}),
	createFakeFlowRunWithDeploymentAndFlow({
		id: "3",
		state: { type: "COMPLETED", name: "Completed", id: "0" },
	}),
	createFakeFlowRunWithDeploymentAndFlow({
		id: "4",
		state: { type: "FAILED", name: "Failed", id: "0" },
	}),
];

const MOCK_FLOW_RUNS_TASK_COUNT = {
	"0": randNumber({ min: 0, max: 5 }),
	"1": randNumber({ min: 0, max: 5 }),
	"2": randNumber({ min: 0, max: 5 }),
	"3": randNumber({ min: 0, max: 5 }),
	"4": randNumber({ min: 0, max: 5 }),
};

const MOCK_TASK_RUNS = [
	createFakeTaskRunResponse({
		id: "task-0",
		name: "my_task-0",
		flow_run_id: "0",
		task_key: "my_task",
		state: { type: "COMPLETED", name: "Completed", id: "state-0" },
		tags: [],
	}),
	createFakeTaskRunResponse({
		id: "task-1",
		name: "my_task-1",
		flow_run_id: "1",
		task_key: "my_task",
		state: { type: "FAILED", name: "Failed", id: "state-1" },
		tags: ["important"],
	}),
	createFakeTaskRunResponse({
		id: "task-2",
		name: "another_task-0",
		flow_run_id: "2",
		task_key: "another_task",
		state: { type: "RUNNING", name: "Running", id: "state-2" },
		tags: [],
	}),
];

const meta = {
	title: "Components/Runs/RunsPage",
	component: RunsPage,
	decorators: [routerDecorator, reactQueryDecorator, toastDecorator],
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () => {
					return HttpResponse.json(MOCK_FLOW_RUNS_TASK_COUNT);
				}),
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json([
						{ id: "flow-1", name: "Test Flow", tags: [] },
					]);
				}),
			],
		},
	},
} satisfies Meta<typeof RunsPage>;

export default meta;

type Story = StoryObj<typeof RunsPage>;

const RunsPageWithState = ({
	initialFlowRuns = MOCK_FLOW_RUNS,
	initialFlowRunsCount = 5,
	initialTaskRuns = MOCK_TASK_RUNS,
	initialTaskRunsCount = 3,
	initialPages = 1,
	initialTaskRunsPages = 1,
	initialFlowRunSearch = "",
	initialTaskRunSearch = "",
	initialSelectedStates = new Set<FlowRunState>(),
	initialDateRange = {},
	initialSelectedFlows = new Set<string>(),
	initialSelectedDeployments = new Set<string>(),
	initialSelectedWorkPools = new Set<string>(),
}: {
	initialFlowRuns?: typeof MOCK_FLOW_RUNS;
	initialFlowRunsCount?: number;
	initialTaskRuns?: TaskRunResponse[];
	initialTaskRunsCount?: number;
	initialPages?: number;
	initialTaskRunsPages?: number;
	initialFlowRunSearch?: string;
	initialTaskRunSearch?: string;
	initialSelectedStates?: Set<FlowRunState>;
	initialDateRange?: DateRangeUrlState;
	initialSelectedFlows?: Set<string>;
	initialSelectedDeployments?: Set<string>;
	initialSelectedWorkPools?: Set<string>;
}) => {
	const [tab, setTab] = useState<"flow-runs" | "task-runs">("flow-runs");
	const [pagination, setPagination] = useState<PaginationState>({
		page: 1,
		limit: 10,
	});
	const [sort, setSort] = useState<SortFilters>("START_TIME_DESC");
	const [hideSubflows, setHideSubflows] = useState(false);
	const [flowRunSearch, setFlowRunSearch] = useState(initialFlowRunSearch);
	const [selectedStates, setSelectedStates] = useState<Set<FlowRunState>>(
		initialSelectedStates,
	);
	const [dateRange, setDateRange] =
		useState<DateRangeUrlState>(initialDateRange);
	const [selectedFlows, setSelectedFlows] =
		useState<Set<string>>(initialSelectedFlows);
	const [selectedDeployments, setSelectedDeployments] = useState<Set<string>>(
		initialSelectedDeployments,
	);
	const [selectedWorkPools, setSelectedWorkPools] = useState<Set<string>>(
		initialSelectedWorkPools,
	);
	const [selectedTags, setSelectedTags] = useState<Set<string>>(new Set());

	// Task runs state
	const [taskRunsPagination, setTaskRunsPagination] = useState<PaginationState>(
		{
			page: 1,
			limit: 10,
		},
	);
	const [taskRunsSort, setTaskRunsSort] = useState<TaskRunSortFilters>(
		"EXPECTED_START_TIME_DESC",
	);
	const [taskRunSearch, setTaskRunSearch] = useState(initialTaskRunSearch);

	// Mock saved filters state
	const mockCurrentFilter = null;
	const mockSavedFilters: { id: string; name: string; isDefault: boolean }[] =
		[];

	return (
		<RunsPage
			tab={tab}
			onTabChange={(newTab) => setTab(newTab as "flow-runs" | "task-runs")}
			flowRunsCount={initialFlowRunsCount}
			taskRunsCount={initialTaskRunsCount}
			hasAnyFlowRuns={initialFlowRunsCount > 0 || initialFlowRuns.length > 0}
			hasAnyTaskRuns={initialTaskRunsCount > 0 || initialTaskRuns.length > 0}
			flowRuns={initialFlowRuns}
			flowRunsPages={initialPages}
			pagination={pagination}
			onPaginationChange={setPagination}
			sort={sort}
			onSortChange={setSort}
			hideSubflows={hideSubflows}
			onHideSubflowsChange={setHideSubflows}
			flowRunSearch={flowRunSearch}
			onFlowRunSearchChange={setFlowRunSearch}
			selectedStates={selectedStates}
			onStateFilterChange={setSelectedStates}
			selectedFlows={selectedFlows}
			onFlowFilterChange={setSelectedFlows}
			selectedDeployments={selectedDeployments}
			onDeploymentFilterChange={setSelectedDeployments}
			selectedWorkPools={selectedWorkPools}
			onWorkPoolFilterChange={setSelectedWorkPools}
			selectedTags={selectedTags}
			onTagsFilterChange={setSelectedTags}
			dateRange={dateRange}
			onDateRangeChange={setDateRange}
			// Scatter plot props
			flowRunHistory={[]}
			scatterPlotDateRange={{}}
			// Task runs props
			taskRuns={initialTaskRuns}
			taskRunsPages={initialTaskRunsPages}
			taskRunsPagination={taskRunsPagination}
			onTaskRunsPaginationChange={setTaskRunsPagination}
			onTaskRunsPrefetchPage={() => {}}
			taskRunsSort={taskRunsSort}
			onTaskRunsSortChange={setTaskRunsSort}
			taskRunSearch={taskRunSearch}
			onTaskRunSearchChange={setTaskRunSearch}
			onClearTaskRunFilters={() => setTaskRunSearch("")}
			// Saved filters props
			currentFilter={mockCurrentFilter}
			savedFilters={mockSavedFilters}
			onSelectFilter={() => {}}
			onSaveFilter={() => {}}
			onDeleteFilter={() => {}}
			onSetDefault={() => {}}
			onRemoveDefault={() => {}}
			isSaveDialogOpen={false}
			onCloseSaveDialog={() => {}}
			onConfirmSave={() => {}}
		/>
	);
};

export const WithFlowRuns: Story = {
	name: "With Flow Runs",
	render: () => <RunsPageWithState />,
};

export const EmptyState: Story = {
	name: "Empty State",
	render: () => (
		<RunsPageWithState
			initialFlowRuns={[]}
			initialFlowRunsCount={0}
			initialTaskRuns={[]}
			initialTaskRunsCount={0}
		/>
	),
};

export const WithPagination: Story = {
	name: "With Pagination",
	render: () => (
		<RunsPageWithState
			initialFlowRunsCount={50}
			initialTaskRunsCount={25}
			initialPages={5}
		/>
	),
};

export const WithSearchValue: Story = {
	name: "With Search Value",
	render: () => <RunsPageWithState initialFlowRunSearch="test-flow" />,
};

export const WithStateFilter: Story = {
	name: "With State Filter",
	render: () => (
		<RunsPageWithState
			initialSelectedStates={new Set<FlowRunState>(["Completed", "Failed"])}
		/>
	),
};
