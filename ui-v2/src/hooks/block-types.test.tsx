import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import {
  type BlockType,
  queryKeyFactory,
  useCreateBlockType,
  useUpdateBlockType,
  useListBlockTypes,
} from "./block-types";

import { server } from "../../tests/mocks/node";

describe("block types hooks", () => {
  const seedBlockTypes = () => [
    {
      id: "0",
      created: "2021-01-01T00:00:00Z",
      updated: "2021-01-01T00:00:00Z",
      name: "block type 0",
      slug: "block-type-0",
      logo_url: "https://example.com/logo.png",
      documentation_url: "https://example.com/docs",
      description: "A test block type",
      code_example: "example code",
      is_protected: false
    },
  ];

  const mockFetchBlockTypesAPI = (
    blockTypes: Array<BlockType>,
  ) => {
    server.use(
      http.post(
        "http://localhost:4200/api/v2/block_types/filter",
        () => {
          return HttpResponse.json(blockTypes);
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
    block_types: { name: null, slug: null },
    offset: 0,
    limit: undefined
  };

  it("stores list data into the appropriate list query when using useQuery()", async () => {
    const mockList = seedBlockTypes();
    mockFetchBlockTypesAPI(mockList);
    const { result } = renderHook(
      () => useListBlockTypes(filter),
      { wrapper: createQueryWrapper({}) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockList);
  });

  it("useCreateBlockType() invalidates cache and fetches updated value", async () => {
    const queryClient = new QueryClient();
    const MOCK_NEW_TYPE_ID = "1";
    const MOCK_NEW_TYPE = {
      name: "block type 1",
      slug: "block-type-1",
      logo_url: "https://example.com/logo2.png",
      documentation_url: "https://example.com/docs2",
      description: "Another test block type",
      code_example: "example code 2",
      is_protected: false
    };

    const NEW_TYPE_DATA = {
      ...MOCK_NEW_TYPE,
      id: MOCK_NEW_TYPE_ID,
      created: "2021-01-01T00:00:00Z",
      updated: "2021-01-01T00:00:00Z"
    };

    const mockData = [...seedBlockTypes(), NEW_TYPE_DATA];
    mockFetchBlockTypesAPI(mockData);

    queryClient.setQueryData(
      queryKeyFactory.list(filter),
      seedBlockTypes(),
    );

    const { result: useListBlockTypesResult } = renderHook(
      () => useListBlockTypes(filter),
      { wrapper: createQueryWrapper({ queryClient }) },
    );
    const { result: useCreateBlockTypeResult } = renderHook(
      useCreateBlockType,
      { wrapper: createQueryWrapper({ queryClient }) },
    );

    act(() =>
      useCreateBlockTypeResult.current.createBlockType(
        MOCK_NEW_TYPE,
      ),
    );

    await waitFor(() =>
      expect(useCreateBlockTypeResult.current.isSuccess).toBe(
        true,
      ),
    );
    expect(useListBlockTypesResult.current.data).toHaveLength(2);
    const newType = useListBlockTypesResult.current.data?.find(
      (type) => type.id === MOCK_NEW_TYPE_ID,
    );
    expect(newType).toMatchObject(NEW_TYPE_DATA);
  });

  it("useUpdateBlockType() invalidates cache and fetches updated value", async () => {
    const queryClient = new QueryClient();
    const MOCK_UPDATE_TYPE_ID = "0";
    const UPDATED_TYPE_BODY = {
      name: "block type updated",
      slug: "block-type-updated",
      logo_url: "https://example.com/logo-updated.png",
      documentation_url: "https://example.com/docs-updated",
      description: "An updated test block type",
      code_example: "updated example code",
      is_protected: false
    };
    const UPDATED_TYPE = {
      ...UPDATED_TYPE_BODY,
      id: MOCK_UPDATE_TYPE_ID,
      created: "2021-01-01T00:00:00Z",
      updated: "2021-01-01T00:00:00Z"
    };

    const mockData = seedBlockTypes().map((type) =>
      type.id === MOCK_UPDATE_TYPE_ID ? UPDATED_TYPE : type,
    );
    mockFetchBlockTypesAPI(mockData);

    queryClient.setQueryData(
      queryKeyFactory.list(filter),
      seedBlockTypes(),
    );

    const { result: useListBlockTypesResult } = renderHook(
      () => useListBlockTypes(filter),
      { wrapper: createQueryWrapper({ queryClient }) },
    );

    const { result: useUpdateBlockTypeResult } = renderHook(
      useUpdateBlockType,
      { wrapper: createQueryWrapper({ queryClient }) },
    );

    act(() =>
      useUpdateBlockTypeResult.current.updateBlockType(
        {
          id: MOCK_UPDATE_TYPE_ID,
          ...UPDATED_TYPE_BODY
        },
      ),
    );

    await waitFor(() =>
      expect(useUpdateBlockTypeResult.current.isSuccess).toBe(
        true,
      ),
    );

    const type = useListBlockTypesResult.current.data?.find(
      (type) => type.id === MOCK_UPDATE_TYPE_ID,
    );
    expect(type).toMatchObject(UPDATED_TYPE);
  });
});
