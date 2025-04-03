import {
	type BlockDocumentsFilter,
	buildCountAllBlockDocumentsQuery,
	buildCountFilterBlockDocumentsQuery,
	buildListFilterBlockDocumentsQuery,
} from "@/api/block-documents";
import { buildListFilterBlockTypesQuery } from "@/api/block-types";
import { BlocksPage } from "@/components/blocks/blocks-page";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";

const searchParams = z.object({
	blockDocuments: z.object({ name: z.string() }).optional(),
	blockTypes: z.object({ slug: z.array(z.string()) }).optional(),
	page: z.number().int().positive().optional().default(1).catch(1),
	limit: z.number().int().positive().optional().default(10).catch(10),
});

export const Route = createFileRoute("/blocks/")({
	validateSearch: zodValidator(searchParams),
	component: BlocksPage,
	loaderDeps: ({ search: { blockDocuments, blockTypes, page, limit } }) => ({
		blockDocuments,
		blockTypes,
		page,
		limit,
	}),
	loader: ({ deps, context: { queryClient } }) => {
		// ----- Critical data
		const filter: BlockDocumentsFilter = {
			block_types: { slug: { any_: deps.blockTypes?.slug } },
			block_documents: {
				is_anonymous: { eq_: false },
				operator: "or_",
				name: { like_: deps.blockDocuments?.name },
			},
			limit: deps.limit,
			offset: deps.page,
			include_secrets: false,
			sort: "NAME_ASC",
		};
		return Promise.all([
			queryClient.ensureQueryData(buildListFilterBlockTypesQuery()),
			// All count query
			queryClient.ensureQueryData(buildCountAllBlockDocumentsQuery()),
			// Filtered block document
			queryClient.ensureQueryData(buildListFilterBlockDocumentsQuery(filter)),
			// Filtered count query
			queryClient.ensureQueryData(buildCountFilterBlockDocumentsQuery(filter)),
		]);
	},
	wrapInSuspense: true,
});
