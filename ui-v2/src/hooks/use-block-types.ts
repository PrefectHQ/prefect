import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import {
	queryOptions,
	useQuery,
	keepPreviousData,
	type UseQueryOptions,
} from "@tanstack/react-query";

export type BlockTypeKeys = {
	all: readonly ["block-types"];
	filtered: (
		options?: components["schemas"]["BlockTypeFilter"],
	) => readonly ["block-types", "filtered", string];
	detail: (slug: string) => readonly ["block-types", "detail", string];
};

export const blockTypeKeys: BlockTypeKeys = {
	all: ["block-types"],
	filtered: (options) => [
		...blockTypeKeys.all,
		"filtered",
		JSON.stringify(options),
	],
	detail: (slug) => [...blockTypeKeys.all, "detail", slug],
};

export type BlockTypesResponse = Awaited<ReturnType<typeof getBlockTypes>>;
export type BlockTypeResponse = Awaited<ReturnType<typeof getBlockType>>;

export const getBlockTypes = async ({
	blockTypes,
	limit = 100,
	offset = 0,
}: {
	blockTypes?: components["schemas"]["BlockTypeFilter"];
	limit?: number;
	offset?: number;
} = {}) => {
	const response = await getQueryService().POST("/block_types/filter", {
		body: {
			block_types: blockTypes,
			limit,
			offset,
		},
	});
	return response.data;
};
export const getBlockType = async (slug: string) => {
	const response = await getQueryService().GET(`/block_types/slug/{slug}`, {
		params: {
			path: { slug },
		},
	});
	return response.data;
};

export const buildBlockTypesQuery = (
	params: Parameters<typeof getBlockTypes>[0] = {},
) =>
	queryOptions({
		queryKey: blockTypeKeys.filtered(params.blockTypes),
		queryFn: () => getBlockTypes(params),
		staleTime: 1000,
		placeholderData: keepPreviousData,
	});

export const buildBlockTypeQuery = (slug: string) =>
	queryOptions({
		queryKey: blockTypeKeys.detail(slug),
		queryFn: () => getBlockType(slug),
		staleTime: 1000,
	});

export const useBlockTypes = (
	params: Parameters<typeof getBlockTypes>[0] = {},
	options: Omit<
		UseQueryOptions<BlockTypesResponse>,
		"queryKey" | "queryFn"
	> = {},
) => {
	const query = useQuery({
		...buildBlockTypesQuery(params),
		...options,
	});

	return {
		blockTypes: query.data ?? [],
		isLoading: query.isLoading,
		isError: query.isError,
		error: query.error,
	};
};

export const useBlockType = (
	slug: string,
	options: Omit<
		UseQueryOptions<BlockTypeResponse>,
		"queryKey" | "queryFn"
	> = {},
) => {
	const query = useQuery({
		...buildBlockTypeQuery(slug),
		...options,
	});

	return {
		blockType: query.data,
		isLoading: query.isLoading,
		isError: query.isError,
		error: query.error,
	};
};
