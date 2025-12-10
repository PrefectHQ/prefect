import { useQuery } from "@tanstack/react-query";
import type { FlowRun } from "@/api/flow-runs";
import { buildListFlowsQuery } from "@/api/flows";
import type { FlowRunCardData } from "@/components/flow-runs/flow-run-card";
import {
	DateRangeFilter,
	type DateRangeUrlState,
	type FlowRunState,
	FlowRunsList,
	FlowRunsPagination,
	FlowRunsRowCount,
	type PaginationState,
	type SortFilters,
	useFlowRunsSelectedRows,
} from "@/components/flow-runs/flow-runs-list";
import { SortFilter } from "@/components/flow-runs/flow-runs-list/flow-runs-filters/sort-filter";
import { StateFilter } from "@/components/flow-runs/flow-runs-list/flow-runs-filters/state-filter";
import { DocsLink } from "@/components/ui/docs-link";
import {
	EmptyState,
	EmptyStateActions,
	EmptyStateDescription,
	EmptyStateIcon,
	EmptyStateTitle,
} from "@/components/ui/empty-state";
import { SearchInput } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Typography } from "@/components/ui/typography";

type RunsPageProps = {
	tab: "flow-runs" | "task-runs";
	onTabChange: (tab: string) => void;
	flowRunsCount: number;
	taskRunsCount: number;
	flowRuns: FlowRun[];
	flowRunsPages: number;
	pagination: PaginationState;
	onPaginationChange: (pagination: PaginationState) => void;
	onPrefetchPage?: (page: number) => void;
	sort: SortFilters;
	onSortChange: (sort: SortFilters) => void;
	hideSubflows: boolean;
	onHideSubflowsChange: (hideSubflows: boolean) => void;
	flowRunSearch: string;
	onFlowRunSearchChange: (search: string) => void;
	selectedStates: Set<FlowRunState>;
	onStateFilterChange: (states: Set<FlowRunState>) => void;
	dateRange: DateRangeUrlState;
	onDateRangeChange: (dateRange: DateRangeUrlState) => void;
};

export const RunsPage = ({
	tab,
	onTabChange,
	flowRunsCount,
	taskRunsCount,
	flowRuns,
	flowRunsPages,
	pagination,
	onPaginationChange,
	onPrefetchPage,
	sort,
	onSortChange,
	hideSubflows,
	onHideSubflowsChange,
	flowRunSearch,
	onFlowRunSearchChange,
	selectedStates,
	onStateFilterChange,
	dateRange,
	onDateRangeChange,
}: RunsPageProps) => {
	const isEmpty = flowRunsCount === 0 && taskRunsCount === 0;

	const [selectedRows, setSelectedRows, { onSelectRow }] =
		useFlowRunsSelectedRows();

	const flowIds = [...new Set(flowRuns.map((flowRun) => flowRun.flow_id))];

	const { data: flows } = useQuery(
		buildListFlowsQuery(
			{
				flows: {
					operator: "and_",
					id: { any_: flowIds },
				},
				offset: 0,
				sort: "NAME_ASC",
			},
			{ enabled: flowIds.length > 0 },
		),
	);

	const flowRunsWithFlows: FlowRunCardData[] = flowRuns.map((flowRun) => ({
		...flowRun,
		flow: flows?.find((flow) => flow.id === flowRun.flow_id),
	}));

	if (isEmpty) {
		return (
			<div className="flex flex-col gap-4">
				<RunsHeader />
				<RunsEmptyState />
			</div>
		);
	}

	return (
		<div className="flex flex-col gap-4">
			<RunsHeader />
			<Tabs value={tab} onValueChange={onTabChange}>
				<TabsList>
					<TabsTrigger value="flow-runs">Flow Runs</TabsTrigger>
					<TabsTrigger value="task-runs">Task Runs</TabsTrigger>
				</TabsList>
				<TabsContent value="flow-runs">
					<div className="flex flex-col gap-4">
						<div className="flex flex-col gap-4">
							<div className="flex items-center gap-4">
								<div className="w-64">
									<StateFilter
										selectedFilters={selectedStates}
										onSelectFilter={onStateFilterChange}
									/>
								</div>
								<DateRangeFilter
									value={dateRange}
									onValueChange={onDateRangeChange}
								/>
							</div>
							<div className="flex items-center justify-between">
								<FlowRunsRowCount
									count={flowRunsCount}
									results={flowRunsWithFlows}
									selectedRows={selectedRows}
									setSelectedRows={setSelectedRows}
								/>
								<div className="flex items-center gap-4">
									<div className="flex items-center gap-2 whitespace-nowrap">
										<Switch
											id="hide-subflows"
											checked={hideSubflows}
											onCheckedChange={onHideSubflowsChange}
										/>
										<Label htmlFor="hide-subflows">Hide subflows</Label>
									</div>
									<SearchInput
										value={flowRunSearch}
										onChange={(e) => onFlowRunSearchChange(e.target.value)}
										placeholder="Search by flow run name"
										aria-label="Search by flow run name"
										className="w-64"
										debounceMs={1200}
									/>
									<SortFilter value={sort} onSelect={onSortChange} />
								</div>
							</div>
						</div>
						<FlowRunsPagination
							count={flowRunsCount}
							pages={flowRunsPages}
							pagination={pagination}
							onChangePagination={onPaginationChange}
							onPrefetchPage={onPrefetchPage}
						/>
						<FlowRunsList
							flowRuns={flowRunsWithFlows}
							selectedRows={selectedRows}
							onSelect={onSelectRow}
						/>
					</div>
				</TabsContent>
				<TabsContent value="task-runs">
					<TaskRunsPlaceholder />
				</TabsContent>
			</Tabs>
		</div>
	);
};

const RunsHeader = () => (
	<header>
		<nav>
			<Typography variant="h2">Runs</Typography>
		</nav>
	</header>
);

const RunsEmptyState = () => (
	<EmptyState>
		<EmptyStateIcon id="Workflow" />
		<EmptyStateTitle>Run a task or flow to get started</EmptyStateTitle>
		<EmptyStateDescription>
			Runs store the state history for each execution of a task or flow.
		</EmptyStateDescription>
		<EmptyStateActions>
			<DocsLink id="getting-started" />
		</EmptyStateActions>
	</EmptyState>
);

const TaskRunsPlaceholder = () => (
	<div className="flex flex-col items-center justify-center py-16">
		<Typography variant="bodySmall" className="text-muted-foreground">
			Task Runs tab coming soon
		</Typography>
	</div>
);
