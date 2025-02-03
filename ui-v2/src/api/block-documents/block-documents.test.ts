import { useSuspenseQuery } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { createFakeBlockDocument } from "@/mocks";

import {
	type BlockDocument,
	buildFilterBlockDocumentsQuery,
} from "./block-documents";

describe("block documents queries", () => {
	const seedBlocksData = () => [createFakeBlockDocument()];

	const mockFilterBlocksAPI = (blocks: Array<BlockDocument>) => {
		server.use(
			http.post(buildApiUrl("/block_documents/filter"), () => {
				return HttpResponse.json(blocks);
			}),
		);
	};

	it("is stores block documents list data", async () => {
		// ------------ Mock API requests when cache is empty
		const mockList = seedBlocksData();
		mockFilterBlocksAPI(mockList);

		// ------------ Initialize hooks to test
		const { result } = renderHook(
			() => useSuspenseQuery(buildFilterBlockDocumentsQuery()),
			{ wrapper: createWrapper() },
		);

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
		expect(result.current.data).toEqual(mockList);
	});
});
