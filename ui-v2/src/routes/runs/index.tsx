import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { useCallback, useMemo } from "react";
import { z } from "zod";
import {
	buildCountTaskRunsQuery,
	buildPaginateTaskRunsQuery,
	type TaskRunsPaginateFilter,
} from "@/api/task-runs";
import {
	type PaginationState,
	type TaskRunSortOption,
	TaskRunsFilters,
	TaskRunsList,
	TaskRunsPagination,
} from "@/components/task-runs/task-runs-list";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Typography } from "@/components/ui/typography";

const searchParams = z.object({
	tab: z.enum(["flow-runs", "task-runs"]).optional().default("task-runs"),
	"task-runs-page": z.number().int().positive().optional().default(1).catch(1),
	"task-runs-limit": z
		.number()
		.int()
		.positive()
		.optional()
		.default(10)
		.catch(10),
	"task-runs-sort": z
		.enum([
			"EXPECTED_START_TIME_DESC",
			"EXPECTED_START_TIME_ASC",
			"NAME_ASC",
			"NAME_DESC",
		])
		.optional()
		.default("EXPECTED_START_TIME_DESC")
		.catch("EXPECTED_START_TIME_DESC"),
	"task-runs-search": z.string().optional().default("").catch(""),
});

type SearchParams = z.infer<typeof searchParams>;

const buildTaskRunsFilterBody = (
	search: SearchParams,
): TaskRunsPaginateFilter => ({
	page: search["task-runs-page"],
	limit: search["task-runs-limit"],
	sort: search["task-runs-sort"],
	task_runs: search["task-runs-search"]
		? {
				operator: "and_",
				name: { like_: search["task-runs-search"] },
			}
		: undefined,
});

export const Route = createFileRoute("/runs/")({
	validateSearch: zodValidator(searchParams),
	component: RouteComponent,
	loaderDeps: ({ search }) => buildTaskRunsFilterBody(search),
	loader: async ({ deps, context }) => {
		const taskRunsCountResult = await context.queryClient.ensureQueryData(
			buildCountTaskRunsQuery(
				deps.task_runs ? { task_runs: deps.task_runs } : {},
			),
		);

		const taskRunsPaginateResult = await context.queryClient.ensureQueryData(
			buildPaginateTaskRunsQuery(deps),
		);

		return {
			taskRunsCountResult,
			taskRunsPaginateResult,
		};
	},
	wrapInSuspense: true,
});

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

const useTaskRunsPagination = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const pagination: PaginationState = useMemo(
		() => ({
			page: search["task-runs-page"],
			limit: search["task-runs-limit"],
		}),
		[search],
	);

	const onPaginationChange = useCallback(
		(newPagination: PaginationState) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					"task-runs-page": newPagination.page,
					"task-runs-limit": newPagination.limit,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	return [pagination, onPaginationChange] as const;
};

const useTaskRunsSort = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const onSortChange = useCallback(
		(sort: TaskRunSortOption) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					"task-runs-sort": sort,
					"task-runs-page": 1,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	return [search["task-runs-sort"], onSortChange] as const;
};

const useTaskRunsSearch = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const onSearchChange = useCallback(
		(value: string) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					"task-runs-search": value,
					"task-runs-page": 1,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	return [search["task-runs-search"], onSearchChange] as const;
};

const useClearFilters = () => {
	const navigate = Route.useNavigate();

	return useCallback(() => {
		void navigate({
			to: ".",
			search: (prev) => ({
				...prev,
				"task-runs-search": "",
				"task-runs-page": 1,
			}),
			replace: true,
		});
	}, [navigate]);
};

function RouteComponent() {
	const search = Route.useSearch();
	const [tab, onTabChange] = useTab();
	const [pagination, onPaginationChange] = useTaskRunsPagination();
	const [sort, onSortChange] = useTaskRunsSort();
	const [searchValue, onSearchChange] = useTaskRunsSearch();
	const clearFilters = useClearFilters();

	const filterBody = buildTaskRunsFilterBody(search);

	const { data: taskRunsCount } = useSuspenseQuery(
		buildCountTaskRunsQuery(
			filterBody.task_runs ? { task_runs: filterBody.task_runs } : {},
		),
	);

	const { data: taskRunsPage } = useSuspenseQuery(
		buildPaginateTaskRunsQuery(filterBody),
	);

	const taskRuns = taskRunsPage?.results ?? [];
	const pages = taskRunsPage?.pages ?? 0;

	const hasFilters = searchValue !== "";

	return (
		<div className="flex flex-col gap-4">
			<Typography variant="h2">Runs</Typography>
			<Tabs value={tab} onValueChange={onTabChange}>
				<TabsList>
					<TabsTrigger value="flow-runs">Flow Runs</TabsTrigger>
					<TabsTrigger value="task-runs">Task Runs</TabsTrigger>
				</TabsList>
				<TabsContent value="flow-runs" className="mt-4">
					<div className="flex flex-col gap-4">
						<Typography className="text-muted-foreground">
							Flow runs tab coming soon...
						</Typography>
					</div>
				</TabsContent>
				<TabsContent value="task-runs" className="mt-4">
					<div className="flex flex-col gap-4">
						<TaskRunsFilters
							search={{
								value: searchValue,
								onChange: onSearchChange,
							}}
							sort={{
								value: sort,
								onSelect: onSortChange,
							}}
						/>
						<TaskRunsPagination
							count={taskRunsCount}
							pages={pages}
							pagination={pagination}
							onChangePagination={onPaginationChange}
						/>
						<TaskRunsList
							taskRuns={taskRuns}
							onClearFilters={hasFilters ? clearFilters : undefined}
						/>
					</div>
				</TabsContent>
			</Tabs>
		</div>
	);
}
