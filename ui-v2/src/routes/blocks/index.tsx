import {
	type BlockDocumentsFilter,
	buildCountAllBlockDocumentsQuery,
	buildCountFilterBlockDocumentsQuery,
	buildListFilterBlockDocumentsQuery,
} from "@/api/block-documents";
import { buildListFilterBlockTypesQuery } from "@/api/block-types";
import { BlocksPage } from "@/components/blocks/blocks-page";
import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { useCallback, useMemo } from "react";
import { z } from "zod";

const searchParams = z.object({
	blockName: z.string().optional(),
	blockTypes: z.object({ slug: z.array(z.string()) }).optional(),
	page: z.number().int().positive().optional().default(1).catch(1),
	limit: z.number().int().positive().optional().default(10).catch(10),
});

export const Route = createFileRoute("/blocks/")({
	validateSearch: zodValidator(searchParams),
	component: RouteComponent,
	loaderDeps: ({ search: { blockName, blockTypes, page, limit } }) => ({
		blockName,
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
				name: { like_: deps.blockName },
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

function RouteComponent() {
	const [search, onSearch] = useSearch();

	const { data: allBlockDocumentsCount } = useSuspenseQuery(
		buildCountAllBlockDocumentsQuery(),
	);

	const { data: blockDocuments } = useQuery(
		buildListFilterBlockDocumentsQuery({
			sort: "BLOCK_TYPE_AND_NAME_ASC",
			include_secrets: false,
			block_documents: {
				name: { like_: search },
				operator: "and_",
				is_anonymous: { eq_: false },
			},
			// TODO
			offset: 0,
		}),
	);

	return (
		<BlocksPage
			allCount={allBlockDocumentsCount}
			blockDocuments={blockDocuments}
			onSearch={onSearch}
			search={search}
		/>
	);
}

function useSearch() {
	const { blockName } = Route.useSearch();
	const navigate = Route.useNavigate();

	const onSearch = useCallback(
		(value?: string) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					blockName: value,
				}),
				replace: true,
			});
		},
		[navigate],
	);
	const search = useMemo(() => blockName ?? "", [blockName]);
	return [search, onSearch] as const;
}
