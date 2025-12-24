import {
	useQuery,
	useQueryClient,
	useSuspenseQuery,
} from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
	buildCountFlowRunsQuery,
	buildPaginateFlowRunsQuery,
	type FlowRunsCountFilter,
	type FlowRunsPaginateFilter,
	type FlowRunWithFlow,
} from "@/api/flow-runs";
import { buildListFlowsQuery, type Flow } from "@/api/flows";
import { FlowRunsList } from "@/components/flow-runs/flow-runs-list";
import { SortFilter } from "@/components/flow-runs/flow-runs-list/flow-runs-filters/sort-filter";
import type { SortFilters } from "@/components/flow-runs/flow-runs-list/flow-runs-filters/sort-filter.constants";
import { StateFilter } from "@/components/flow-runs/flow-runs-list/flow-runs-filters/state-filter";
import type { FlowRunState } from "@/components/flow-runs/flow-runs-list/flow-runs-filters/state-filters.constants";
import {
	FlowRunsPagination,
	type PaginationState,
} from "@/components/flow-runs/flow-runs-list/flow-runs-pagination";
import { SearchInput } from "@/components/ui/input";
import { Typography } from "@/components/ui/typography";
import useDebounce from "@/hooks/use-debounce";

type FlowRunSubflowsProps = {
	parentFlowRunId: string;
};

export const FlowRunSubflows = ({ parentFlowRunId }: FlowRunSubflowsProps) => {
	const queryClient = useQueryClient();
	const [search, setSearch] = useState("");
	const [stateFilter, setStateFilter] = useState<Set<FlowRunState>>(new Set());
	const [sort, setSort] = useState<SortFilters>("START_TIME_DESC");
	const [pagination, setPagination] = useState<PaginationState>({
		page: 1,
		limit: 10,
	});

	const debouncedSearch = useDebounce(search, 300);

	const countFilter: FlowRunsCountFilter = useMemo(() => {
		return {
			flow_runs: {
				operator: "and_",
				parent_flow_run_id: {
					operator: "and_",
					any_: [parentFlowRunId],
				},
			},
		};
	}, [parentFlowRunId]);

	const { data: countData } = useSuspenseQuery(
		buildCountFlowRunsQuery(countFilter, 30_000),
	);

	const paginateFilter: FlowRunsPaginateFilter = useMemo(() => {
		const baseFilter: FlowRunsPaginateFilter = {
			page: pagination.page,
			limit: pagination.limit,
			sort,
			flow_runs: {
				operator: "and_",
				parent_flow_run_id: {
					operator: "and_",
					any_: [parentFlowRunId],
				},
				name: debouncedSearch ? { like_: debouncedSearch } : undefined,
				state:
					stateFilter.size > 0
						? {
								operator: "and_",
								name: { any_: Array.from(stateFilter) },
							}
						: undefined,
			},
		};
		return baseFilter;
	}, [parentFlowRunId, pagination, sort, debouncedSearch, stateFilter]);

	const { data: paginatedData } = useQuery(
		buildPaginateFlowRunsQuery(paginateFilter, 30_000),
	);

	const flowIds = useMemo(
		() => [
			...new Set(
				(paginatedData?.results ?? []).map((flowRun) => flowRun.flow_id),
			),
		],
		[paginatedData?.results],
	);

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

	const flowRunsWithFlows = useMemo(() => {
		if (!paginatedData?.results) return [];
		const flowMap = new Map(flows?.map((flow: Flow) => [flow.id, flow]) ?? []);
		return paginatedData.results
			.map((flowRun) => {
				const flow = flowMap.get(flowRun.flow_id);
				if (!flow) return { ...flowRun, flow: undefined };
				return {
					...flowRun,
					flow,
				};
			})
			.filter((flowRun) => flowRun !== null) as FlowRunWithFlow[];
	}, [paginatedData?.results, flows]);

	const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		setSearch(e.target.value);
		setPagination((prev) => ({ ...prev, page: 1 }));
	};

	const handleStateFilterChange = (newFilters: Set<FlowRunState>) => {
		setStateFilter(newFilters);
		setPagination((prev) => ({ ...prev, page: 1 }));
	};

	const handleSortChange = (newSort: SortFilters) => {
		setSort(newSort);
		setPagination((prev) => ({ ...prev, page: 1 }));
	};

	const handleClearFilters = () => {
		setSearch("");
		setStateFilter(new Set());
		setPagination((prev) => ({ ...prev, page: 1 }));
	};

	const handlePrefetchPage = (page: number) => {
		void queryClient.prefetchQuery(
			buildPaginateFlowRunsQuery(
				{
					...paginateFilter,
					page,
				},
				30_000,
			),
		);
	};

	const hasFilters = search || stateFilter.size > 0;

	if (countData === 0) {
		return (
			<div className="flex items-center justify-center h-48 border rounded-lg bg-muted/50">
				<Typography className="text-muted-foreground">
					No subflow runs found for this flow run.
				</Typography>
			</div>
		);
	}

	return (
		<div className="flex flex-col gap-4">
			<div className="grid grid-cols-12 items-center gap-2">
				<div className="flex flex-col gap-1 xl:col-span-3 md:col-span-12 col-span-6 md:order-0 order-2">
					<Typography variant="bodySmall" className="text-muted-foreground">
						{countData} Subflow run{countData !== 1 ? "s" : ""}
					</Typography>
				</div>

				<div className="xl:col-span-4 col-span-12 md:order-1 order-0">
					<SearchInput
						value={search}
						onChange={handleSearchChange}
						placeholder="Search by run name"
						aria-label="Search by run name"
						debounceMs={300}
					/>
				</div>
				<div className="xl:col-span-3 md:col-span-6 col-span-12 md:order-2 order-1">
					<StateFilter
						selectedFilters={stateFilter}
						onSelectFilter={handleStateFilterChange}
					/>
				</div>
				<div className="xl:border-l xl:border-border xl:pl-2 xl:col-span-2 md:col-span-6 col-span-6 md:order-3 order-3">
					<SortFilter value={sort} onSelect={handleSortChange} />
				</div>
			</div>

			<FlowRunsList
				flowRuns={flowRunsWithFlows}
				onClearFilters={hasFilters ? handleClearFilters : undefined}
			/>

			{paginatedData && paginatedData.pages > 0 && (
				<FlowRunsPagination
					pagination={pagination}
					onChangePagination={setPagination}
					count={paginatedData.count}
					pages={paginatedData.pages}
					onPrefetchPage={handlePrefetchPage}
				/>
			)}
		</div>
	);
};
