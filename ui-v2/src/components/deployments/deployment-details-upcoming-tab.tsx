import { getRouteApi } from "@tanstack/react-router";
import { PaginationState } from "@tanstack/react-table";

import { usePaginateFlowRunswithFlows } from "@/api/flow-runs/use-paginate-flow-runs-with-flows";
import {
	FlowRunState,
	FlowRunsDataTable,
	FlowRunsFilters,
	RowSelectionProvider,
	SortFilters,
} from "@/components/flow-runs/data-table";

import { useCallback, useMemo } from "react";

const routeApi = getRouteApi("/deployments/deployment/$id");

type DeploymentDetailsUpcomingTabProps = {
	deploymentId: string;
};

export const DeploymentDetailsUpcomingTab = ({
	deploymentId,
}: DeploymentDetailsUpcomingTabProps) => {
	const [pagination, onPaginationChange] = usePagination();
	const [search, setSearch] = useSearch();
	const [sort, setSort] = useSort();
	const [filter, setFilter] = useFilter();

	const { data } = usePaginateFlowRunswithFlows({
		deployments: {
			operator: "and_",
			id: { any_: [deploymentId] },
		},
		flow_runs: {
			name: { like_: search || undefined },
			state: {
				name: { any_: filter.length === 0 ? undefined : filter },
				operator: "or_",
			},
			operator: "and_",
		},
		limit: pagination.pageSize,
		page: pagination.pageIndex + 1, // + 1 for to account for react table's 0 index
		sort,
	});

	return (
		<RowSelectionProvider>
			<FlowRunsFilters
				flowRunsCount={data?.count}
				search={{ value: search, onChange: setSearch }}
				sort={{ value: sort, onSelect: setSort }}
				stateFilter={{
					value: new Set(filter),
					onSelect: setFilter,
				}}
			/>
			{data ? (
				<FlowRunsDataTable
					flowRuns={data.results}
					flowRunsCount={data.count}
					pagination={pagination}
					pageCount={data.pages}
					onPaginationChange={onPaginationChange}
				/>
			) : null}
		</RowSelectionProvider>
	);
};

function usePagination() {
	const { upcoming } = routeApi.useSearch();
	const navigate = routeApi.useNavigate();

	// React Table uses 0-based pagination, so we need to subtract 1 from the page number
	const pageIndex = (upcoming?.page ?? 1) - 1;
	const pageSize = upcoming?.limit ?? 5;
	const pagination: PaginationState = useMemo(
		() => ({
			pageIndex,
			pageSize,
		}),
		[pageIndex, pageSize],
	);

	const onPaginationChange = useCallback(
		(newPagination: PaginationState) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					page: newPagination.pageIndex + 1,
					limit: newPagination.pageSize,
					upcoming: {
						...upcoming,
						page: newPagination.pageIndex + 1,
						limit: newPagination.pageSize,
					},
				}),
				replace: true,
			});
		},
		[navigate, upcoming],
	);

	return [pagination, onPaginationChange] as const;
}

function useSearch() {
	const { upcoming } = routeApi.useSearch();
	const navigate = routeApi.useNavigate();

	const onSearch = useCallback(
		(value: string) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					upcoming: {
						...upcoming,
						flowRuns: {
							...upcoming?.flowRuns,
							name: value,
						},
					},
				}),
				replace: true,
			});
		},
		[navigate, upcoming],
	);
	const search = useMemo(
		() => upcoming?.flowRuns?.name ?? "",
		[upcoming?.flowRuns?.name],
	);
	return [search, onSearch] as const;
}

function useSort() {
	const { upcoming } = routeApi.useSearch();
	const navigate = routeApi.useNavigate();

	const onSort = useCallback(
		(value: SortFilters | undefined) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					upcoming: {
						...upcoming,
						sort: value,
					},
				}),
				replace: true,
			});
		},
		[navigate, upcoming],
	);
	const sort = useMemo(
		() => upcoming?.sort ?? "START_TIME_ASC",
		[upcoming?.sort],
	);
	return [sort, onSort] as const;
}

function useFilter() {
	const { upcoming } = routeApi.useSearch();
	const navigate = routeApi.useNavigate();

	const onFilter = useCallback(
		(value: Set<FlowRunState>) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					upcoming: {
						...upcoming,
						flowRuns: {
							...upcoming?.flowRuns,
							state: Array.from(value),
						},
					},
				}),
				replace: true,
			});
		},
		[navigate, upcoming],
	);

	const filter = useMemo(
		() =>
			upcoming?.flowRuns?.state ??
			(["Scheduled"] satisfies Array<FlowRunState>),
		[upcoming?.flowRuns?.state],
	);
	return [filter, onFilter] as const;
}
