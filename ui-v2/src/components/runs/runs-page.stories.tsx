import { randNumber } from "@ngneat/falso";
import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { useState } from "react";
import { createFakeFlowRunWithDeploymentAndFlow } from "@/mocks/create-fake-flow-run";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import type {
	FlowRunState,
	PaginationState,
	SortFilters,
} from "../flow-runs/flow-runs-list";
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
	initialTaskRunsCount = 3,
	initialPages = 1,
	initialFlowRunSearch = "",
	initialSelectedStates = new Set<FlowRunState>(),
}: {
	initialFlowRuns?: typeof MOCK_FLOW_RUNS;
	initialFlowRunsCount?: number;
	initialTaskRunsCount?: number;
	initialPages?: number;
	initialFlowRunSearch?: string;
	initialSelectedStates?: Set<FlowRunState>;
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

	return (
		<RunsPage
			tab={tab}
			onTabChange={(newTab) => setTab(newTab as "flow-runs" | "task-runs")}
			flowRunsCount={initialFlowRunsCount}
			taskRunsCount={initialTaskRunsCount}
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
