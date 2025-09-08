import { useQuery } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";
import {
	buildCountFlowRunsQuery,
	buildPaginateFlowRunsQuery,
	type FlowRunsCountFilter,
	type FlowRunsPaginateFilter,
	type FlowRunWithFlow,
} from "@/api/flow-runs";
import { buildListFlowsQuery, type Flow } from "@/api/flows";
import { FlowRunsList } from "@/components/flow-runs/flow-runs-list";
import { StateFilter } from "@/components/flow-runs/flow-runs-list/flow-runs-filters/state-filter";
import type { FlowRunState } from "@/components/flow-runs/flow-runs-list/flow-runs-filters/state-filters.constants";
import {
	FlowRunsPagination,
	type PaginationState,
} from "@/components/flow-runs/flow-runs-list/flow-runs-pagination";
import { SearchInput } from "@/components/ui/input";
import useDebounce from "@/hooks/use-debounce";

type WorkPoolFlowRunsTabProps = {
	workPoolName: string;
	className?: string;
};

export const WorkPoolFlowRunsTab = ({
	workPoolName,
	className,
}: WorkPoolFlowRunsTabProps) => {
	const [pagination, setPagination] = useState<PaginationState>({
		limit: 10,
		page: 1,
	});
	const [searchTerm, setSearchTerm] = useState("");
	const [selectedStates, setSelectedStates] = useState<Set<FlowRunState>>(
		new Set(),
	);

	// Debounce the search term to avoid too many API calls
	const debouncedSearchTerm = useDebounce(searchTerm, 500);

	const filter: FlowRunsPaginateFilter = useMemo(() => {
		const baseFilter: FlowRunsPaginateFilter = {
			page: pagination.page,
			limit: pagination.limit,
			sort: "START_TIME_DESC",
			work_pools: {
				operator: "and_",
				name: { any_: [workPoolName] },
			},
		};

		// Add search filter if search term exists
		if (debouncedSearchTerm.trim()) {
			baseFilter.flow_runs = {
				operator: "and_",
				name: { like_: debouncedSearchTerm.trim() },
			};
		}

		// Add state filter if states are selected
		if (selectedStates.size > 0) {
			const stateFilter = {
				state: {
					operator: "and_" as const,
					name: { any_: Array.from(selectedStates) },
				},
			};

			if (baseFilter.flow_runs) {
				// Merge with existing flow_runs filter
				baseFilter.flow_runs = {
					...baseFilter.flow_runs,
					...stateFilter,
				};
			} else {
				baseFilter.flow_runs = {
					operator: "and_",
					...stateFilter,
				};
			}
		}

		return baseFilter;
	}, [workPoolName, pagination, debouncedSearchTerm, selectedStates]);

	const countFilter: FlowRunsCountFilter = useMemo(() => {
		const baseCountFilter: FlowRunsCountFilter = {
			work_pools: {
				operator: "and_",
				name: { any_: [workPoolName] },
			},
		};

		// Add search filter to count if search term exists
		if (debouncedSearchTerm.trim()) {
			baseCountFilter.flow_runs = {
				operator: "and_",
				name: { like_: debouncedSearchTerm.trim() },
			};
		}

		// Add state filter to count if states are selected
		if (selectedStates.size > 0) {
			const stateFilter = {
				state: {
					operator: "and_" as const,
					name: { any_: Array.from(selectedStates) },
				},
			};

			if (baseCountFilter.flow_runs) {
				// Merge with existing flow_runs filter
				baseCountFilter.flow_runs = {
					...baseCountFilter.flow_runs,
					...stateFilter,
				};
			} else {
				baseCountFilter.flow_runs = {
					operator: "and_",
					...stateFilter,
				};
			}
		}

		return baseCountFilter;
	}, [workPoolName, debouncedSearchTerm, selectedStates]);

	// Fetch paginated flow runs data
	const { data: paginatedData } = useQuery(buildPaginateFlowRunsQuery(filter));

	// Fetch total count for pagination
	const { data: totalCount } = useQuery(buildCountFlowRunsQuery(countFilter));

	// Get unique flow IDs for fetching flow details
	const flowIds = useMemo(
		() => [
			...new Set(
				(paginatedData?.results ?? []).map((flowRun) => flowRun.flow_id),
			),
		],
		[paginatedData?.results],
	);

	// Fetch flow details
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

	// Combine flow runs with their corresponding flows
	const flowRunsWithFlows = useMemo(() => {
		if (!paginatedData?.results) return [];
		const flowMap = new Map(flows?.map((flow: Flow) => [flow.id, flow]) ?? []);
		return paginatedData.results
			.map((flowRun) => {
				const flow = flowMap.get(flowRun.flow_id);
				if (!flow) return null;
				return {
					...flowRun,
					flow,
				};
			})
			.filter((flowRun) => flowRun !== null) as FlowRunWithFlow[];
	}, [paginatedData?.results, flows]);

	const handleSearchChange = useCallback(
		(event: React.ChangeEvent<HTMLInputElement>) => {
			setSearchTerm(event.target.value);
			// Reset to first page when searching
			setPagination((prev) => ({ ...prev, page: 1 }));
		},
		[],
	);

	const handlePaginationChange = useCallback(
		(newPagination: PaginationState) => {
			setPagination(newPagination);
		},
		[],
	);

	const handleStateFilterChange = useCallback(
		(newSelectedStates: Set<FlowRunState>) => {
			setSelectedStates(newSelectedStates);
			// Reset to first page when filtering
			setPagination((prev) => ({ ...prev, page: 1 }));
		},
		[],
	);

	const handleClearFilters = useCallback(() => {
		setSearchTerm("");
		setSelectedStates(new Set());
		setPagination((prev) => ({ ...prev, page: 1 }));
	}, []);

	// Show loading only on initial load, not on pagination/filtering changes
	if (!paginatedData || totalCount === undefined) {
		return (
			<div className={className}>
				<div className="text-muted-foreground text-center py-8">
					Loading flow runs...
				</div>
			</div>
		);
	}

	return (
		<div className={className}>
			{/* Search and Filter Controls */}
			<div className="flex flex-col sm:flex-row gap-4 mb-6">
				<div className="flex-1">
					<SearchInput
						placeholder="Search flow runs by name..."
						value={searchTerm}
						onChange={handleSearchChange}
						debounceMs={500}
					/>
				</div>
				<div className="w-full sm:w-64">
					<StateFilter
						selectedFilters={selectedStates}
						onSelectFilter={handleStateFilterChange}
					/>
				</div>
			</div>

			{/* Flow Runs List */}
			<FlowRunsList
				flowRuns={flowRunsWithFlows}
				onClearFilters={
					flowRunsWithFlows.length === 0 ? handleClearFilters : undefined
				}
			/>

			{/* Pagination Controls */}
			{paginatedData.pages > 1 && (
				<div className="mt-6">
					<FlowRunsPagination
						count={totalCount}
						pages={paginatedData.pages}
						pagination={pagination}
						onChangePagination={handlePaginationChange}
					/>
				</div>
			)}
		</div>
	);
};
