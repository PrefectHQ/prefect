import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import { zodSearchValidator } from "@tanstack/router-zod-adapter";
import WorkPoolPage from "@/components/work-pools/page";
import { PaginationState, OnChangeFn } from "@tanstack/react-table";
import { useCallback, useMemo } from "react";
import { useWorkPools } from "@/hooks/work-pools";

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

function WorkPoolsRoute() {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const {
		workPools,
		filteredCount: filteredWorkPoolsCount,
		totalCount: totalWorkPoolsCount,
	} = useWorkPools(search);

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
			workPools={workPools}
			filteredWorkPoolsCount={filteredWorkPoolsCount}
			totalWorkPoolsCount={totalWorkPoolsCount}
			pagination={pagination}
			onPaginationChange={onPaginationChange}
		/>
	);
}

export const Route = createFileRoute("/work-pools/")({
	validateSearch: zodSearchValidator(searchParams),
	component: WorkPoolsRoute,
	loaderDeps: ({ search }) => search,
	loader: useWorkPools.loader,
	wrapInSuspense: true,
});
