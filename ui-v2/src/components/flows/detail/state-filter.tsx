import { useMemo } from "react";
import { StateFilter } from "@/components/flow-runs/flow-runs-list/flow-runs-filters/state-filter";
import type { FlowRunState } from "@/components/flow-runs/flow-runs-list/flow-runs-filters/state-filters.constants";
import { Route } from "@/routes/flows/flow.$id";

export const FlowDetailStateFilter = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const selectedStates = useMemo(
		() => new Set((search["runs.flowRuns.state.name"] || []) as FlowRunState[]),
		[search],
	);

	const onSelectFilter = (states: Set<FlowRunState>) => {
		void navigate({
			to: ".",
			search: (prev) => ({
				...prev,
				"runs.flowRuns.state.name": Array.from(states),
				"runs.page": 0,
			}),
		});
	};

	return (
		<StateFilter
			selectedFilters={selectedStates}
			onSelectFilter={onSelectFilter}
		/>
	);
};
