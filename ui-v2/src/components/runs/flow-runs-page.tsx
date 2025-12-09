import type { PaginationState } from "@tanstack/react-table";
import type { Deployment } from "@/api/deployments";
import type { FlowRun } from "@/api/flow-runs";
import type { Flow } from "@/api/flows";
import type { WorkPool } from "@/api/work-pools";
import {
	FlowRunsList,
	FlowRunsPagination,
} from "@/components/flow-runs/flow-runs-list";
import type { DateRangeSelectValue } from "@/components/ui/date-range-select";
import { FlowRunsFilterGroup } from "./flow-runs-filter-group";

export type FlowRunsFilters = {
	search: string;
	deferredSearch: string;
	state: string[];
	flow: string[];
	deployment: string[];
	workPool: string[];
	tag: string[];
	range: DateRangeSelectValue;
	hasActiveFilters: boolean;
	onSearchChange: (value: string) => void;
	onStateChange: (states: string[]) => void;
	onFlowChange: (flows: string[]) => void;
	onDeploymentChange: (deployments: string[]) => void;
	onWorkPoolChange: (workPools: string[]) => void;
	onTagChange: (tags: string[]) => void;
	onDateRangeChange: (range: DateRangeSelectValue) => void;
	onClearFilters: () => void;
};

type FlowRunsPageProps = {
	flowRuns: FlowRun[];
	flows: Flow[];
	deployments: Deployment[];
	workPools: WorkPool[];
	pageCount: number;
	pagination: PaginationState;
	onPaginationChange: (pagination: PaginationState) => void;
	filters: FlowRunsFilters;
};

export const FlowRunsPage = ({
	flowRuns,
	flows,
	deployments,
	workPools,
	pageCount,
	pagination,
	onPaginationChange,
	filters,
}: FlowRunsPageProps) => {
	const handlePaginationChange = (state: { limit: number; page: number }) => {
		onPaginationChange({
			pageIndex: state.page - 1,
			pageSize: state.limit,
		});
	};

	return (
		<div className="flex flex-col gap-4">
			<FlowRunsFilterGroup
				flows={flows}
				deployments={deployments}
				workPools={workPools}
				filters={filters}
			/>
			<FlowRunsList
				flowRuns={flowRuns}
				onClearFilters={
					filters.hasActiveFilters ? filters.onClearFilters : undefined
				}
			/>
			{pageCount > 0 && (
				<FlowRunsPagination
					count={flowRuns.length}
					pages={pageCount}
					pagination={{
						limit: pagination.pageSize,
						page: pagination.pageIndex + 1,
					}}
					onChangePagination={handlePaginationChange}
				/>
			)}
		</div>
	);
};
