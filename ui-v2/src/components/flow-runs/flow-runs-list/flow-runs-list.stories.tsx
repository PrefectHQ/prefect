import { randNumber } from "@ngneat/falso";
import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { useMemo, useState } from "react";
import { fn } from "storybook/test";
import { createFakeFlowRunWithDeploymentAndFlow } from "@/mocks/create-fake-flow-run";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { FlowRunsFilters } from "./flow-runs-filters";
import type { FlowRunState } from "./flow-runs-filters/state-filters.constants";
import { FlowRunsList } from "./flow-runs-list";
import {
	FlowRunsPagination,
	type PaginationState,
} from "./flow-runs-pagination";
import { FlowRunsRowCount } from "./flow-runs-row-count";

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
	"0": randNumber({ min: 0, max: 5 }),
	"1": randNumber({ min: 0, max: 5 }),
	"2": randNumber({ min: 0, max: 5 }),
	"3": randNumber({ min: 0, max: 5 }),
	"4": randNumber({ min: 0, max: 5 }),
};

const meta = {
	title: "Components/FlowRuns/FlowRunsList",
	render: () => <FlowRunsListStory />,
	decorators: [routerDecorator, reactQueryDecorator, toastDecorator],
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () => {
					return HttpResponse.json(MOCK_FLOW_RUNS_TASK_COUNT);
				}),
			],
		},
	},
} satisfies Meta<typeof FlowRunsList>;

export default meta;

export const story: StoryObj = { name: "FlowRunsList" };

const FlowRunsListStory = () => {
	const [selectedRows, setSelectedRows] = useState<Set<string>>(new Set());
	const [pagination, setPagination] = useState<PaginationState>({
		limit: 5,
		page: 1,
	});
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
		setFilters(new Set());
	};

	return (
		<div className="flex flex-col gap-2">
			<div className="flex items-center justify-between">
				<FlowRunsRowCount
					count={MOCK_DATA.length}
					results={flowRuns}
					selectedRows={selectedRows}
					setSelectedRows={setSelectedRows}
				/>
				<FlowRunsFilters
					search={{ value: search, onChange: setSearch }}
					stateFilter={{
						value: filters,
						onSelect: setFilters,
					}}
					sort={{
						value: "NAME_ASC",
						onSelect: fn(),
					}}
				/>
			</div>

			<FlowRunsList
				flowRuns={flowRuns}
				selectedRows={selectedRows}
				onSelect={handleSelectRow}
				onClearFilters={handleResetFilters}
			/>

			<FlowRunsPagination
				count={MOCK_DATA.length}
				pagination={pagination}
				onChangePagination={setPagination}
				pages={20}
			/>
		</div>
	);
};
