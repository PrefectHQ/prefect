import { QueryClient, useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { createFakeVariable } from "@/mocks/create-fake-variable";
import type { Variable } from "./index";
import {
	buildCountVariablesQuery,
	buildFilterVariablesQuery,
	queryKeyFactory,
	useCreateVariable,
	useDeleteVariable,
	useUpdateVariable,
} from "./index";

describe("variables api", () => {
	const mockFetchVariablesAPI = (
		variables: Array<Variable>,
		count: number = variables.length,
	) => {
		server.use(
			http.post(buildApiUrl("/variables/filter"), () => {
				return HttpResponse.json(variables);
			}),
			http.post(buildApiUrl("/variables/count"), () => {
				return HttpResponse.json(count);
			}),
		);
	};

	describe("buildFilterVariablesQuery", () => {
		it("fetches filtered variables with default parameters", async () => {
			const variable = createFakeVariable();
			mockFetchVariablesAPI([variable]);

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildFilterVariablesQuery()),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.data).toEqual([variable]);
			});
		});

		it("fetches filtered variables with custom filter parameters", async () => {
			const variable = createFakeVariable();
			mockFetchVariablesAPI([variable]);

			const filter = {
				offset: 10,
				limit: 25,
				sort: "NAME_ASC" as const,
			};

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildFilterVariablesQuery(filter)),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => expect(result.current.isSuccess).toBe(true));
			expect(result.current.data).toEqual([variable]);
		});
	});

	describe("buildCountVariablesQuery", () => {
		it("fetches variable count with no filter (total count)", async () => {
			mockFetchVariablesAPI([createFakeVariable()], 5);

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildCountVariablesQuery()),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.data).toBe(5);
			});
		});

		it("fetches variable count with custom filter", async () => {
			mockFetchVariablesAPI([createFakeVariable()], 3);

			const filter = {
				offset: 0,
				sort: "CREATED_DESC" as const,
				variables: {
					operator: "and_" as const,
					name: { like_: "test" },
				},
			};

			const queryClient = new QueryClient();
			const { result } = renderHook(
				() => useSuspenseQuery(buildCountVariablesQuery(filter)),
				{ wrapper: createWrapper({ queryClient }) },
			);

			await waitFor(() => {
				expect(result.current.data).toBe(3);
			});
		});
	});

	describe("useCreateVariable", () => {
		const mockCreateVariableAPI = (variable: Variable) => {
			server.use(
				http.post(buildApiUrl("/variables"), () => {
					return HttpResponse.json(variable);
				}),
			);
		};

		it("invalidates cache and fetches updated value", async () => {
			const mockVariable = createFakeVariable();
			const newVariable = createFakeVariable({ name: "new-variable" });
			mockFetchVariablesAPI([mockVariable, newVariable]);
			mockCreateVariableAPI(newVariable);
			const queryClient = new QueryClient();

			queryClient.setQueryData(queryKeyFactory["lists-filter"](), [
				mockVariable,
			]);

			const { result: useListVariablesResult } = renderHook(
				() => useQuery(buildFilterVariablesQuery()),
				{ wrapper: createWrapper({ queryClient }) },
			);

			const { result: useCreateVariableResult } = renderHook(
				useCreateVariable,
				{ wrapper: createWrapper({ queryClient }) },
			);

			act(() =>
				useCreateVariableResult.current.createVariable({
					name: newVariable.name,
					value: newVariable.value,
					tags: newVariable.tags,
				}),
			);

			await waitFor(() =>
				expect(useCreateVariableResult.current.isSuccess).toBe(true),
			);
			expect(useListVariablesResult.current.data).toHaveLength(2);
			const createdVariable = useListVariablesResult.current.data?.find(
				(variable) => variable.name === newVariable.name,
			);
			expect(createdVariable).toBeDefined();
		});
	});

	describe("useUpdateVariable", () => {
		it("invalidates cache and fetches updated value", async () => {
			const MOCK_ID = "0";
			const mockVariable = createFakeVariable({
				id: MOCK_ID,
				name: "original-name",
			});
			const updatedMockVariable = { ...mockVariable, name: "updated-name" };
			mockFetchVariablesAPI([updatedMockVariable]);

			const queryClient = new QueryClient();

			queryClient.setQueryData(queryKeyFactory.all(), [mockVariable]);

			const { result: useListVariablesResult } = renderHook(
				() => useQuery(buildFilterVariablesQuery()),
				{ wrapper: createWrapper({ queryClient }) },
			);

			const { result: useUpdateVariableResult } = renderHook(
				useUpdateVariable,
				{ wrapper: createWrapper({ queryClient }) },
			);

			act(() =>
				useUpdateVariableResult.current.updateVariable({
					id: MOCK_ID,
					name: "updated-name",
				}),
			);

			await waitFor(() =>
				expect(useUpdateVariableResult.current.isSuccess).toBe(true),
			);
			const result = useListVariablesResult.current.data?.find(
				(variable) => variable.id === MOCK_ID,
			);
			expect(result).toEqual(updatedMockVariable);
		});
	});

	describe("useDeleteVariable", () => {
		it("invalidates cache and fetches updated value", async () => {
			const mockVariable = createFakeVariable();
			mockFetchVariablesAPI([]);

			const queryClient = new QueryClient();

			queryClient.setQueryData(queryKeyFactory.all(), [mockVariable]);

			const { result: useListVariablesResult } = renderHook(
				() => useQuery(buildFilterVariablesQuery()),
				{ wrapper: createWrapper({ queryClient }) },
			);

			const { result: useDeleteVariableResult } = renderHook(
				useDeleteVariable,
				{ wrapper: createWrapper({ queryClient }) },
			);

			act(() =>
				useDeleteVariableResult.current.deleteVariable(mockVariable.id),
			);

			await waitFor(() =>
				expect(useDeleteVariableResult.current.isSuccess).toBe(true),
			);
			expect(useListVariablesResult.current.data).toHaveLength(0);
		});
	});
});
