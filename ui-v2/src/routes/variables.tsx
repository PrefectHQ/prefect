import { getQueryService } from "@/api/service";
import { keepPreviousData, useSuspenseQuery } from "@tanstack/react-query";
import { VariablesPage } from "@/components/variables/page";
import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import { zodSearchValidator } from "@tanstack/router-zod-adapter";
import type { OnChangeFn, PaginationState } from "@tanstack/react-table";

const searchParams = z.object({
	offset: z.number().int().nonnegative().optional().default(0),
	limit: z.number().int().positive().optional().default(10),
	sort: z
		.enum(["CREATED_DESC", "UPDATED_DESC", "NAME_ASC", "NAME_DESC"])
		.optional()
		.default("CREATED_DESC"),
});

const buildVariablesQuery = (search: z.infer<typeof searchParams>) => ({
	queryKey: ["variables", JSON.stringify(search)],
	queryFn: async () => {
		const response = await getQueryService().POST("/variables/filter", {
			body: search,
		});
		return response.data;
	},
	staleTime: 1000,
	placeholderData: keepPreviousData,
});

const buildTotalVariableCountQuery = () => ({
	queryKey: ["total-variable-count"],
	queryFn: async () => {
		const response = await getQueryService().POST("/variables/count", {});
		return response.data;
	},
});

function VariablesRoute() {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const { data: variables } = useSuspenseQuery(buildVariablesQuery(search));
	const { data: totalVariableCount } = useSuspenseQuery(
		buildTotalVariableCountQuery(),
	);

	const pageIndex = search.offset ? search.offset / search.limit : 0;
	const pageSize = search.limit ?? 10;
	const pagination: PaginationState = {
		pageIndex,
		pageSize,
	};

	const onPaginationChange: OnChangeFn<PaginationState> = (updater) => {
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
	};

	return (
		<VariablesPage
			variables={variables ?? []}
			totalVariableCount={totalVariableCount ?? 0}
			pagination={pagination}
			onPaginationChange={onPaginationChange}
		/>
	);
}

export const Route = createFileRoute("/variables")({
	validateSearch: zodSearchValidator(searchParams),
	component: VariablesRoute,
	loaderDeps: ({ search }) => search,
	loader: ({ deps: search, context }) =>
		Promise.all([
			context.queryClient.ensureQueryData(buildVariablesQuery(search)),
			context.queryClient.ensureQueryData(buildTotalVariableCountQuery()),
		]),
	wrapInSuspense: true,
});
