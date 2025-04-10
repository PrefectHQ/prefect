import { QueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { createFakeBlockDocument } from "@/mocks";

import {
	type BlockDocument,
	buildCountFilterBlockDocumentsQuery,
	buildGetBlockDocumentQuery,
	buildListFilterBlockDocumentsQuery,
	queryKeyFactory,
	useDeleteBlockDocument,
	useUpdateBlockDocument,
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

	const mockGetBlockAPI = (block: BlockDocument) => {
		server.use(
			http.get(buildApiUrl("/block_documents/:id"), () => {
				return HttpResponse.json(block);
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

	it("is gets single block document data by id", async () => {
		// ------------ Mock API requests when cache is empty
		const mockData = createFakeBlockDocument();
		mockGetBlockAPI(mockData);

		// ------------ Initialize hooks to test
		const { result } = renderHook(
			() => useSuspenseQuery(buildGetBlockDocumentQuery(mockData.id)),
			{ wrapper: createWrapper() },
		);

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
		expect(result.current.data).toEqual(mockData);
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

	describe("useDeleteBlockDocument", () => {
		it("invalidates cache and fetches updated value", async () => {
			const mockBlockDocument = createFakeBlockDocument();
			mockFilterListBlocksAPI([]);

			const queryClient = new QueryClient();
			const FILTER = {
				offset: 0,
				sort: "NAME_ASC" as const,
				include_secrets: false,
			};
			queryClient.setQueryData(queryKeyFactory.listFilter(FILTER), [
				mockBlockDocument,
			]);

			const { result: useListBlockDocumentsResult } = renderHook(
				() => useSuspenseQuery(buildListFilterBlockDocumentsQuery(FILTER)),
				{ wrapper: createWrapper({ queryClient }) },
			);

			const { result: useDeleteBlockDocumentResult } = renderHook(
				useDeleteBlockDocument,
				{ wrapper: createWrapper({ queryClient }) },
			);

			act(() =>
				useDeleteBlockDocumentResult.current.deleteBlockDocument(
					mockBlockDocument.id,
				),
			);

			await waitFor(() =>
				expect(useDeleteBlockDocumentResult.current.isSuccess).toBe(true),
			);
			expect(useListBlockDocumentsResult.current.data).toHaveLength(0);
		});
	});

	describe("useUpdateBlockDocument", () => {
		it("invalidates cache and fetches updated value", async () => {
			const mockBlockDocument = createFakeBlockDocument();
			const updatedBlockDocument = {
				...mockBlockDocument,
				data: { foo: "bar" },
			};
			const queryClient = new QueryClient();
			const FILTER = {
				offset: 0,
				sort: "NAME_ASC" as const,
				include_secrets: false,
			};
			queryClient.setQueryData(queryKeyFactory.listFilter(FILTER), [
				mockBlockDocument,
			]);
			mockFilterListBlocksAPI([updatedBlockDocument]);

			queryClient.setQueryData(queryKeyFactory.listFilter(FILTER), [
				mockBlockDocument,
			]);

			const { result: useListBlockDocumentsResult } = renderHook(
				() => useSuspenseQuery(buildListFilterBlockDocumentsQuery(FILTER)),
				{ wrapper: createWrapper({ queryClient }) },
			);

			const { result: useUpdateBlockDocumentResult } = renderHook(
				useUpdateBlockDocument,
				{ wrapper: createWrapper({ queryClient }) },
			);

			act(() =>
				useUpdateBlockDocumentResult.current.updateBlockDocument({
					...updatedBlockDocument,
					merge_existing_data: false,
				}),
			);

			await waitFor(() =>
				expect(useUpdateBlockDocumentResult.current.isSuccess).toBe(true),
			);
			expect(useListBlockDocumentsResult.current.data).toEqual([
				updatedBlockDocument,
			]);
		});
	});
});
