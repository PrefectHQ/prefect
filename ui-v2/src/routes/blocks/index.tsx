import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import type { PaginationState } from "@tanstack/react-table";
import { zodValidator } from "@tanstack/zod-adapter";
import { useCallback, useMemo } from "react";
import { toast } from "sonner";
import { z } from "zod";
import {
	buildGetDefaultResultStorageQuery,
	useClearDefaultResultStorage,
	useUpdateDefaultResultStorage,
} from "@/api/admin";
import {
	type BlockDocumentsFilter,
	buildCountAllBlockDocumentsQuery,
	buildCountFilterBlockDocumentsQuery,
	buildGetBlockDocumentQuery,
	buildListFilterBlockDocumentsQuery,
} from "@/api/block-documents";
import { buildListFilterBlockTypesQuery } from "@/api/block-types";
import { categorizeError } from "@/api/error-utils";
import { BlocksPage } from "@/components/blocks/blocks-page";
import { PrefectLoading } from "@/components/ui/loading";
import { RouteErrorState } from "@/components/ui/route-error-state";
import { usePageTitle } from "@/hooks/use-page-title";

const searchParams = z.object({
	blockName: z.string().optional(),
	blockTypes: z.array(z.string()).optional(),
	page: z.number().int().positive().optional().default(1).catch(1),
	limit: z.number().int().positive().optional().default(10).catch(10),
});

const storageBlockDocumentsFilter = {
	sort: "BLOCK_TYPE_AND_NAME_ASC",
	include_secrets: false,
	offset: 0,
	limit: 200,
	block_documents: {
		operator: "and_",
		is_anonymous: { eq_: false },
	},
	block_schemas: {
		operator: "and_",
		block_capabilities: { all_: ["write-path"] },
	},
} satisfies BlockDocumentsFilter;

export const Route = createFileRoute("/blocks/")({
	validateSearch: zodValidator(searchParams),
	component: function RouteComponent() {
		usePageTitle("Blocks");
		const navigate = Route.useNavigate();
		const [search, onSearch] = useSearch();
		const [blockTypeSlugs, onSetBlockTypeSlugs] = useFilterByBlockTypes();
		const [pagination, onPaginationChange] = usePagination();

		const { data: allBlockDocumentsCount } = useSuspenseQuery(
			buildCountAllBlockDocumentsQuery(),
		);
		const { data: defaultResultStorage } = useSuspenseQuery(
			buildGetDefaultResultStorageQuery(),
		);
		const defaultResultStorageBlockId =
			defaultResultStorage.default_result_storage_block_id ?? undefined;

		const blockDocumentsFilter = useMemo(
			() => ({
				sort: "NAME_ASC" as const,
				include_secrets: false,
				offset: 0,
				block_documents: {
					name: { like_: search },
					operator: "and_" as const,
					is_anonymous: { eq_: false },
				},
				block_types: {
					slug: {
						any_: blockTypeSlugs.length > 0 ? blockTypeSlugs : undefined,
					},
				},
			}),
			[search, blockTypeSlugs],
		);
		const { data: blockDocuments } = useQuery(
			buildListFilterBlockDocumentsQuery({
				...blockDocumentsFilter,
				offset: pagination.pageIndex * pagination.pageSize,
				limit: pagination.pageSize,
			}),
		);

		const { data: filteredBlockDocumentsCount } = useQuery(
			buildCountFilterBlockDocumentsQuery(blockDocumentsFilter),
		);
		const {
			data: storageBlockDocuments,
			isLoading: isLoadingStorageBlockDocuments,
		} = useQuery(
			buildListFilterBlockDocumentsQuery(storageBlockDocumentsFilter),
		);
		const {
			data: defaultResultStorageBlock,
			isLoading: isLoadingDefaultResultStorageBlockDetail,
		} = useQuery({
			...buildGetBlockDocumentQuery(defaultResultStorageBlockId ?? ""),
			enabled: Boolean(defaultResultStorageBlockId),
		});
		const resolvedDefaultResultStorageBlock =
			defaultResultStorageBlock ??
			storageBlockDocuments?.find(
				(blockDocument) => blockDocument.id === defaultResultStorageBlockId,
			);
		const isLoadingDefaultResultStorageBlock =
			Boolean(defaultResultStorageBlockId) &&
			!resolvedDefaultResultStorageBlock &&
			(isLoadingDefaultResultStorageBlockDetail ||
				isLoadingStorageBlockDocuments);
		const {
			updateDefaultResultStorage,
			isPending: isUpdatingDefaultResultStorage,
		} = useUpdateDefaultResultStorage();
		const {
			clearDefaultResultStorage,
			isPending: isClearingDefaultResultStorage,
		} = useClearDefaultResultStorage();

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

		const onClearFilters = useCallback(() => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					blockName: undefined,
					blockTypes: undefined,
					page: 1,
				}),
				replace: true,
			});
		}, [navigate]);
		const handleUpdateDefaultResultStorage = useCallback(
			(blockDocumentId: string) => {
				if (blockDocumentId === defaultResultStorageBlockId) {
					return;
				}
				updateDefaultResultStorage(
					{ default_result_storage_block_id: blockDocumentId },
					{
						onSuccess: () => toast.success("Default result storage updated"),
						onError: (error) => toast.error(error.message),
					},
				);
			},
			[defaultResultStorageBlockId, updateDefaultResultStorage],
		);
		const handleClearDefaultResultStorage = useCallback(() => {
			clearDefaultResultStorage(undefined, {
				onSuccess: () => toast.success("Default result storage cleared"),
				onError: (error) => toast.error(error.message),
			});
		}, [clearDefaultResultStorage]);

		return (
			<BlocksPage
				allCount={allBlockDocumentsCount}
				filteredCount={filteredBlockDocumentsCount}
				blockDocuments={blockDocuments}
				onSearch={onSearch}
				search={search}
				blockTypeSlugsFilter={blockTypeSlugs}
				onRemoveBlockTypeSlug={handleRemoveBlockType}
				onToggleBlockTypeSlug={handleToggleBlockType}
				pagination={pagination}
				onPaginationChange={onPaginationChange}
				onClearFilters={onClearFilters}
				defaultResultStorageBlockId={defaultResultStorageBlockId}
				defaultResultStorageBlock={resolvedDefaultResultStorageBlock}
				storageBlockDocuments={storageBlockDocuments}
				onUpdateDefaultResultStorage={handleUpdateDefaultResultStorage}
				onClearDefaultResultStorage={handleClearDefaultResultStorage}
				isUpdatingDefaultResultStorage={isUpdatingDefaultResultStorage}
				isClearingDefaultResultStorage={isClearingDefaultResultStorage}
				isLoadingDefaultResultStorageBlock={isLoadingDefaultResultStorageBlock}
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
		const baseFilter: BlockDocumentsFilter = {
			block_types: { slug: { any_: deps.blockTypes } },
			block_documents: {
				is_anonymous: { eq_: false },
				operator: "and_",
				name: { like_: deps.blockName },
			},
			offset: 0,
			include_secrets: false,
			sort: "NAME_ASC",
		};
		const paginatedFilter: BlockDocumentsFilter = {
			...baseFilter,
			limit: deps.limit,
			offset: ((deps.page ?? 1) - 1) * (deps.limit ?? 10),
		};
		// Prefetch all queries without awaiting to avoid blocking render
		void queryClient.prefetchQuery(buildListFilterBlockTypesQuery());
		void queryClient.prefetchQuery(buildCountAllBlockDocumentsQuery());
		void queryClient.prefetchQuery(buildGetDefaultResultStorageQuery());
		void queryClient.prefetchQuery(
			buildListFilterBlockDocumentsQuery(storageBlockDocumentsFilter),
		);
		void queryClient.prefetchQuery(
			buildListFilterBlockDocumentsQuery(paginatedFilter),
		);
		void queryClient.prefetchQuery(
			buildCountFilterBlockDocumentsQuery(baseFilter),
		);
	},
	errorComponent: function BlocksErrorComponent({
		error,
		reset,
	}: ErrorComponentProps) {
		const serverError = categorizeError(error, "Failed to load blocks");
		if (
			serverError.type !== "server-error" &&
			serverError.type !== "client-error"
		) {
			throw error;
		}
		return (
			<div className="flex flex-col gap-4">
				<div>
					<h1 className="text-2xl font-semibold">Blocks</h1>
				</div>
				<RouteErrorState error={serverError} onRetry={reset} />
			</div>
		);
	},
	wrapInSuspense: true,
	pendingComponent: PrefectLoading,
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
					page: 1,
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
					page: 1,
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
