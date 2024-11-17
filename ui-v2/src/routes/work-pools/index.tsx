import { getQueryService } from "@/api/service";
import { keepPreviousData, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import { zodSearchValidator } from "@tanstack/router-zod-adapter";
import WorkPoolPage from "@/components/work-pools/page";
import { PaginationState, OnChangeFn } from "@tanstack/react-table";
import { useCallback, useMemo } from "react";

const searchParams = z.object({
	offset: z.number().int().nonnegative().optional().default(0),
	limit: z.number().int().positive().optional().default(10),
	sort: z
		.enum(["CREATED_DESC", "UPDATED_DESC", "NAME_ASC", "NAME_DESC"])
		.optional()
		.default("CREATED_DESC"),
	name: z.string().optional(),
	type: z.string().optional(),
});

const buildWorkPoolsQuery = (search: z.infer<typeof searchParams>) => ({
	queryKey: ["work-pools", JSON.stringify(search)],
	queryFn: async () => {
		const response = await getQueryService().POST("/work_pools/filter");
		return response.data;
	},
	staleTime: 1000,
	placeholderData: keepPreviousData,
});

const buildTotalWorkPoolCountQuery = (
	search?: z.infer<typeof searchParams>,
) => ({
	queryKey: ["work-pool-count", JSON.stringify(search)],
	queryFn: async () => {
		const response = await getQueryService().POST("/work_pools/count");
		return response.data;
	},
	staleTime: 1000,
	placeholderData: keepPreviousData,
});

function WorkPoolsRoute() {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const { data: workPools } = useSuspenseQuery(buildWorkPoolsQuery(search));
	const { data: filteredWorkPoolsCount } = useSuspenseQuery(
		buildTotalWorkPoolCountQuery(search),
	);
	const { data: totalWorkPoolsCount } = useSuspenseQuery(
		buildTotalWorkPoolCountQuery(),
	);

	const pageIndex = search.offset ? search.offset / search.limit : 0;
	const pageSize = search.limit ?? 10;
	const pagination: PaginationState = useMemo(
		() => ({
			pageIndex,
			pageSize,
		}),
		[pageIndex, pageSize],
	);

	const onPaginationChange: OnChangeFn<PaginationState> = useCallback(
		(updater) => {
			let newPagination = pagination;
			if (typeof updater === "function") {
				newPagination = updater(pagination);
			} else {
				newPagination = updater;
			}
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					offset: newPagination.pageIndex * newPagination.pageSize,
					limit: newPagination.pageSize,
				}),
				replace: true,
			});
		},
		[pagination, navigate],
	);

	return (
		<WorkPoolPage
			workPools={workPools ?? []}
			filteredWorkPoolsCount={filteredWorkPoolsCount ?? 0}
			totalWorkPoolsCount={totalWorkPoolsCount ?? 0}
			pagination={pagination}
			onPaginationChange={onPaginationChange}
		/>
	);
}

export const Route = createFileRoute("/work-pools/")({
	validateSearch: zodSearchValidator(searchParams),
	component: WorkPoolsRoute,
	loaderDeps: ({ search }) => search,
	loader: ({ deps: search, context }) =>
		Promise.all([
			context.queryClient.ensureQueryData(buildWorkPoolsQuery(search)),
			context.queryClient.ensureQueryData(buildTotalWorkPoolCountQuery(search)),
			context.queryClient.ensureQueryData(buildTotalWorkPoolCountQuery()),
		]),
	wrapInSuspense: true,
});