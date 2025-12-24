import {
	useQuery,
	useQueryClient,
	useSuspenseQuery,
} from "@tanstack/react-query";
import { useState } from "react";
import {
	buildCountTaskRunsQuery,
	buildPaginateTaskRunsQuery,
} from "@/api/task-runs";
import { TaskRunStateFilter } from "@/components/task-runs/task-run-state-filter";
import {
	type TaskRunSortFilters,
	TaskRunsList,
	TaskRunsPagination,
	TaskRunsSortFilter,
} from "@/components/task-runs/task-runs-list";
import type { PaginationState } from "@/components/task-runs/task-runs-list/task-runs-pagination";
import { SearchInput } from "@/components/ui/input";
import { Typography } from "@/components/ui/typography";
import useDebounce from "@/hooks/use-debounce";

type FlowRunTaskRunsProps = {
	flowRunId: string;
};

export const FlowRunTaskRuns = ({ flowRunId }: FlowRunTaskRunsProps) => {
	const queryClient = useQueryClient();
	const [search, setSearch] = useState("");
	const [stateFilter, setStateFilter] = useState<Set<string>>(new Set());
	const [sort, setSort] = useState<TaskRunSortFilters>(
		"EXPECTED_START_TIME_DESC",
	);
	const [pagination, setPagination] = useState<PaginationState>({
		page: 1,
		limit: 20,
	});

	const debouncedSearch = useDebounce(search, 300);

	const { data: countData } = useSuspenseQuery(
		buildCountTaskRunsQuery(
			{
				task_runs: {
					operator: "and_",
					flow_run_id: { operator: "and_", any_: [flowRunId], is_null_: false },
					subflow_runs: { exists_: false },
				},
			},
			30_000,
		),
	);

	const { data: paginatedData } = useQuery(
		buildPaginateTaskRunsQuery(
			{
				task_runs: {
					operator: "and_",
					flow_run_id: { operator: "and_", any_: [flowRunId], is_null_: false },
					subflow_runs: { exists_: false },
					name: debouncedSearch ? { like_: debouncedSearch } : undefined,
					state:
						stateFilter.size > 0
							? {
									operator: "and_",
									name: { any_: Array.from(stateFilter) },
								}
							: undefined,
				},
				sort,
				page: pagination.page,
				limit: pagination.limit,
			},
			30_000,
		),
	);

	const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		setSearch(e.target.value);
		setPagination((prev) => ({ ...prev, page: 1 }));
	};

	const handleStateFilterChange = (newFilters: Set<string>) => {
		setStateFilter(newFilters);
		setPagination((prev) => ({ ...prev, page: 1 }));
	};

	const handleSortChange = (newSort: TaskRunSortFilters) => {
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
			buildPaginateTaskRunsQuery(
				{
					task_runs: {
						operator: "and_",
						flow_run_id: {
							operator: "and_",
							any_: [flowRunId],
							is_null_: false,
						},
						subflow_runs: { exists_: false },
						name: debouncedSearch ? { like_: debouncedSearch } : undefined,
						state:
							stateFilter.size > 0
								? {
										operator: "and_",
										name: { any_: Array.from(stateFilter) },
									}
								: undefined,
					},
					sort,
					page,
					limit: pagination.limit,
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
					No task runs found for this flow run.
				</Typography>
			</div>
		);
	}

	return (
		<div className="flex flex-col gap-4">
			<div className="flex items-center justify-between">
				<Typography variant="bodySmall" className="text-muted-foreground">
					{countData} Task Run{countData !== 1 ? "s" : ""}
				</Typography>
			</div>

			<div className="flex flex-col sm:flex-row gap-2">
				<div className="flex-1">
					<SearchInput
						value={search}
						onChange={handleSearchChange}
						placeholder="Search task runs..."
						debounceMs={300}
					/>
				</div>
				<div className="flex gap-2">
					<div className="w-48">
						<TaskRunStateFilter
							selectedFilters={stateFilter}
							onSelectFilter={handleStateFilterChange}
						/>
					</div>
					<div className="w-40">
						<TaskRunsSortFilter value={sort} onSelect={handleSortChange} />
					</div>
				</div>
			</div>

			<TaskRunsList
				taskRuns={paginatedData?.results}
				onClearFilters={hasFilters ? handleClearFilters : undefined}
			/>

			{paginatedData && paginatedData.pages > 0 && (
				<TaskRunsPagination
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
