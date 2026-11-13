import { getRouteApi } from "@tanstack/react-router";
import { useCallback, useMemo } from "react";
import type { StateType } from "@/api/flow-runs/constants";
import type { DateRangeUrlState } from "@/components/flow-runs/flow-runs-list";
import {
	parseStateNames,
	serializeStateNames,
} from "@/components/flow-runs/flow-runs-list/flow-runs-filters/state-filter-utils";

const routeApi = getRouteApi("/runs/");

const parseCommaSeparatedFilter = (filterString: string): string[] => {
	if (!filterString) return [];
	return filterString.split(",").filter((s) => s.trim().length > 0);
};

export type RunsFilters = {
	states: Set<string>;
	stateTypes: Set<StateType>;
	onStateTypesChange: (types: Set<StateType>) => void;
	flows: Set<string>;
	deployments: Set<string>;
	workPools: Set<string>;
	tags: Set<string>;
	dateRange: DateRangeUrlState;

	onStatesChange: (states: Set<string>) => void;
	onFlowsChange: (flows: Set<string>) => void;
	onDeploymentsChange: (deployments: Set<string>) => void;
	onWorkPoolsChange: (workPools: Set<string>) => void;
	onTagsChange: (tags: Set<string>) => void;
	onDateRangeChange: (range: DateRangeUrlState) => void;

	clearAllFilters: () => void;
	hasActiveFilters: boolean;
};

export function useRunsFilters(): RunsFilters {
	const search = routeApi.useSearch();
	const navigate = routeApi.useNavigate();

	const states = useMemo(
		() => new Set<string>(parseStateNames(search.state)),
		[search.state],
	);

	const stateTypeValues = search["state-types"];
	const stateTypes = useMemo(
		() => new Set(stateTypeValues ?? []),
		[stateTypeValues],
	);
	const onStateTypesChange = useCallback(
		(types: Set<StateType>) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					"state-types": [...types],
					page: 1,
					"task-runs-page": 1,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	const flows = useMemo(
		() => new Set<string>(parseCommaSeparatedFilter(search.flows ?? "")),
		[search.flows],
	);

	const deployments = useMemo(
		() => new Set<string>(parseCommaSeparatedFilter(search.deployments ?? "")),
		[search.deployments],
	);

	const workPools = useMemo(
		() =>
			new Set<string>(parseCommaSeparatedFilter(search["work-pools"] ?? "")),
		[search["work-pools"]],
	);

	const tags = useMemo(
		() => new Set<string>(parseCommaSeparatedFilter(search.tags ?? "")),
		[search.tags],
	);

	const dateRange: DateRangeUrlState = useMemo(
		() => ({
			range: search.range,
			start: search.start,
			end: search.end,
		}),
		[search.range, search.start, search.end],
	);

	const onStatesChange = useCallback(
		(newStates: Set<string>) => {
			const statesArray = Array.from(newStates);
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					state: serializeStateNames(statesArray),
					page: 1,
					"task-runs-page": 1,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	const onFlowsChange = useCallback(
		(newFlows: Set<string>) => {
			const flowsArray = Array.from(newFlows);
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					flows: flowsArray.length > 0 ? flowsArray.join(",") : "",
					page: 1,
					"task-runs-page": 1,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	const onDeploymentsChange = useCallback(
		(newDeployments: Set<string>) => {
			const deploymentsArray = Array.from(newDeployments);
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					deployments:
						deploymentsArray.length > 0 ? deploymentsArray.join(",") : "",
					page: 1,
					"task-runs-page": 1,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	const onWorkPoolsChange = useCallback(
		(newWorkPools: Set<string>) => {
			const workPoolsArray = Array.from(newWorkPools);
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					"work-pools":
						workPoolsArray.length > 0 ? workPoolsArray.join(",") : "",
					page: 1,
					"task-runs-page": 1,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	const onTagsChange = useCallback(
		(newTags: Set<string>) => {
			const tagsArray = Array.from(newTags);
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					tags: tagsArray.length > 0 ? tagsArray.join(",") : "",
					page: 1,
					"task-runs-page": 1,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	const onDateRangeChange = useCallback(
		(newDateRange: DateRangeUrlState) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					range: newDateRange.range,
					start: newDateRange.start,
					end: newDateRange.end,
					page: 1,
					"task-runs-page": 1,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	const hasActiveFilters = useMemo(() => {
		return (
			states.size > 0 ||
			stateTypes.size > 0 ||
			flows.size > 0 ||
			deployments.size > 0 ||
			workPools.size > 0 ||
			tags.size > 0 ||
			dateRange.range !== undefined ||
			dateRange.start !== undefined ||
			dateRange.end !== undefined
		);
	}, [states, stateTypes, flows, deployments, workPools, tags, dateRange]);

	const clearAllFilters = useCallback(() => {
		void navigate({
			to: ".",
			search: (prev) => ({
				...prev,
				state: "",
				"state-types": undefined,
				flows: "",
				deployments: "",
				"work-pools": "",
				tags: "",
				range: undefined,
				start: undefined,
				end: undefined,
				page: 1,
				"task-runs-page": 1,
			}),
			replace: true,
		});
	}, [navigate]);

	return {
		states,
		stateTypes,
		onStateTypesChange,
		flows,
		deployments,
		workPools,
		tags,
		dateRange,
		onStatesChange,
		onFlowsChange,
		onDeploymentsChange,
		onWorkPoolsChange,
		onTagsChange,
		onDateRangeChange,
		clearAllFilters,
		hasActiveFilters,
	};
}
