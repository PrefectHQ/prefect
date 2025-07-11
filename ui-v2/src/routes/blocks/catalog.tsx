import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { useCallback, useMemo } from "react";
import { z } from "zod";
import { buildListFilterBlockTypesQuery } from "@/api/block-types";
import { BlocksCatalogPage } from "@/components/blocks/blocks-catalog-page/blocks-catalog-page";

const searchParams = z.object({
	blockName: z.string().optional(),
});

export const Route = createFileRoute("/blocks/catalog")({
	validateSearch: zodValidator(searchParams),
	component: RouteComponent,
	loaderDeps: ({ search: { blockName } }) => ({
		blockName,
	}),
	loader: ({ deps, context: { queryClient } }) => {
		return queryClient.ensureQueryData(
			buildListFilterBlockTypesQuery({
				block_types: { name: { like_: deps.blockName } },
				offset: 0,
			}),
		);
	},
	wrapInSuspense: true,
});

function RouteComponent() {
	const [search, onSearch] = useSearch();
	const { data: blockTypes } = useSuspenseQuery(
		buildListFilterBlockTypesQuery({
			block_types: { name: { like_: search } },
			offset: 0,
		}),
	);

	return (
		<BlocksCatalogPage
			blockTypes={blockTypes}
			search={search}
			onSearch={onSearch}
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
