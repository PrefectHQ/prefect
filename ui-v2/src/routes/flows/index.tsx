import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";
import { buildCountFlowsFilteredQuery, type Flow } from "@/api/flows";
import { getQueryService } from "@/api/service"; // Service object that makes requests to the Prefect API
import FlowsPage from "@/components/flows/flows-page";

// Route for /flows/

// This file should only contain the route definition and loader function for the /flows/ route.

// 1. searchParams defined as a zod schema, so that the search query can be validated and typechecked.
// 2. flowsQueryParams function that takes a search object and returns the queryKey and queryFn for the loader.
// 3. Route definition that uses the createFileRoute function to define the route.
//    - It passes down the result of the loader function to the FlowsTable component.

const searchParams = z
	.object({
		name: z.string().optional(),
		page: z.number().int().positive().optional().default(1),
		limit: z.number().int().positive().max(100).optional().default(10),
		tags: z.array(z.string()).optional(),
		sort: z
			.enum(["CREATED_DESC", "UPDATED_DESC", "NAME_ASC", "NAME_DESC"])
			.optional()
			.default("CREATED_DESC"),
		offset: z.number().int().min(0).optional().default(0),
	})
	.optional()
	.default({});

// Alex: check why this appears to be totally fucked.
// 1. extra keyword: ignored
// 2. think through expected behavior of bad data.

const flowsQueryParams = (search: z.infer<typeof searchParams>) => ({
	queryKey: ["flows", JSON.stringify(search)],
	queryFn: async () =>
		await getQueryService().POST("/flows/paginate", {
			body: {
				page: search.page,
				limit: search.limit,
				sort: search.sort,
				flows: { operator: "and_", name: { like_: search.name } },
			},
		}),
	staleTime: 1000, // Data will be considered stale after 1 second.
});

const FlowsRoute = () => {
	const search = Route.useSearch();
	const { data } = useSuspenseQuery(flowsQueryParams(search));
	const { data: count } = useQuery(
		buildCountFlowsFilteredQuery({
			offset: search.offset,
			sort: search.sort,
			flows: {
				operator: "and_",
				name: { like_: search.name },
			},
			limit: search.limit,
		}),
	);
	return <FlowsPage flows={data.data?.results as Flow[]} count={count ?? 0} />;
};

export const Route = createFileRoute("/flows/")({
	validateSearch: zodValidator(searchParams),
	component: FlowsRoute,
	loaderDeps: ({ search }) => search,
	loader: async ({ deps: search, context }) => {
		await context.queryClient.ensureQueryData(flowsQueryParams(search));
		void context.queryClient.ensureQueryData(
			buildCountFlowsFilteredQuery({
				offset: search.offset,
				sort: search.sort,
				flows: {
					operator: "and_",
					name: { like_: search.name },
				},
				limit: search.limit,
			}),
		);
	},
	wrapInSuspense: true,
});
