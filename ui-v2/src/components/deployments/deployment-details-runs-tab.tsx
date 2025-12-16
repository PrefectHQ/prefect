import { getRouteApi } from "@tanstack/react-router";
import { useCallback, useMemo } from "react";
import type { Deployment } from "@/api/deployments";
import { useFilterFlowRunswithFlows } from "@/api/flow-runs/use-filter-flow-runs-with-flows";
import { usePaginateFlowRunswithFlows } from "@/api/flow-runs/use-paginate-flow-runs-with-flows";
import { FlowRunCard } from "@/components/flow-runs/flow-run-card";
import {
	FLOW_RUN_STATES_NO_SCHEDULED,
	type FlowRunState,
	FlowRunsFilters,
	FlowRunsList,
	FlowRunsPagination,
	FlowRunsRowCount,
	type PaginationState,
	type SortFilters,
	useFlowRunsSelectedRows,
} from "@/components/flow-runs/flow-runs-list";
import { Typography } from "@/components/ui/typography";

const routeApi = getRouteApi("/deployments/deployment/$id");

type DeploymentDetailsRunsTabProps = {
	deployment: Deployment;
};

export const DeploymentDetailsRunsTab = ({
	deployment,
}: DeploymentDetailsRunsTabProps) => {
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

	const nextRun = useGetNextRun(deployment);

	return (
		<div className="flex flex-col gap-2">
			{nextRun && (
				<div className="flex flex-col gap-2 border-b py-2">
					<Typography variant="bodyLarge">Next Run</Typography>
					<FlowRunCard flowRun={nextRun} />
				</div>
			)}
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

				{dataWithDeployment && (
					<FlowRunsPagination
						count={dataWithDeployment.count}
						pagination={pagination}
						onChangePagination={onChangePagination}
						pages={dataWithDeployment.pages}
					/>
				)}
			</div>
		</div>
	);
};

function useGetNextRun(deployment: Deployment) {
	const { data } = useFilterFlowRunswithFlows({
		deployments: { id: { any_: [deployment.id] }, operator: "and_" },
		flow_runs: {
			state: { name: { any_: ["Scheduled"] }, operator: "and_" },
			operator: "and_",
		},
		sort: "EXPECTED_START_TIME_ASC",
		limit: 1,
		offset: 0,
	});

	return useMemo(() => {
		if (!data || !data[0]) {
			return undefined;
		}
		return {
			...data[0],
			deployment,
		};
	}, [data, deployment]);
}

function useResetFilters() {
	const { runs } = routeApi.useSearch();
	const navigate = routeApi.useNavigate();
	const resetFilters = useCallback(() => {
		void navigate({
			to: ".",
			search: (prev) => ({
				...prev,
				runs: undefined,
			}),
			replace: true,
		});
	}, [navigate]);
	const hasFiltersApplied = useMemo(() => Boolean(runs), [runs]);

	return hasFiltersApplied ? resetFilters : undefined;
}

function usePagination() {
	const { runs } = routeApi.useSearch();
	const navigate = routeApi.useNavigate();

	const onChangePagination = useCallback(
		(pagination?: PaginationState) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					runs: {
						...runs,
						...pagination,
					},
				}),
				replace: true,
			});
		},
		[navigate, runs],
	);

	const pagination = useMemo(() => {
		return {
			page: runs?.page ?? 1,
			limit: runs?.limit ?? 10,
		};
	}, [runs?.limit, runs?.page]);

	return [pagination, onChangePagination] as const;
}

function useSearch() {
	const { runs } = routeApi.useSearch();
	const navigate = routeApi.useNavigate();

	const onSearch = useCallback(
		(value?: string) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					runs: {
						...runs,
						flowRuns: {
							...runs?.flowRuns,
							name: value,
						},
					},
				}),
				replace: true,
			});
		},
		[navigate, runs],
	);
	const search = useMemo(
		() => runs?.flowRuns?.name ?? "",
		[runs?.flowRuns?.name],
	);
	return [search, onSearch] as const;
}

function useSort() {
	const { runs } = routeApi.useSearch();
	const navigate = routeApi.useNavigate();

	const onSort = useCallback(
		(value?: SortFilters) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					runs: {
						...runs,
						sort: value,
					},
				}),
				replace: true,
			});
		},
		[navigate, runs],
	);
	const sort = useMemo(() => runs?.sort ?? "START_TIME_DESC", [runs?.sort]);
	return [sort, onSort] as const;
}

function useFilter() {
	const { runs } = routeApi.useSearch();
	const navigate = routeApi.useNavigate();

	const onFilter = useCallback(
		(value?: Set<FlowRunState>) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					runs: {
						...runs,
						flowRuns: {
							...runs?.flowRuns,
							state: value ? Array.from(value) : undefined,
						},
					},
				}),
				replace: true,
			});
		},
		[navigate, runs],
	);

	const filter = useMemo(
		() =>
			runs?.flowRuns?.state ??
			(FLOW_RUN_STATES_NO_SCHEDULED satisfies Array<FlowRunState>),
		[runs?.flowRuns?.state],
	);
	return [filter, onFilter] as const;
}
