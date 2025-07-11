import { useSuspenseQuery } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import { BLOCK_SCHEMAS, createFakeBlockSchema } from "@/mocks";

import {
	type BlockSchema,
	buildGetBlockSchemaQuery,
	buildListFilterBlockSchemasQuery,
} from "./block-schemas";

describe("block schema queries", () => {
	const seedBlockTypesData = () => BLOCK_SCHEMAS;

	const mockListBlockSchemasAPI = (blockSchemas: Array<BlockSchema>) => {
		server.use(
			http.post(buildApiUrl("/block_schemas/filter"), () => {
				return HttpResponse.json(blockSchemas);
			}),
		);
	};

	const mockGetBlockSchemaAPI = (blockSchema: BlockSchema) => {
		server.use(
			http.get(buildApiUrl("/block_schemas/:id"), () => {
				return HttpResponse.json(blockSchema);
			}),
		);
	};

	it("stores block schema list data", async () => {
		// ------------ Mock API requests when cache is empty
		const mockList = seedBlockTypesData();
		mockListBlockSchemasAPI(mockList);

		// ------------ Initialize hooks to test
		const { result } = renderHook(
			() => useSuspenseQuery(buildListFilterBlockSchemasQuery()),
			{ wrapper: createWrapper() },
		);

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
		expect(result.current.data).toEqual(mockList);
	});

	it("stores block schema info by id", async () => {
		// ------------ Mock API requests when cache is empty
		const mockBlockSchema = createFakeBlockSchema();
		mockGetBlockSchemaAPI(mockBlockSchema);

		// ------------ Initialize hooks to test
		const { result } = renderHook(
			() => useSuspenseQuery(buildGetBlockSchemaQuery(mockBlockSchema.id)),
			{ wrapper: createWrapper() },
		);

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
		expect(result.current.data).toEqual(mockBlockSchema);
	});
});
