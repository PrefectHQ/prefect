import {
	useQuery,
	useQueryClient,
	useSuspenseQuery,
} from "@tanstack/react-query";
import type { ChangeEvent } from "react";
import { useMemo, useState } from "react";
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
import { TagsInput } from "@/components/ui/tags-input";
import { Typography } from "@/components/ui/typography";
import useDebounce from "@/hooks/use-debounce";

type FlowRunTaskRunsProps = {
	flowRunId: string;
};

export const FlowRunTaskRuns = ({ flowRunId }: FlowRunTaskRunsProps) => {
	const queryClient = useQueryClient();
	const [search, setSearch] = useState("");
	const [stateFilter, setStateFilter] = useState<Set<string>>(new Set());
	const [tagsFilter, setTagsFilter] = useState<Set<string>>(new Set());
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
					tags:
						tagsFilter.size > 0
							? {
									operator: "and_",
									all_: Array.from(tagsFilter),
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

	const handleTagsFilterChange = (
		tags: string[] | ChangeEvent<HTMLInputElement>,
	) => {
		const newTags = Array.isArray(tags) ? tags : [];
		setTagsFilter(new Set(newTags));
		setPagination((prev) => ({ ...prev, page: 1 }));
	};

	const handleClearFilters = () => {
		setSearch("");
		setStateFilter(new Set());
		setTagsFilter(new Set());
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
						tags:
							tagsFilter.size > 0
								? {
										operator: "and_",
										all_: Array.from(tagsFilter),
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

	const hasFilters = search || stateFilter.size > 0 || tagsFilter.size > 0;

	// Calculate state summary from paginated results
	const stateSummary = useMemo(() => {
		if (!paginatedData?.results) return null;
		const stateCounts = new Map<string, number>();
		for (const taskRun of paginatedData.results) {
			const stateName = String(taskRun.state?.name ?? "Unknown");
			stateCounts.set(stateName, (stateCounts.get(stateName) ?? 0) + 1);
		}
		return Array.from(stateCounts.entries())
			.map(([name, count]) => `${count} ${name}`)
			.join(", ");
	}, [paginatedData?.results]);

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
			{/* Mobile: controls on top, count/sort on bottom. Desktop: count | controls | sort */}
			<div className="grid grid-cols-12 items-center gap-2">
				{/* Count - first column */}
				<div className="flex flex-col gap-1 xl:col-span-3 md:col-span-12 col-span-6 md:order-0 order-3">
					<Typography variant="bodySmall" className="text-muted-foreground">
						{countData} Task run{countData !== 1 ? "s" : ""}
					</Typography>
					{stateSummary && (
						<Typography
							variant="bodySmall"
							className="text-muted-foreground text-xs capitalize"
						>
							({stateSummary})
						</Typography>
					)}
				</div>

				{/* Controls - middle column */}
				<div className="xl:col-span-3 md:col-span-6 col-span-12 md:order-1 order-0">
					<SearchInput
						value={search}
						onChange={handleSearchChange}
						placeholder="Search by run name"
						aria-label="Search by run name"
						debounceMs={300}
					/>
				</div>
				<div className="xl:col-span-2 md:col-span-6 col-span-12 md:order-2 order-1">
					<TaskRunStateFilter
						selectedFilters={stateFilter}
						onSelectFilter={handleStateFilterChange}
					/>
				</div>
				<div className="xl:col-span-2 md:col-span-6 col-span-12 md:order-3 order-2">
					<TagsInput
						value={Array.from(tagsFilter)}
						onChange={handleTagsFilterChange}
						placeholder="All tags"
					/>
				</div>
				{/* Sort - last column with left border on desktop */}
				<div className="xl:border-l xl:border-border xl:pl-2 xl:col-span-2 md:col-span-6 col-span-6 md:order-4 order-4">
					<TaskRunsSortFilter value={sort} onSelect={handleSortChange} />
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
