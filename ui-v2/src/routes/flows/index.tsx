import {
	useQuery,
	useQueryClient,
	useSuspenseQuery,
} from "@tanstack/react-query";
import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import type {
	ColumnFiltersState,
	PaginationState,
} from "@tanstack/react-table";
import { zodValidator } from "@tanstack/zod-adapter";
import { useCallback, useMemo } from "react";
import { z } from "zod";
import { categorizeError } from "@/api/error-utils";
import { buildFilterFlowRunsQuery } from "@/api/flow-runs";
import {
	buildCountFlowsFilteredQuery,
	buildDeploymentsCountByFlowQuery,
	buildNextRunsByFlowQuery,
	buildPaginateFlowsQuery,
	type FlowsPaginateFilter,
} from "@/api/flows";
import FlowsPage from "@/components/flows/flows-page";
import { RouteErrorState } from "@/components/ui/route-error-state";

// Route for /flows/

const searchParams = z
	.object({
		name: z.string().optional(),
		page: z.number().int().positive().optional().default(1).catch(1),
		limit: z
			.number()
			.int()
			.positive()
			.max(100)
			.optional()
			.default(10)
			.catch(10),
		tags: z.array(z.string()).optional(),
		sort: z
			.enum(["CREATED_DESC", "UPDATED_DESC", "NAME_ASC", "NAME_DESC"])
			.optional()
			.default("NAME_ASC"),
	})
	.optional()
	.default({});

type SearchParams = z.infer<typeof searchParams>;

const buildPaginationBody = (search?: SearchParams): FlowsPaginateFilter => {
	const hasNameFilter = Boolean(search?.name);
	const hasTagsFilter = Boolean(search?.tags?.length);

	if (!hasNameFilter && !hasTagsFilter) {
		return {
			page: search?.page ?? 1,
			limit: search?.limit ?? 10,
			sort: search?.sort ?? "NAME_ASC",
		};
	}

	return {
		page: search?.page ?? 1,
		limit: search?.limit ?? 10,
		sort: search?.sort ?? "NAME_ASC",
		flows: {
			operator: "and_",
			...(hasNameFilter && { name: { like_: search?.name } }),
			...(hasTagsFilter && {
				tags: { operator: "and_", all_: search?.tags },
			}),
		},
	};
};

const NUMBER_OF_ACTIVITY_BARS = 16;

function FlowsErrorComponent({ error, reset }: ErrorComponentProps) {
	const serverError = categorizeError(error, "Failed to load flows");

	// Only handle API errors (server-error, client-error) at route level
	// Let network errors and unknown errors bubble up to root error component
	if (
		serverError.type !== "server-error" &&
		serverError.type !== "client-error"
	) {
		throw error;
	}

	return (
		<div className="flex flex-col gap-4">
			<div>
				<h1 className="text-2xl font-semibold">Flows</h1>
			</div>
			<RouteErrorState error={serverError} onRetry={reset} />
		</div>
	);
}

export const Route = createFileRoute("/flows/")({
	validateSearch: zodValidator(searchParams),
	component: FlowsRoute,
	errorComponent: FlowsErrorComponent,
	loaderDeps: ({ search }) => buildPaginationBody(search),
	loader: ({ deps, context }) => {
		// Prefetch current page queries without blocking the loader
		void context.queryClient.prefetchQuery(
			buildPaginateFlowsQuery(deps, 30_000),
		);
		void context.queryClient.prefetchQuery(
			buildCountFlowsFilteredQuery({
				offset: 0,
				sort: deps.sort,
				flows: deps.flows ?? undefined,
			}),
		);
		// Prefetch total count for empty state check
		void context.queryClient.prefetchQuery(
			buildCountFlowsFilteredQuery({
				offset: 0,
				sort: "NAME_ASC",
			}),
		);
	},
	wrapInSuspense: true,
});

const usePagination = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	// Convert URL params (1-based page) to TanStack Table's PaginationState (0-based pageIndex)
	const pagination: PaginationState = useMemo(
		() => ({
			pageIndex: (search.page ?? 1) - 1,
			pageSize: search.limit ?? 10,
		}),
		[search.page, search.limit],
	);

	const onPaginationChange = useCallback(
		(newPagination: PaginationState) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					// Convert TanStack Table's 0-based pageIndex back to 1-based page for URL
					page: newPagination.pageIndex + 1,
					limit: newPagination.pageSize,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	return [pagination, onPaginationChange] as const;
};

type FlowSort = "CREATED_DESC" | "UPDATED_DESC" | "NAME_ASC" | "NAME_DESC";

const useSort = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const onSortChange = useCallback(
		(sort: FlowSort) => {
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

const useFlowsColumnFilters = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();
	const columnFilters: ColumnFiltersState = useMemo(
		() => [
			{ id: "name", value: search.name },
			{ id: "tags", value: search.tags },
		],
		[search.name, search.tags],
	);

	const onColumnFiltersChange = useCallback(
		(newColumnFilters: ColumnFiltersState) => {
			void navigate({
				to: ".",
				search: (prev) => {
					const name = newColumnFilters.find((filter) => filter.id === "name")
						?.value as string | undefined;
					const tags = newColumnFilters.find((filter) => filter.id === "tags")
						?.value as string[] | undefined;
					return {
						...prev,
						page: 1,
						name,
						tags,
					};
				},
				replace: true,
			});
		},
		[navigate],
	);

	return [columnFilters, onColumnFiltersChange] as const;
};

function FlowsRoute() {
	const search = Route.useSearch();
	const queryClient = useQueryClient();
	const [pagination, onPaginationChange] = usePagination();
	const [sort, onSortChange] = useSort();
	const [columnFilters, onColumnFiltersChange] = useFlowsColumnFilters();

	const paginationBody = buildPaginationBody(search);

	// Use useSuspenseQuery for count (stable key, won't cause suspense on search change)
	const { data: count } = useSuspenseQuery(
		buildCountFlowsFilteredQuery({
			offset: 0,
			sort: search.sort,
			flows: paginationBody.flows ?? undefined,
		}),
	);

	// Get total count of all flows (without filters) to determine if empty state should be shown
	const { data: totalCount } = useSuspenseQuery(
		buildCountFlowsFilteredQuery({
			offset: 0,
			sort: "NAME_ASC",
		}),
	);

	// Use useQuery for paginated flows to leverage placeholderData: keepPreviousData
	// This prevents the page from suspending when search/filter changes
	const { data: flowsPage } = useQuery(
		buildPaginateFlowsQuery(paginationBody, 30_000),
	);

	const flows = flowsPage?.results ?? [];

	// Prefetch a page and its child component data when user hovers over pagination buttons
	const onPrefetchPage = useCallback(
		(page: number) => {
			const pageDeps = { ...paginationBody, page };
			void queryClient
				.prefetchQuery(buildPaginateFlowsQuery(pageDeps, 30_000))
				.then(() => {
					// Get the prefetched page data from cache
					const pageData = queryClient.getQueryData<{
						results?: Array<{ id?: string }>;
					}>(buildPaginateFlowsQuery(pageDeps, 30_000).queryKey);

					const flowIds =
						pageData?.results
							?.map((flow) => flow.id)
							.filter((id): id is string => Boolean(id)) ?? [];

					if (flowIds.length === 0) return;

					// Prefetch child component queries for each flow individually
					// Using individual flow IDs ensures query keys match what components use
					for (const flowId of flowIds) {
						// FlowNextRun query - uses single flow ID array for query key matching
						void queryClient.prefetchQuery(buildNextRunsByFlowQuery([flowId]));

						// FlowDeploymentCount query - uses single flow ID array for query key matching
						void queryClient.prefetchQuery(
							buildDeploymentsCountByFlowQuery([flowId]),
						);
						// FlowLastRun query - last completed run
						void queryClient.prefetchQuery(
							buildFilterFlowRunsQuery({
								flows: { operator: "and_", id: { any_: [flowId] } },
								flow_runs: {
									operator: "and_",
									start_time: { is_null_: false },
								},
								offset: 0,
								limit: 1,
								sort: "START_TIME_DESC",
							}),
						);

						// FlowActivity query - recent runs for activity chart
						void queryClient.prefetchQuery(
							buildFilterFlowRunsQuery({
								flows: { operator: "and_", id: { any_: [flowId] } },
								flow_runs: {
									operator: "and_",
									start_time: { is_null_: false },
								},
								offset: 0,
								limit: NUMBER_OF_ACTIVITY_BARS,
								sort: "START_TIME_DESC",
							}),
						);
					}
				});
		},
		[queryClient, paginationBody],
	);

	return (
		<FlowsPage
			flows={flows}
			count={count ?? 0}
			totalCount={totalCount ?? 0}
			pageCount={flowsPage?.pages ?? 0}
			sort={sort as "NAME_ASC" | "NAME_DESC" | "CREATED_DESC"}
			pagination={pagination}
			onPaginationChange={onPaginationChange}
			onSortChange={onSortChange}
			columnFilters={columnFilters}
			onColumnFiltersChange={onColumnFiltersChange}
			onPrefetchPage={onPrefetchPage}
		/>
	);
}
