import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import { zodSearchValidator } from "@tanstack/router-zod-adapter";
import { useListBlockDocuments, buildListBlockDocumentsQuery } from "@/hooks/block-documents";
import { BlocksLayout } from "@/components/blocks/layout";
import { BlocksDataTable } from "@/components/blocks/data-table/data-table";
import { useCallback, useMemo } from "react";
import type { PaginationState } from "@tanstack/react-table";

const searchParams = z.object({
	offset: z.number().int().nonnegative().optional().default(0).catch(0),
	limit: z.number().int().positive().optional().default(10).catch(10),
});

/**
 * Builds a filter body for the blocks API based on search parameters.
 * @param search - Optional search parameters containing offset and limit
 * @returns An object containing pagination parameters and block filters that can be passed to the blocks API
 */
const buildFilterBody = (search: z.infer<typeof searchParams>) => ({
	block_documents: { operator: "and_" as const, is_anonymous: { eq_: false } },
	include_secrets: false,
	sort: null,
	offset: search.offset,
	limit: search.limit,
});

/**
 * Hook to manage pagination state and navigation for blocks table
 */
const usePagination = () => {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const pageIndex = Math.ceil(search.offset / search.limit);
	const pageSize = search.limit;
	const pagination: PaginationState = useMemo(
		() => ({
			pageIndex,
			pageSize,
		}),
		[pageIndex, pageSize],
	);

	const onPaginationChange = useCallback(
		(newPagination: PaginationState) => {
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
		[navigate],
	);

	return [pagination, onPaginationChange] as const;
};

function BlocksPage() {
	const search = Route.useSearch();
	const [pagination, onPaginationChange] = usePagination();
	const { data: blockDocuments } = useListBlockDocuments(buildFilterBody(search));

	return (
		<BlocksLayout>
			<BlocksDataTable
				blocks={blockDocuments ?? []}
				currentBlockCount={10}
				pagination={pagination}
				onPaginationChange={onPaginationChange}
			/>
		</BlocksLayout>
	);
}

export const Route = createFileRoute("/blocks")({
	validateSearch: zodSearchValidator(searchParams),
	component: BlocksPage,
	loaderDeps: ({ search }) => buildFilterBody(search),
	loader: ({ context: { queryClient }, deps }) => {
		return queryClient.ensureQueryData(buildListBlockDocumentsQuery(deps));
	},
	wrapInSuspense: true,
});
