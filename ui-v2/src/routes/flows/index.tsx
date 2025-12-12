import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import type {
	ColumnFiltersState,
	PaginationState,
} from "@tanstack/react-table";
import { zodValidator } from "@tanstack/zod-adapter";
import { useCallback, useMemo } from "react";
import { z } from "zod";
import {
	buildCountFlowsFilteredQuery,
	buildPaginateFlowsQuery,
	type FlowsPaginateFilter,
} from "@/api/flows";
import FlowsPage from "@/components/flows/flows-page";

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

export const Route = createFileRoute("/flows/")({
	validateSearch: zodValidator(searchParams),
	component: FlowsRoute,
	loaderDeps: ({ search }) => buildPaginationBody(search),
	loader: ({ deps, context }) => {
		// Prefetch all queries without blocking the loader
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

	// Use useQuery for paginated flows to leverage placeholderData: keepPreviousData
	// This prevents the page from suspending when search/filter changes
	const { data: flowsPage } = useQuery(
		buildPaginateFlowsQuery(paginationBody, 30_000),
	);

	const flows = flowsPage?.results ?? [];

	return (
		<FlowsPage
			flows={flows}
			count={count ?? 0}
			pageCount={flowsPage?.pages ?? 0}
			sort={sort as "NAME_ASC" | "NAME_DESC" | "CREATED_DESC"}
			pagination={pagination}
			onPaginationChange={onPaginationChange}
			onSortChange={onSortChange}
			columnFilters={columnFilters}
			onColumnFiltersChange={onColumnFiltersChange}
		/>
	);
}
