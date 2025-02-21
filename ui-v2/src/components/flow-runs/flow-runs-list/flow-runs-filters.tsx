import { RunNameSearch } from "./flow-runs-filters/run-name-search";
import { SortFilter } from "./flow-runs-filters/sort-filter";
import type { SortFilters } from "./flow-runs-filters/sort-filter.constants";
import { StateFilter } from "./flow-runs-filters/state-filter";
import type { FlowRunState } from "./flow-runs-filters/state-filters.constants";

export type FlowRunsFiltersProps = {
	search: {
		onChange: (value: string) => void;
		value: string;
	};
	stateFilter: {
		value: Set<FlowRunState>;
		onSelect: (filters: Set<FlowRunState>) => void;
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
}: FlowRunsFiltersProps) => {
	return (
		<div className="flex items-center gap-2">
			<div className="flex items-center gap-2 pr-2 border-r-2">
				<div className="min-w-56">
					<RunNameSearch
						value={search.value}
						onChange={(e) => search.onChange(e.target.value)}
						placeholder="Search by run name"
					/>
				</div>
				<div className="min-w-56">
					<StateFilter
						selectedFilters={stateFilter.value}
						onSelectFilter={stateFilter.onSelect}
					/>
				</div>
			</div>
			<SortFilter value={sort.value} onSelect={sort.onSelect} />
		</div>
	);
};
