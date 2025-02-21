import { getRouteApi } from "@tanstack/react-router";

import { usePaginateFlowRunswithFlows } from "@/api/flow-runs/use-paginate-flow-runs-with-flows";
import { FlowRunState, SortFilters } from "@/components/flow-runs/data-table";
import {
	FlowRunsFilters,
	FlowRunsList,
	FlowRunsPagination,
	FlowRunsRowCount,
	type PaginationState,
} from "@/components/flow-runs/flow-runs-list";
import { useCallback, useMemo, useState } from "react";

const routeApi = getRouteApi("/deployments/deployment/$id");

type DeploymentDetailsUpcomingTabProps = {
	deploymentId: string;
};

export const DeploymentDetailsUpcomingTab = ({
	deploymentId,
}: DeploymentDetailsUpcomingTabProps) => {
	const [selectedRows, setSelectedRows] = useState<Set<string>>(new Set());
	const [pagination, onChangePagination] = usePagination();
	const [search, setSearch] = useSearch();
	const [sort, setSort] = useSort();
	const [filter, setFilter] = useFilter();
	const resetFilters = useResetFilters();

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
		limit: pagination.limit,
		page: pagination.page,
		sort,
	});

	const handleResetFilters = () => {
		resetFilters();
		setSelectedRows(new Set());
	};

	const addRow = (id: string) =>
		setSelectedRows((curr) => new Set(curr).add(id));
	const removeRow = (id: string) =>
		setSelectedRows((curr) => {
			const newValue = new Set(curr);
			newValue.delete(id);
			return newValue;
		});

	const handleSelectRow = (id: string, checked: boolean) => {
		if (checked) {
			addRow(id);
		} else {
			removeRow(id);
		}
	};

	return (
		<div className="flex flex-col gap-2">
			<div className="flex items-center justify-between">
				<FlowRunsRowCount
					count={data?.count}
					results={data?.results}
					selectedRows={selectedRows}
					setSelectedRows={setSelectedRows}
				/>
				<FlowRunsFilters
					search={{ value: search, onChange: setSearch }}
					sort={{ value: sort, onSelect: setSort }}
					stateFilter={{
						value: new Set(filter),
						onSelect: setFilter,
					}}
				/>
			</div>

			<FlowRunsList
				flowRuns={data?.results}
				selectedRows={selectedRows}
				onSelect={handleSelectRow}
				onClearFilters={handleResetFilters}
			/>

			{data && data.results.length > 0 && (
				<FlowRunsPagination
					pagination={pagination}
					onChangePagination={onChangePagination}
					pages={data.pages}
				/>
			)}
		</div>
	);
};

function useResetFilters() {
	const navigate = routeApi.useNavigate();
	const resetFilters = useCallback(() => {
		void navigate({
			to: ".",
			search: (prev) => ({
				...prev,
				upcoming: undefined,
			}),
			replace: true,
		});
	}, [navigate]);
	return resetFilters;
}

function usePagination() {
	const { upcoming } = routeApi.useSearch();
	const navigate = routeApi.useNavigate();

	const onChangePagination = useCallback(
		(pagination?: PaginationState) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					upcoming: {
						...upcoming,
						...pagination,
					},
				}),
				replace: true,
			});
		},
		[navigate, upcoming],
	);

	const pagination = useMemo(() => {
		return {
			page: upcoming?.page ?? 1,
			limit: upcoming?.limit ?? 5,
		};
	}, [upcoming?.limit, upcoming?.page]);

	return [pagination, onChangePagination] as const;
}

function useSearch() {
	const { upcoming } = routeApi.useSearch();
	const navigate = routeApi.useNavigate();

	const onSearch = useCallback(
		(value?: string) => {
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
		(value?: SortFilters) => {
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
		(value?: Set<FlowRunState>) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					upcoming: {
						...upcoming,
						flowRuns: {
							...upcoming?.flowRuns,
							state: value ? Array.from(value) : undefined,
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
