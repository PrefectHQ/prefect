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
};

export const blockTypeKeys: BlockTypeKeys = {
	all: ["block-types"],
	filtered: (options) => [
		...blockTypeKeys.all,
		"filtered",
		JSON.stringify(options),
	],
};

export type BlockTypesResponse = Awaited<ReturnType<typeof getBlockTypes>>;

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

export const buildBlockTypesQuery = (
	params: Parameters<typeof getBlockTypes>[0] = {},
) =>
	queryOptions({
		queryKey: blockTypeKeys.filtered(params.blockTypes),
		queryFn: () => getBlockTypes(params),
		staleTime: 1000,
		placeholderData: keepPreviousData,
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
