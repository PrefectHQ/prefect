import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { useCallback, useMemo } from "react";
import { z } from "zod";
import {
	buildCountFlowsFilteredQuery,
	buildPaginateFlowsQuery,
	type FlowsPaginateFilter,
} from "@/api/flows";
import type { PaginationState } from "@/components/flow-runs/flow-runs-list";
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
	return {
		page: search?.page ?? 1,
		limit: search?.limit ?? 10,
		sort: search?.sort ?? "NAME_ASC",
		flows: search?.name
			? { operator: "and_", name: { like_: search.name } }
			: undefined,
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

function FlowsRoute() {
	const search = Route.useSearch();
	const [pagination, onPaginationChange] = usePagination();

	// Use useSuspenseQuery for count (stable key, won't cause suspense on search change)
	const { data: count } = useSuspenseQuery(
		buildCountFlowsFilteredQuery({
			offset: 0,
			sort: search.sort,
			flows: search.name
				? { operator: "and_", name: { like_: search.name } }
				: undefined,
		}),
	);

	// Use useQuery for paginated flows to leverage placeholderData: keepPreviousData
	// This prevents the page from suspending when search/filter changes
	const { data: flowsPage } = useQuery(
		buildPaginateFlowsQuery(buildPaginationBody(search), 30_000),
	);

	const flows = flowsPage?.results ?? [];

	return (
		<FlowsPage
			flows={flows}
			count={count ?? 0}
			pages={flowsPage?.pages ?? 0}
			sort={search.sort as "NAME_ASC" | "NAME_DESC" | "CREATED_DESC"}
			pagination={pagination}
			onPaginationChange={onPaginationChange}
		/>
	);
}
