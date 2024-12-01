import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import {
	queryOptions,
	useMutation,
	useQueryClient,
	useQuery,
	useQueries,
	keepPreviousData,
	type UseQueryOptions,
} from "@tanstack/react-query";

type BlockDocumentsOptions =
	components["schemas"]["Body_read_block_documents_block_documents_filter_post"];
type BlockDocumentsCountOptions = Partial<
	Pick<
		BlockDocumentsOptions,
		"block_documents" | "block_schemas" | "block_types"
	>
>;

type BlockDocumentKeys = {
	all: readonly ["block-documents"];
	filtered: (
		options?: BlockDocumentsOptions,
	) => readonly ["block-documents", "filtered", string];
	detail: (id: string) => readonly ["block-documents", "detail", string];
	count: (options?: BlockDocumentsCountOptions) => readonly string[];
};

const blockDocumentKeys: BlockDocumentKeys = {
	all: ["block-documents"],
	filtered: (options) => [
		...blockDocumentKeys.all,
		"filtered",
		JSON.stringify(options),
	],
	detail: (id) => [...blockDocumentKeys.all, "detail", id],
	count: (options) => {
		const key = [...blockDocumentKeys.all, "count"];
		if (options) key.push(JSON.stringify(options));
		return key;
	},
};

type BlockDocumentsResponse = Awaited<ReturnType<typeof getBlockDocuments>>;

export const getBlockDocuments = async (options: BlockDocumentsOptions) => {
	const response = await getQueryService().POST("/block_documents/filter", {
		body: options,
	});
	return response.data;
};

export const buildBlockDocumentsQuery = (params: BlockDocumentsOptions) =>
	queryOptions({
		queryKey: blockDocumentKeys.filtered(params),
		queryFn: () => getBlockDocuments(params),
		staleTime: 1000,
		placeholderData: keepPreviousData,
	});

export const useBlockDocuments = (
	params: BlockDocumentsOptions,
	options: Omit<
		UseQueryOptions<BlockDocumentsResponse>,
		"queryKey" | "queryFn"
	> = {},
) => {
	const results = useQueries({
		queries: [
			// Filtered block documents with pagination
			buildBlockDocumentsQuery(params),
			// Filtered count
			buildBlockDocumentsCountQuery(params),
			// Total count
			buildBlockDocumentsCountQuery(),
		],
		...options,
	});

	const [blockDocumentsQuery, filteredCountQuery, totalCountQuery] = results;

	return {
		// Block documents with pagination
		blockDocuments: blockDocumentsQuery.data ?? [],
		isLoadingBlockDocuments: blockDocumentsQuery.isLoading,
		isErrorBlockDocuments: blockDocumentsQuery.isError,
		errorBlockDocuments: blockDocumentsQuery.error,

		// Filtered count
		filteredCount: filteredCountQuery.data ?? 0,
		isLoadingFilteredCount: filteredCountQuery.isLoading,
		isErrorFilteredCount: filteredCountQuery.isError,

		// Total count
		totalCount: totalCountQuery?.data ?? filteredCountQuery.data ?? 0,
		isLoadingTotalCount: totalCountQuery?.isLoading ?? false,
		isErrorTotalCount: totalCountQuery?.isError ?? false,

		// Overall loading state
		isLoading: results.some((result) => result.isLoading),
		isError: results.some((result) => result.isError),
	};
};

type BlockDocumentsCountResponse = Awaited<
	ReturnType<typeof getBlockDocumentsCount>
>;

export const getBlockDocumentsCount = async (
	params: BlockDocumentsCountOptions = {},
) => {
	const response = await getQueryService().POST("/block_documents/count", {
		body: params,
	});
	return response.data;
};

export const buildBlockDocumentsCountQuery = (
	params?: BlockDocumentsCountOptions,
) =>
	queryOptions({
		queryKey: blockDocumentKeys.count(params),
		queryFn: () => getBlockDocumentsCount(params),
		staleTime: 1000,
		placeholderData: keepPreviousData,
	});

export const useBlockDocumentsCount = (
	params: BlockDocumentsOptions,
	options: Omit<
		UseQueryOptions<BlockDocumentsCountResponse>,
		"queryKey" | "queryFn"
	> = {},
) => {
	return useQuery({
		...buildBlockDocumentsCountQuery(params),
		...options,
	});
};

type BlockDocumentResponse = Awaited<ReturnType<typeof getBlockDocument>>;

const getBlockDocument = async (id: string) => {
	const response = await getQueryService().GET("/block_documents/{id}", {
		params: { path: { id } },
	});
	return response.data;
};

export const buildBlockDocumentQuery = (id: string) =>
	queryOptions({
		queryKey: blockDocumentKeys.detail(id),
		queryFn: () => getBlockDocument(id),
		staleTime: 1000,
	});

export const useBlockDocument = (
	id: string,
	options: Omit<
		UseQueryOptions<BlockDocumentResponse>,
		"queryKey" | "queryFn"
	> = {},
) => {
	return useQuery({
		...buildBlockDocumentQuery(id),
		...options,
	});
};

/**
 * Hook for deleting a block document
 *
 * @returns Mutation object for deleting a block document with loading/error states and trigger function
 */
export const useDeleteBlockDocument = () => {
	const queryClient = useQueryClient();

	const { mutate: deleteBlockDocument, ...rest } = useMutation({
		mutationFn: async (id: string) => {
			return await getQueryService().DELETE("/block_documents/{id}", {
				params: { path: { id } },
			});
		},
		onSettled: async () => {
			return await queryClient.invalidateQueries({
				queryKey: blockDocumentKeys.all,
			});
		},
	});

	return { deleteBlockDocument, ...rest };
};

/**
 * Hook for updating an existing block document
 *
 * @returns Mutation object for updating a block document with loading/error states and trigger function
 */
export const useUpdateBlockDocument = () => {
	const queryClient = useQueryClient();

	const { mutate: updateBlockDocument, ...rest } = useMutation({
		mutationFn: async ({
			id,
			blockDocument,
		}: {
			id: string;
			blockDocument: components["schemas"]["BlockDocumentUpdate"];
		}) => {
			return await getQueryService().PATCH("/block_documents/{id}", {
				params: { path: { id } },
				body: blockDocument,
			});
		},
		onSettled: async () => {
			return await queryClient.invalidateQueries({
				queryKey: blockDocumentKeys.all,
			});
		},
	});

	return { updateBlockDocument, ...rest };
};

/**
 * Hook for creating a new block document
 *
 * @returns Mutation object for creating a block document with loading/error states and trigger function
 */
export const useCreateBlockDocument = () => {
	const queryClient = useQueryClient();

	const { mutate: createBlockDocument, ...rest } = useMutation({
		mutationFn: async (
			blockDocument: components["schemas"]["BlockDocument"],
		) => {
			return await getQueryService().POST("/block_documents/", {
				body: blockDocument,
			});
		},
		onSettled: async () => {
			return await queryClient.invalidateQueries({
				queryKey: blockDocumentKeys.all,
			});
		},
	});

	return { createBlockDocument, ...rest };
};
