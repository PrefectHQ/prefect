import type { StateType } from "@/api/flow-runs/constants";
import { SearchInput } from "@/components/ui/input";
import { DeploymentFilter } from "./flow-runs-filters/deployment-filter";
import { SortFilter } from "./flow-runs-filters/sort-filter";
import type { SortFilters } from "./flow-runs-filters/sort-filter.constants";
import { StateFilter } from "./flow-runs-filters/state-filter";
import { StateTypeFilter } from "./flow-runs-filters/state-type-filter";
import { WorkPoolFilter } from "./flow-runs-filters/work-pool-filter";

export type FlowRunsFiltersProps = {
	search: {
		onChange: (value: string) => void;
		value: string;
	};
	stateFilter: {
		value: Set<string>;
		onSelect: (filters: Set<string>) => void;
	};
	stateTypeFilter?: {
		value: Set<StateType>;
		onSelect: (types: Set<StateType>) => void;
	};
	deploymentFilter?: {
		value: Set<string>;
		onSelect: (deployments: Set<string>) => void;
	};
	workPoolFilter?: {
		value: Set<string>;
		onSelect: (workPools: Set<string>) => void;
	};
	sort: {
		value: SortFilters | undefined;
		onSelect: (sort: SortFilters) => void;
	};
};

export const FlowRunsFilters = ({
	search,
	sort,
	stateFilter,
	stateTypeFilter,
	deploymentFilter,
	workPoolFilter,
}: FlowRunsFiltersProps) => {
	return (
		<div className="flex flex-wrap items-center gap-2 min-w-0">
			<div className="flex flex-wrap items-center gap-2 pr-2 border-r-2 min-w-0">
				<div className="w-56 max-w-full">
					<SearchInput
						aria-label="search by run name"
						placeholder="Search by run name"
						value={search.value}
						onChange={(e) => search.onChange(e.target.value)}
					/>
				</div>
				{stateTypeFilter && (
					<div className="w-56 max-w-full">
						<StateTypeFilter
							selectedFilters={stateTypeFilter.value}
							onSelectFilter={stateTypeFilter.onSelect}
						/>
					</div>
				)}
				<div className="w-56 max-w-full">
					<StateFilter
						selectedFilters={stateFilter.value}
						onSelectFilter={stateFilter.onSelect}
					/>
				</div>
				{deploymentFilter && (
					<div className="w-56 max-w-full">
						<DeploymentFilter
							selectedDeployments={deploymentFilter.value}
							onSelectDeployments={deploymentFilter.onSelect}
						/>
					</div>
				)}
				{workPoolFilter && (
					<div className="w-56 max-w-full">
						<WorkPoolFilter
							selectedWorkPools={workPoolFilter.value}
							onSelectWorkPools={workPoolFilter.onSelect}
						/>
					</div>
				)}
			</div>
			<SortFilter value={sort.value} onSelect={sort.onSelect} />
		</div>
	);
};
