import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import type { PaginationState } from "@tanstack/react-table";
import { zodValidator } from "@tanstack/zod-adapter";
import { useCallback, useMemo } from "react";
import { z } from "zod";
import {
	type BlockDocumentsFilter,
	buildCountAllBlockDocumentsQuery,
	buildCountFilterBlockDocumentsQuery,
	buildListFilterBlockDocumentsQuery,
} from "@/api/block-documents";
import { buildListFilterBlockTypesQuery } from "@/api/block-types";
import { BlocksPage } from "@/components/blocks/blocks-page";
import { Skeleton } from "@/components/ui/skeleton";
import { usePageTitle } from "@/hooks/use-page-title";

/**
 * Skeleton component shown while the blocks page is loading.
 * Displays placeholder elements for header, filter bar, and table rows.
 */
const blocksPageSkeleton = () => {
	return (
		<div className="flex flex-col gap-4">
			{/* Header skeleton */}
			<Skeleton className="h-8 w-20" />
			{/* Filter bar skeleton */}
			<div className="flex flex-wrap gap-2">
				<Skeleton className="h-9 w-full" />
				<Skeleton className="h-9 w-48" />
			</div>
			{/* Table skeleton */}
			<div className="rounded-md border">
				<div className="flex flex-col divide-y">
					{Array.from({ length: 8 }).map((_, i) => (
						<div
							key={`block-skeleton-${String(i)}`}
							className="flex items-center gap-4 px-4 py-3"
						>
							<Skeleton className="h-10 w-10 rounded-md" />
							<Skeleton className="h-4 w-40" />
							<Skeleton className="h-4 w-24" />
						</div>
					))}
				</div>
			</div>
		</div>
	);
};

const searchParams = z.object({
	blockName: z.string().optional(),
	blockTypes: z.array(z.string()).optional(),
	page: z.number().int().positive().optional().default(1).catch(1),
	limit: z.number().int().positive().optional().default(10).catch(10),
});

export const Route = createFileRoute("/blocks/")({
	validateSearch: zodValidator(searchParams),
	component: function RouteComponent() {
		usePageTitle("Blocks");
		const [search, onSearch] = useSearch();
		const [blockTypeSlugs, onSetBlockTypeSlugs] = useFilterByBlockTypes();
		const [pagination, onPaginationChange] = usePagination();

		const { data: allBlockDocumentsCount } = useSuspenseQuery(
			buildCountAllBlockDocumentsQuery(),
		);

		const { data: blockDocuments } = useQuery(
			buildListFilterBlockDocumentsQuery({
				sort: "NAME_ASC",
				include_secrets: false,
				block_documents: {
					name: { like_: search },
					operator: "and_",
					is_anonymous: { eq_: false },
				},
				block_types: {
					slug: {
						any_: blockTypeSlugs.length > 0 ? blockTypeSlugs : undefined,
					},
				},
				offset: pagination.pageIndex * pagination.pageSize,
				limit: pagination.pageSize,
			}),
		);

		const handleRemoveBlockType = (id: string) => {
			const newValue = blockTypeSlugs.filter((blockId) => blockId !== id);
			onSetBlockTypeSlugs(newValue);
		};

		const handleToggleBlockType = (id: string) => {
			// Remove block id if its in the list
			if (blockTypeSlugs.includes(id)) {
				return handleRemoveBlockType(id);
			}
			// Else add it to the list
			onSetBlockTypeSlugs([...blockTypeSlugs, id]);
		};

		return (
			<BlocksPage
				allCount={allBlockDocumentsCount}
				blockDocuments={blockDocuments}
				onSearch={onSearch}
				search={search}
				blockTypeSlugsFilter={blockTypeSlugs}
				onRemoveBlockTypeSlug={handleRemoveBlockType}
				onToggleBlockTypeSlug={handleToggleBlockType}
				pagination={pagination}
				onPaginationChange={onPaginationChange}
			/>
		);
	},
	loaderDeps: ({ search: { blockName, blockTypes, page, limit } }) => ({
		blockName,
		blockTypes,
		page,
		limit,
	}),
	loader: ({ deps, context: { queryClient } }) => {
		// ----- Critical data
		const filter: BlockDocumentsFilter = {
			block_types: { slug: { any_: deps.blockTypes } },
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
	pendingComponent: blocksPageSkeleton,
});

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

function useFilterByBlockTypes() {
	const { blockTypes = [] } = Route.useSearch();
	const navigate = Route.useNavigate();

	const onSetBlockTypes = useCallback(
		(value?: Array<string>) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					blockTypes: value,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	return [blockTypes, onSetBlockTypes] as const;
}

function usePagination() {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	// React Table uses 0-based pagination, so we need to subtract 1 from the page number
	const pageIndex = (search.page ?? 1) - 1;
	const pageSize = search.limit ?? 10;
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
					page: newPagination.pageIndex + 1,
					limit: newPagination.pageSize,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	return [pagination, onPaginationChange] as const;
}
