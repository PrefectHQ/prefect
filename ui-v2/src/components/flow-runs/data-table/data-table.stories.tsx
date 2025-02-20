import type { Meta, StoryObj } from "@storybook/react";

import { createFakeFlowRunWithDeploymentAndFlow } from "@/mocks/create-fake-flow-run";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { faker } from "@faker-js/faker";
import { fn } from "@storybook/test";
import { buildApiUrl } from "@tests/utils/handlers";
import { http, HttpResponse } from "msw";
import { useMemo, useState } from "react";
import { FlowRunsDataTable } from "./data-table";
import { FlowRunsFilters } from "./data-table-filters";
import type { FlowRunState } from "./flow-runs-filters/state-filters.constants";
import { RowSelectionProvider } from "./row-selection-provider";

const MOCK_DATA = [
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
	"0": faker.number.int({ min: 0, max: 5 }),
	"1": faker.number.int({ min: 0, max: 5 }),
	"2": faker.number.int({ min: 0, max: 5 }),
	"3": faker.number.int({ min: 0, max: 5 }),
	"4": faker.number.int({ min: 0, max: 5 }),
};

const meta = {
	title: "Components/FlowRuns/DataTable/FlowRunsDataTable",
	decorators: [routerDecorator, reactQueryDecorator, toastDecorator],
	args: { flowRuns: MOCK_DATA, flowRunsCount: MOCK_DATA.length },
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () => {
					return HttpResponse.json(MOCK_FLOW_RUNS_TASK_COUNT);
				}),
			],
		},
	},
} satisfies Meta<typeof FlowRunsDataTable>;

export default meta;
type Story = StoryObj<typeof meta>;

export const DataTableWithFilters: Story = {
	render: () => <DataTableWithFiltersStory />,
};

export const DataTableOnly: Story = {
	render: () => <DataTableOnlyStory />,
};

const DataTableWithFiltersStory = () => {
	const [pageIndex, setPageIndex] = useState(0);
	const [pageSize, setPageSize] = useState(10);

	const [search, setSearch] = useState("");
	const [filters, setFilters] = useState<Set<FlowRunState>>(new Set());

	const flowRuns = useMemo(() => {
		return MOCK_DATA.filter((flowRun) =>
			flowRun.name?.toLocaleLowerCase().includes(search.toLowerCase()),
		).filter((flowRun) =>
			filters.size === 0
				? flowRun
				: filters.has(flowRun.state?.name as FlowRunState),
		);
	}, [filters, search]);

	return (
		<div className="flex flex-col">
			<RowSelectionProvider>
				<FlowRunsFilters
					stateFilter={{
						value: filters,
						onSelect: setFilters,
					}}
					search={{
						value: search,
						onChange: setSearch,
					}}
					sort={{
						value: "NAME_ASC",
						onSelect: fn(),
					}}
					flowRunsCount={flowRuns.length}
				/>
				<FlowRunsDataTable
					flowRuns={flowRuns}
					flowRunsCount={flowRuns.length}
					pagination={{ pageIndex, pageSize }}
					pageCount={Math.ceil(flowRuns.length / pageSize)}
					onPaginationChange={(pagination) => {
						setPageIndex(pagination.pageIndex);
						setPageSize(pagination.pageSize);
					}}
				/>
			</RowSelectionProvider>
		</div>
	);
};

const DataTableOnlyStory = () => {
	const [pageIndex, setPageIndex] = useState(0);
	const [pageSize, setPageSize] = useState(10);

	const flowRuns = MOCK_DATA;

	return (
		<FlowRunsDataTable
			flowRuns={flowRuns}
			flowRunsCount={flowRuns.length}
			pagination={{ pageIndex, pageSize }}
			pageCount={Math.ceil(flowRuns.length / pageSize)}
			onPaginationChange={(pagination) => {
				setPageIndex(pagination.pageIndex);
				setPageSize(pagination.pageSize);
			}}
		/>
	);
};
