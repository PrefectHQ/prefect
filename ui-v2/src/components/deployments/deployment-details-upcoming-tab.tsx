import { getRouteApi } from "@tanstack/react-router";
import { useCallback, useMemo } from "react";
import type { Deployment } from "@/api/deployments";
import { usePaginateFlowRunswithFlows } from "@/api/flow-runs/use-paginate-flow-runs-with-flows";
import {
	type FlowRunState,
	FlowRunsFilters,
	FlowRunsList,
	FlowRunsPagination,
	FlowRunsRowCount,
	type PaginationState,
	type SortFilters,
	useFlowRunsSelectedRows,
} from "@/components/flow-runs/flow-runs-list";

const routeApi = getRouteApi("/deployments/deployment/$id");

type DeploymentDetailsUpcomingTabProps = {
	deployment: Deployment;
};

export const DeploymentDetailsUpcomingTab = ({
	deployment,
}: DeploymentDetailsUpcomingTabProps) => {
	const [selectedRows, setSelectedRows, { clearSet, onSelectRow }] =
		useFlowRunsSelectedRows();
	const [pagination, onChangePagination] = usePagination();
	const [search, setSearch] = useSearch();
	const [sort, setSort] = useSort();
	const [filter, setFilter] = useFilter();
	const resetFilters = useResetFilters();

	const { data } = usePaginateFlowRunswithFlows({
		deployments: {
			operator: "and_",
			id: { any_: [deployment.id] },
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

	const dataWithDeployment = useMemo(() => {
		if (!data) {
			return undefined;
		}
		return {
			...data,
			results: data.results.map((flowRun) => ({ ...flowRun, deployment })),
		};
	}, [data, deployment]);

	const handleResetFilters = !resetFilters
		? undefined
		: () => {
				resetFilters();
				clearSet();
			};

	return (
		<div className="flex flex-col gap-2">
			<div className="flex items-center justify-between">
				<FlowRunsRowCount
					count={dataWithDeployment?.count}
					results={dataWithDeployment?.results}
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
				flowRuns={dataWithDeployment?.results}
				selectedRows={selectedRows}
				onSelect={onSelectRow}
				onClearFilters={handleResetFilters}
			/>

			{dataWithDeployment && dataWithDeployment.results.length > 0 && (
				<FlowRunsPagination
					count={dataWithDeployment.count}
					pagination={pagination}
					onChangePagination={onChangePagination}
					pages={dataWithDeployment.pages}
				/>
			)}
		</div>
	);
};

function useResetFilters() {
	const { upcoming } = routeApi.useSearch();
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
	const hasFiltersApplied = useMemo(() => Boolean(upcoming), [upcoming]);

	return hasFiltersApplied ? resetFilters : undefined;
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
