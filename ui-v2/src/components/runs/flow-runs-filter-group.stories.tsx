import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { useState } from "react";
import type { DateRangeSelectValue } from "@/components/ui/date-range-select";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { FlowRunsFilterGroup } from "./flow-runs-filter-group";
import type { FlowRunsFilters } from "./flow-runs-page";

const MOCK_FLOWS = [
	{
		id: "flow-1",
		name: "ETL Pipeline",
		tags: [],
		created: new Date().toISOString(),
		updated: new Date().toISOString(),
	},
	{
		id: "flow-2",
		name: "Data Processing",
		tags: [],
		created: new Date().toISOString(),
		updated: new Date().toISOString(),
	},
	{
		id: "flow-3",
		name: "Report Generator",
		tags: [],
		created: new Date().toISOString(),
		updated: new Date().toISOString(),
	},
];

const MOCK_DEPLOYMENTS = [
	{
		id: "deployment-1",
		name: "Production ETL",
		flow_id: "flow-1",
		created: new Date().toISOString(),
		updated: new Date().toISOString(),
	},
	{
		id: "deployment-2",
		name: "Staging ETL",
		flow_id: "flow-1",
		created: new Date().toISOString(),
		updated: new Date().toISOString(),
	},
	{
		id: "deployment-3",
		name: "Data Processing Daily",
		flow_id: "flow-2",
		created: new Date().toISOString(),
		updated: new Date().toISOString(),
	},
];

const MOCK_WORK_POOLS = [
	{
		id: "pool-1",
		name: "default-agent-pool",
		type: "process",
		created: new Date().toISOString(),
		updated: new Date().toISOString(),
	},
	{
		id: "pool-2",
		name: "kubernetes-pool",
		type: "kubernetes",
		created: new Date().toISOString(),
		updated: new Date().toISOString(),
	},
];

const DEFAULT_DATE_RANGE: DateRangeSelectValue = {
	type: "span",
	seconds: -604800, // 7 days in seconds
};

const meta = {
	title: "Components/Runs/FlowRunsFilterGroup",
	render: () => <FlowRunsFilterGroupStory />,
	decorators: [routerDecorator, reactQueryDecorator],
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json(MOCK_FLOWS);
				}),
				http.post(buildApiUrl("/deployments/filter"), () => {
					return HttpResponse.json(MOCK_DEPLOYMENTS);
				}),
				http.post(buildApiUrl("/work_pools/filter"), () => {
					return HttpResponse.json(MOCK_WORK_POOLS);
				}),
			],
		},
	},
} satisfies Meta<typeof FlowRunsFilterGroup>;

export default meta;

export const story: StoryObj = { name: "FlowRunsFilterGroup" };

const FlowRunsFilterGroupStory = () => {
	const [search, setSearch] = useState("");
	const [state, setState] = useState<string[]>([]);
	const [flow, setFlow] = useState<string[]>([]);
	const [deployment, setDeployment] = useState<string[]>([]);
	const [workPool, setWorkPool] = useState<string[]>([]);
	const [tag, setTag] = useState<string[]>([]);
	const [range, setRange] = useState<DateRangeSelectValue>(DEFAULT_DATE_RANGE);

	const hasActiveFilters =
		!!search ||
		state.length > 0 ||
		flow.length > 0 ||
		deployment.length > 0 ||
		workPool.length > 0 ||
		tag.length > 0 ||
		JSON.stringify(range) !== JSON.stringify(DEFAULT_DATE_RANGE);

	const handleClearFilters = () => {
		setSearch("");
		setState([]);
		setFlow([]);
		setDeployment([]);
		setWorkPool([]);
		setTag([]);
		setRange(DEFAULT_DATE_RANGE);
	};

	const filters: FlowRunsFilters = {
		search,
		deferredSearch: search,
		state,
		flow,
		deployment,
		workPool,
		tag,
		range,
		hasActiveFilters,
		onSearchChange: setSearch,
		onStateChange: setState,
		onFlowChange: setFlow,
		onDeploymentChange: setDeployment,
		onWorkPoolChange: setWorkPool,
		onTagChange: setTag,
		onDateRangeChange: setRange,
		onClearFilters: handleClearFilters,
	};

	return (
		<div className="p-4">
			<FlowRunsFilterGroup
				flows={MOCK_FLOWS}
				deployments={MOCK_DEPLOYMENTS}
				workPools={MOCK_WORK_POOLS}
				filters={filters}
			/>
		</div>
	);
};

export const WithActiveFilters: StoryObj = {
	name: "With Active Filters",
	render: () => <FlowRunsFilterGroupWithActiveFiltersStory />,
};

const FlowRunsFilterGroupWithActiveFiltersStory = () => {
	const [search, setSearch] = useState("my-flow-run");
	const [state, setState] = useState<string[]>(["Completed", "Failed"]);
	const [flow, setFlow] = useState<string[]>(["flow-1"]);
	const [deployment, setDeployment] = useState<string[]>([]);
	const [workPool, setWorkPool] = useState<string[]>([]);
	const [tag, setTag] = useState<string[]>(["production", "critical"]);
	const [range, setRange] = useState<DateRangeSelectValue>(DEFAULT_DATE_RANGE);

	const hasActiveFilters =
		!!search ||
		state.length > 0 ||
		flow.length > 0 ||
		deployment.length > 0 ||
		workPool.length > 0 ||
		tag.length > 0 ||
		JSON.stringify(range) !== JSON.stringify(DEFAULT_DATE_RANGE);

	const handleClearFilters = () => {
		setSearch("");
		setState([]);
		setFlow([]);
		setDeployment([]);
		setWorkPool([]);
		setTag([]);
		setRange(DEFAULT_DATE_RANGE);
	};

	const filters: FlowRunsFilters = {
		search,
		deferredSearch: search,
		state,
		flow,
		deployment,
		workPool,
		tag,
		range,
		hasActiveFilters,
		onSearchChange: setSearch,
		onStateChange: setState,
		onFlowChange: setFlow,
		onDeploymentChange: setDeployment,
		onWorkPoolChange: setWorkPool,
		onTagChange: setTag,
		onDateRangeChange: setRange,
		onClearFilters: handleClearFilters,
	};

	return (
		<div className="p-4">
			<FlowRunsFilterGroup
				flows={MOCK_FLOWS}
				deployments={MOCK_DEPLOYMENTS}
				workPools={MOCK_WORK_POOLS}
				filters={filters}
			/>
		</div>
	);
};
