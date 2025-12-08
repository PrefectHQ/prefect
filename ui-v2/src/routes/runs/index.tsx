import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { useCallback, useMemo } from "react";
import { z } from "zod";
import {
	buildCountFlowRunsQuery,
	buildPaginateFlowRunsQuery,
	type FlowRunsPaginateFilter,
} from "@/api/flow-runs";
import {
	FLOW_RUN_STATES_MAP,
	type FlowRunState,
	FlowRunsFilters,
	FlowRunsList,
	FlowRunsPagination,
	FlowRunsRowCount,
	type PaginationState,
	type SortFilters,
	useFlowRunsSelectedRows,
} from "@/components/flow-runs/flow-runs-list";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Typography } from "@/components/ui/typography";

const searchParams = z.object({
	tab: z.enum(["flow-runs", "task-runs"]).optional().default("flow-runs"),
	page: z.number().int().positive().optional().default(1).catch(1),
	limit: z.number().int().positive().optional().default(10).catch(10),
	sort: z
		.enum(["START_TIME_ASC", "START_TIME_DESC", "NAME_ASC", "NAME_DESC"])
		.optional()
		.default("START_TIME_DESC")
		.catch("START_TIME_DESC"),
	search: z.string().optional().default("").catch(""),
	state: z.array(z.string()).optional().default([]).catch([]),
});

const getStateType = (state: FlowRunState) => FLOW_RUN_STATES_MAP[state];

const buildPaginationBody = (
	search?: z.infer<typeof searchParams>,
): FlowRunsPaginateFilter => {
	const stateFilters = (search?.state ?? []).filter(
		(s): s is FlowRunState => s in FLOW_RUN_STATES_MAP,
	);
	const stateTypes = [...new Set(stateFilters.map(getStateType))];
	const stateNames = stateFilters.length > 0 ? stateFilters : undefined;

	return {
		page: search?.page ?? 1,
		limit: search?.limit ?? 10,
		sort: search?.sort ?? "START_TIME_DESC",
		flow_runs: {
			operator: "and_",
			name: search?.search ? { like_: search.search } : undefined,
			state:
				stateTypes.length > 0
					? {
							operator: "and_",
							type: { any_: stateTypes },
							name: stateNames ? { any_: stateNames } : undefined,
						}
					: undefined,
		},
	};
};

export const Route = createFileRoute("/runs/")({
	validateSearch: zodValidator(searchParams),
	component: RouteComponent,
	loaderDeps: ({ search }) => buildPaginationBody(search),
	loader: async ({ deps, context }) => {
		const flowRunsCountResult = context.queryClient.ensureQueryData(
			buildCountFlowRunsQuery(),
		);

		const flowRunsPaginateResult = await context.queryClient.ensureQueryData(
			buildPaginateFlowRunsQuery(deps),
		);

		return {
			flowRunsCountResult,
			flowRunsPaginateResult,
		};
	},
	wrapInSuspense: true,
});

const usePagination = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const pagination: PaginationState = useMemo(
		() => ({
			page: search.page ?? 1,
			limit: search.limit ?? 10,
		}),
		[search.page, search.limit],
	);

	const onPaginationChange = useCallback(
		(newPagination: PaginationState) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					page: newPagination.page,
					limit: newPagination.limit,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	return [pagination, onPaginationChange] as const;
};

const useSort = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const onSortChange = useCallback(
		(sort: SortFilters) => {
			void navigate({
				to: ".",
				search: (prev) => ({ ...prev, sort }),
				replace: true,
			});
		},
		[navigate],
	);

	return [search.sort, onSortChange] as const;
};

const useSearchFilter = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const onSearchChange = useCallback(
		(value: string) => {
			void navigate({
				to: ".",
				search: (prev) => ({ ...prev, search: value, page: 1 }),
				replace: true,
			});
		},
		[navigate],
	);

	return [search.search, onSearchChange] as const;
};

const useStateFilter = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const stateFilters = useMemo(
		() => new Set(search.state as FlowRunState[]),
		[search.state],
	);

	const onStateFilterChange = useCallback(
		(filters: Set<FlowRunState>) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					state: Array.from(filters),
					page: 1,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	return [stateFilters, onStateFilterChange] as const;
};

const useTab = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const onTabChange = useCallback(
		(tab: string) => {
			void navigate({
				to: ".",
				search: (prev) => ({ ...prev, tab: tab as "flow-runs" | "task-runs" }),
				replace: true,
			});
		},
		[navigate],
	);

	return [search.tab, onTabChange] as const;
};

function RouteComponent() {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();
	const [pagination, onPaginationChange] = usePagination();
	const [sort, onSortChange] = useSort();
	const [searchValue, onSearchChange] = useSearchFilter();
	const [stateFilters, onStateFilterChange] = useStateFilter();
	const [tab, onTabChange] = useTab();
	const [selectedRows, setSelectedRows] = useFlowRunsSelectedRows();

	const { data: flowRunsCount } = useSuspenseQuery(buildCountFlowRunsQuery());
	const { data: flowRunsPage } = useSuspenseQuery(
		buildPaginateFlowRunsQuery(buildPaginationBody(search)),
	);

	const flowRuns = flowRunsPage?.results ?? [];

	const handleClearFilters = useCallback(() => {
		void navigate({
			to: ".",
			search: { tab },
			replace: true,
		});
	}, [navigate, tab]);

	const hasFilters =
		searchValue !== "" || stateFilters.size > 0 || sort !== "START_TIME_DESC";

	return (
		<div className="flex flex-col gap-4">
			<Typography variant="h2">Runs</Typography>
			<Tabs value={tab} onValueChange={onTabChange}>
				<TabsList>
					<TabsTrigger value="flow-runs">Flow runs</TabsTrigger>
					<TabsTrigger value="task-runs">Task runs</TabsTrigger>
				</TabsList>
				<TabsContent value="flow-runs" className="flex flex-col gap-4">
					{flowRunsCount === 0 && !hasFilters ? (
						<div className="flex justify-center py-4">
							<Typography>No flow runs yet</Typography>
						</div>
					) : (
						<>
							<FlowRunsFilters
								search={{
									value: searchValue,
									onChange: onSearchChange,
								}}
								stateFilter={{
									value: stateFilters,
									onSelect: onStateFilterChange,
								}}
								sort={{
									value: sort,
									onSelect: onSortChange,
								}}
							/>
							<div className="flex items-center justify-between">
								<FlowRunsRowCount
									count={flowRunsPage?.count}
									results={flowRuns}
									selectedRows={selectedRows}
									setSelectedRows={setSelectedRows}
								/>
							</div>
							<FlowRunsList
								flowRuns={flowRuns}
								selectedRows={selectedRows}
								onSelect={(id, checked) => {
									if (checked) {
										setSelectedRows(new Set([...selectedRows, id]));
									} else {
										const newSet = new Set(selectedRows);
										newSet.delete(id);
										setSelectedRows(newSet);
									}
								}}
								onClearFilters={hasFilters ? handleClearFilters : undefined}
							/>
							{flowRunsPage && flowRunsPage.pages > 0 && (
								<FlowRunsPagination
									count={flowRunsPage.count}
									pages={flowRunsPage.pages}
									pagination={pagination}
									onChangePagination={onPaginationChange}
								/>
							)}
						</>
					)}
				</TabsContent>
				<TabsContent value="task-runs">
					<div className="flex justify-center py-4">
						<Typography>Task runs tab coming soon</Typography>
					</div>
				</TabsContent>
			</Tabs>
		</div>
	);
}
