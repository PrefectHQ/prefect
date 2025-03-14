import { useSuspenseQuery } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { createFakeBlockDocument } from "@/mocks";

import {
	type BlockDocument,
	buildCountFilterBlockDocumentsQuery,
	buildListFilterBlockDocumentsQuery,
} from "./block-documents";

describe("block documents queries", () => {
	const seedBlocksData = () => [createFakeBlockDocument()];

	const mockFilterListBlocksAPI = (blocks: Array<BlockDocument>) => {
		server.use(
			http.post(buildApiUrl("/block_documents/filter"), () => {
				return HttpResponse.json(blocks);
			}),
		);
		server.use(
			http.post(buildApiUrl("/block_documents/count"), () => {
				return HttpResponse.json(blocks.length);
			}),
		);
	};

	it("is stores block documents list data", async () => {
		// ------------ Mock API requests when cache is empty
		const mockList = seedBlocksData();
		mockFilterListBlocksAPI(mockList);

		// ------------ Initialize hooks to test
		const { result } = renderHook(
			() => useSuspenseQuery(buildListFilterBlockDocumentsQuery()),
			{ wrapper: createWrapper() },
		);

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
		expect(result.current.data).toEqual(mockList);
	});

	it("is stores block documents count data", async () => {
		// ------------ Mock API requests when cache is empty
		const mockList = seedBlocksData();
		mockFilterListBlocksAPI(mockList);

		// ------------ Initialize hooks to test
		const { result } = renderHook(
			() => useSuspenseQuery(buildCountFilterBlockDocumentsQuery()),
			{ wrapper: createWrapper() },
		);

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
		expect(result.current.data).toEqual(1);
	});
});
