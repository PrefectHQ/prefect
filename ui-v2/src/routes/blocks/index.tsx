import { createFileRoute, Link } from "@tanstack/react-router";
import { z } from "zod";
import { zodSearchValidator } from "@tanstack/router-zod-adapter";
import {
	useBlockDocuments,
	buildBlockDocumentsQuery,
	buildBlockDocumentsCountQuery,
} from "@/hooks/use-block-documents";
import { components } from "@/api/prefect";

const searchParams = z.object({
	offset: z.number().int().nonnegative().optional().default(0).catch(0),
	limit: z.number().int().positive().optional().default(10).catch(10),
	sort: z
		.enum(["NAME_ASC", "NAME_DESC"])
		.optional()
		.default("NAME_ASC")
		.catch("NAME_ASC"),
	name: z.string().optional().catch(undefined),
	isAnonymous: z.boolean().optional().default(false),
});

function BlocksPage() {
	const search = Route.useSearch();

	const { blockDocuments: blocks } = useBlockDocuments(buildFilterBody(search));

	return (
		<div>
			{blocks.map((block) => (
				<div key={block.id ?? "unknown"}>
					{block.id ? (
						<Link to="/blocks/$id" params={{ id: block.id }}>
							{block.name}
						</Link>
					) : (
						<span>{block.name}</span>
					)}
				</div>
			))}
		</div>
	);
}

/**
 * Builds a filter body for the blocks API based on search parameters.
 * @param search - Optional search parameters containing offset, limit, sort, name filter, and isAnonymous filter
 * @returns An object containing pagination parameters and block document filters that can be passed to the blocks API
 */
const buildFilterBody = (
	search: z.infer<typeof searchParams> = searchParams.parse({}),
): components["schemas"]["Body_read_block_documents_block_documents_filter_post"] => ({
	offset: search.offset,
	limit: search.limit,
	block_documents: {
		operator: "and_",
		name: { like_: search.name },
		is_anonymous: { eq_: search.isAnonymous },
	},
	sort: search.sort,
	include_secrets: false,
})

export const Route = createFileRoute("/blocks/")({
	validateSearch: zodSearchValidator(searchParams),
	component: BlocksPage,
	loaderDeps: ({ search }) => buildFilterBody(search),
	loader: ({ deps, context }) => {
		return Promise.all([
			context.queryClient.ensureQueryData(buildBlockDocumentsQuery(deps)),
			context.queryClient.ensureQueryData(buildBlockDocumentsCountQuery(deps)),
			context.queryClient.ensureQueryData(buildBlockDocumentsCountQuery()),
		]);
	},
	wrapInSuspense: true,
});
