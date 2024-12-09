import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import {
  type BlockDocument,
  queryKeyFactory,
  useCreateBlockDocument,
  useDeleteBlockDocument,
  useListBlockDocuments,
  useUpdateBlockDocument,
} from "./block-documents";

import { server } from "../../tests/mocks/node";

describe("block documents hooks", () => {
  const seedBlockDocuments = () => [
    {
      id: "0",
      created: "2021-01-01T00:00:00Z",
      updated: "2021-01-01T00:00:00Z",
      name: "block document 0",
      data: {},
      block_schema_id: "schema-0",
      block_type_id: "type-0",
      is_anonymous: false,
      block_document_references: {}
    },
  ];

  const mockFetchBlockDocumentsAPI = (
    blockDocuments: Array<BlockDocument>,
  ) => {
    server.use(
      http.post(
        "http://localhost:4200/api/v2/block_documents/filter",
        () => {
          return HttpResponse.json(blockDocuments);
        },
      ),
    );
  };

  const createQueryWrapper = ({ queryClient = new QueryClient() }) => {
    const QueryWrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    return QueryWrapper;
  };
  const filter = {
    block_documents: { operator: "and_" as const, is_anonymous: { eq_: false } },
    include_secrets: false,
    sort: null,
    offset: 0,
    limit: undefined
  };

  it("stores list data into the appropriate list query when using useQuery()", async () => {
    const mockList = seedBlockDocuments();
    mockFetchBlockDocumentsAPI(mockList);
    const { result } = renderHook(
      () => useListBlockDocuments(filter),
      { wrapper: createQueryWrapper({}) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockList);
  });

  it("useDeleteBlockDocument() invalidates cache and fetches updated value", async () => {
    const ID_TO_DELETE = "0";
    const queryClient = new QueryClient();

    const mockData = seedBlockDocuments().filter(
      (doc) => doc.id !== ID_TO_DELETE,
    );
    mockFetchBlockDocumentsAPI(mockData);

    queryClient.setQueryData(
      queryKeyFactory.list({
        block_documents: { operator: "and_" as const, is_anonymous: { eq_: false } },
        include_secrets: false,
        sort: null,
        offset: 0,
        limit: undefined
      }),
      seedBlockDocuments(),
    );

    const { result: useListBlockDocumentsResult } = renderHook(
      () => useListBlockDocuments(filter),
      { wrapper: createQueryWrapper({ queryClient }) },
    );

    const { result: useDeleteBlockDocumentResult } = renderHook(
      useDeleteBlockDocument,
      { wrapper: createQueryWrapper({ queryClient }) },
    );

    act(() =>
      useDeleteBlockDocumentResult.current.deleteBlockDocument(
        ID_TO_DELETE,
      ),
    );

    await waitFor(() =>
      expect(useDeleteBlockDocumentResult.current.isSuccess).toBe(
        true,
      ),
    );
    expect(useListBlockDocumentsResult.current.data).toHaveLength(0);
  });

  it("useCreateBlockDocument() invalidates cache and fetches updated value", async () => {
    const queryClient = new QueryClient();
    const MOCK_NEW_DOC_ID = "1";
    const MOCK_NEW_DOC = {
      name: "block document 1",
      data: {},
      block_schema_id: "schema-1",
      block_type_id: "type-1",
      is_anonymous: false
    };

    const NEW_DOC_DATA = {
      ...MOCK_NEW_DOC,
      id: MOCK_NEW_DOC_ID,
      created: "2021-01-01T00:00:00Z",
      updated: "2021-01-01T00:00:00Z",
      block_document_references: {}
    };

    const mockData = [...seedBlockDocuments(), NEW_DOC_DATA];
    mockFetchBlockDocumentsAPI(mockData);

    queryClient.setQueryData(
      queryKeyFactory.list(filter),
      seedBlockDocuments(),
    );

    const { result: useListBlockDocumentsResult } = renderHook(
      () => useListBlockDocuments(filter),
      { wrapper: createQueryWrapper({ queryClient }) },
    );
    const { result: useCreateBlockDocumentResult } = renderHook(
      useCreateBlockDocument,
      { wrapper: createQueryWrapper({ queryClient }) },
    );

    act(() =>
      useCreateBlockDocumentResult.current.createBlockDocument(
        MOCK_NEW_DOC,
      ),
    );

    await waitFor(() =>
      expect(useCreateBlockDocumentResult.current.isSuccess).toBe(
        true,
      ),
    );
    expect(useListBlockDocumentsResult.current.data).toHaveLength(2);
    const newDoc = useListBlockDocumentsResult.current.data?.find(
      (doc) => doc.id === MOCK_NEW_DOC_ID,
    );
    expect(newDoc).toMatchObject(NEW_DOC_DATA);
  });

  it("useUpdateBlockDocument() invalidates cache and fetches updated value", async () => {
    const queryClient = new QueryClient();
    const MOCK_UPDATE_DOC_ID = "0";
    const UPDATED_DOC_BODY = {
      name: "block document updated",
      data: {},
      block_schema_id: "schema-0",
      block_type_id: "type-0",
      is_anonymous: false
    };
    const UPDATED_DOC = {
      ...UPDATED_DOC_BODY,
      id: MOCK_UPDATE_DOC_ID,
      created: "2021-01-01T00:00:00Z",
      updated: "2021-01-01T00:00:00Z",
      block_document_references: {}
    };

    const mockData = seedBlockDocuments().map((doc) =>
      doc.id === MOCK_UPDATE_DOC_ID ? UPDATED_DOC : doc,
    );
    mockFetchBlockDocumentsAPI(mockData);

    queryClient.setQueryData(
      queryKeyFactory.list(filter),
      seedBlockDocuments(),
    );

    const { result: useListBlockDocumentsResult } = renderHook(
      () => useListBlockDocuments(filter),
      { wrapper: createQueryWrapper({ queryClient }) },
    );

    const { result: useUpdateBlockDocumentResult } = renderHook(
      useUpdateBlockDocument,
      { wrapper: createQueryWrapper({ queryClient }) },
    );

    act(() =>
      useUpdateBlockDocumentResult.current.updateBlockDocument(
        {
          id: MOCK_UPDATE_DOC_ID,
          ...UPDATED_DOC_BODY,
          merge_existing_data: false
        },
      ),
    );

    await waitFor(() =>
      expect(useUpdateBlockDocumentResult.current.isSuccess).toBe(
        true,
      ),
    );

    const doc = useListBlockDocumentsResult.current.data?.find(
      (doc) => doc.id === MOCK_UPDATE_DOC_ID,
    );
    expect(doc).toMatchObject(UPDATED_DOC);
  });
});
