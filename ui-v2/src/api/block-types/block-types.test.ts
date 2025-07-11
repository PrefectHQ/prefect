import { useSuspenseQuery } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import { createFakeBlockType } from "@/mocks";

import {
	type BlockType,
	buildGetBlockTypeQuery,
	buildListFilterBlockTypesQuery,
} from "./block-types";

describe("block types queries", () => {
	const seedBlockTypesData = () => [createFakeBlockType()];

	const mockFilterBlocksTypesAPI = (blockTypes: Array<BlockType>) => {
		server.use(
			http.post(buildApiUrl("/block_types/filter"), () => {
				return HttpResponse.json(blockTypes);
			}),
		);
	};

	const mockGetBlockTypeBySlugAPI = (blockType: BlockType) => {
		server.use(
			http.get(buildApiUrl("/block_types/slug/:slug"), () => {
				return HttpResponse.json(blockType);
			}),
		);
	};

	it("stores block types list data", async () => {
		// ------------ Mock API requests when cache is empty
		const mockList = seedBlockTypesData();
		mockFilterBlocksTypesAPI(mockList);

		// ------------ Initialize hooks to test
		const { result } = renderHook(
			() => useSuspenseQuery(buildListFilterBlockTypesQuery()),
			{ wrapper: createWrapper() },
		);

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
		expect(result.current.data).toEqual(mockList);
	});

	it("stores block type info by slug", async () => {
		// ------------ Mock API requests when cache is empty
		const mockBlockType = createFakeBlockType();
		mockGetBlockTypeBySlugAPI(mockBlockType);

		// ------------ Initialize hooks to test
		const { result } = renderHook(
			() => useSuspenseQuery(buildGetBlockTypeQuery(mockBlockType.slug)),
			{ wrapper: createWrapper() },
		);

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
		expect(result.current.data).toEqual(mockBlockType);
	});
});
