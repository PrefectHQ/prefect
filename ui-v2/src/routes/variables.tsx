import { createQueryService } from "@/api/service";
import { useSuspenseQuery } from "@tanstack/react-query";
import { VariablesPage } from "@/components/variables/page";
import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import { zodSearchValidator } from "@tanstack/router-zod-adapter";

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
		const response = await createQueryService().POST("/variables/filter", {
			body: search,
		});
		return response.data;
	},
	staleTime: 1000,
});

function VariablesRoute() {
	const search = Route.useSearch();
	const { data: variables } = useSuspenseQuery(buildVariablesQuery(search));
	const { data: totalVariableCount } = useSuspenseQuery({
		queryKey: ["total-variable-count"],
		queryFn: async () => {
			const response = await createQueryService().POST("/variables/count", {});
			return response.data;
		},
	});
	const pageIndex = search.offset ? search.offset / search.limit : 0;
	const pageSize = search.limit ?? 10;
	return (
		<VariablesPage
			variables={variables ?? []}
			totalVariableCount={totalVariableCount ?? 0}
			pagination={{
				pageIndex,
				pageSize,
			}}
		/>
	);
}

export const Route = createFileRoute("/variables")({
	validateSearch: zodSearchValidator(searchParams),
	component: VariablesRoute,
	loaderDeps: ({ search }) => search,
	loader: async ({ deps: search, context }) =>
		await context.queryClient.ensureQueryData(buildVariablesQuery(search)),
	wrapInSuspense: true,
});
