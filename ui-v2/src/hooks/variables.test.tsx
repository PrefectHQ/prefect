import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { components } from "@/api/prefect";

import {
	buildCountQuery,
	buildVariablesQuery,
	useCreateVariable,
	useDeleteVariable,
	useUpdateVariable,
	useVariables,
} from "./variables";

import { server } from "../../tests/mocks/node";

describe("variable hooks", () => {
	const seedVariables = () => [
		{
			id: "1",
			name: "my-variable",
			value: 123,
			created: "2021-01-01T00:00:00Z",
			updated: "2021-01-01T00:00:00Z",
			tags: ["tag1"],
		},
	];

	const mockFetchVariablesAPIs = (
		variables: Array<components["schemas"]["Variable"]>,
	) => {
		server.use(
			http.post("http://localhost:4200/api/variables/filter", () => {
				return HttpResponse.json(variables);
			}),
			http.post("http://localhost:4200/api/variables/count", () => {
				return HttpResponse.json(variables.length);
			}),
		);
	};

	const createQueryWrapper = ({ queryClient = new QueryClient() }) => {
		const QueryWrapper = ({ children }: { children: React.ReactNode }) => (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);
		return QueryWrapper;
	};

	const variableFilter = {
		offset: 0,
		sort: "CREATED_DESC" as const,
	};

	/**
	 * Data Management:
	 * - Asserts variable data and count is fetched based on the APIs invoked for the hook
	 */
	it("useVariables() is able to fetch from initial cache", async () => {
		const queryClient = new QueryClient();

		// ------------ Mock API requests when cache is empty
		const mockVariablesData = seedVariables();
		mockFetchVariablesAPIs(mockVariablesData);

		// ------------ Initialize hooks to test
		const { result } = renderHook(() => useVariables(variableFilter), {
			wrapper: createQueryWrapper({ queryClient }),
		});

		// ------------ Assert
		await waitFor(() => expect(result.current.isLoading).toBe(false));
		expect(result.current.isError).toBe(false);
		expect(result.current.totalCount).toEqual(1);
	});

	/**
	 * Data Management:
	 * - Asserts delete mutation API is called.
	 * - Upon delete mutation API being called, cache is invalidated and asserts cache invalidation APIS are called
	 */
	it("useDeleteVariable() invalidates cache and fetches updated value", async () => {
		const VARIABLE_ID_TO_DELETE = "1";
		const queryClient = new QueryClient();

		// ------------ Mock API requests after queries are invalidated
		const mockVariablesData = seedVariables().filter(
			(variable) => variable.id !== VARIABLE_ID_TO_DELETE,
		);
		mockFetchVariablesAPIs(mockVariablesData);

		// ------------ Initialize cache
		queryClient.setQueryData(
			buildVariablesQuery(variableFilter).queryKey,
			seedVariables(),
		);
		queryClient.setQueryData(
			buildCountQuery(variableFilter).queryKey,
			seedVariables().length,
		);

		// ------------ Initialize hooks to test
		const { result: useVariablesResult } = renderHook(
			() => useVariables(variableFilter),
			{ wrapper: createQueryWrapper({ queryClient }) },
		);

		const { result: useDeleteVariableResult } = renderHook(useDeleteVariable, {
			wrapper: createQueryWrapper({ queryClient }),
		});

		// ------------ Invoke mutation
		act(() =>
			useDeleteVariableResult.current.deleteVariable(VARIABLE_ID_TO_DELETE),
		);

		// ------------ Assert
		await waitFor(() =>
			expect(useDeleteVariableResult.current.isSuccess).toBe(true),
		);
		expect(useVariablesResult.current.variables.length).toEqual(0);
		expect(useVariablesResult.current.totalCount).toEqual(0);
		const deletedVariable = useVariablesResult.current.variables.find(
			(variable) => variable.id === VARIABLE_ID_TO_DELETE,
		);
		expect(deletedVariable).toBeUndefined();
	});

	/**
	 * Data Management:
	 * - Asserts create mutation API is called.
	 * - Upon create mutation API being called, cache is invalidated and asserts cache invalidation APIS are called
	 */
	it("useCreateVariable() invalidates cache and fetches updated value", async () => {
		const queryClient = new QueryClient();
		const MOCK_NEW_VARIABLE_ID = "2";
		const MOCK_NEW_VARIABLE = {
			name: "my-new-variable",
			value: 123,
			created: "2021-01-01T00:00:00Z",
			updated: "2021-01-01T00:00:00Z",
			tags: ["tag1"],
		};

		// ------------ Mock API requests after queries are invalidated
		const mockVariablesData = [
			...seedVariables(),
			{
				...MOCK_NEW_VARIABLE,
				id: MOCK_NEW_VARIABLE_ID,
			},
		];
		mockFetchVariablesAPIs(mockVariablesData);

		// ------------ Initialize cache
		queryClient.setQueryData(
			buildVariablesQuery(variableFilter).queryKey,
			seedVariables(),
		);
		queryClient.setQueryData(
			buildCountQuery(variableFilter).queryKey,
			seedVariables().length,
		);

		// ------------ Initialize hooks to test
		const { result: useVariablesResult } = renderHook(
			() => useVariables(variableFilter),
			{ wrapper: createQueryWrapper({ queryClient }) },
		);
		const { result: useCreateVariableResult } = renderHook(useCreateVariable, {
			wrapper: createQueryWrapper({ queryClient }),
		});

		// ------------ Invoke mutation
		act(() =>
			useCreateVariableResult.current.createVariable(MOCK_NEW_VARIABLE),
		);

		// ------------ Assert
		await waitFor(() =>
			expect(useCreateVariableResult.current.isSuccess).toBe(true),
		);
		expect(useVariablesResult.current.variables.length).toEqual(2);
		expect(useVariablesResult.current.totalCount).toEqual(2);
		const newVariable = useVariablesResult.current.variables.find(
			(variable) => variable.id === MOCK_NEW_VARIABLE_ID,
		);
		expect(newVariable).toMatchObject({
			...MOCK_NEW_VARIABLE,
			id: MOCK_NEW_VARIABLE_ID,
		});
	});

	/**
	 * Data Management:
	 * - Asserts update mutation API is called.
	 * - Upon update mutation API being called, cache is invalidated and asserts cache invalidation APIS are called
	 */
	it("useUpdateVariable() invalidates cache and fetches updated value", async () => {
		const queryClient = new QueryClient();
		const MOCK_UPDATE_VARIABLE_ID = "1";
		const MOCK_UPDATE_VARIABLE = {
			id: MOCK_UPDATE_VARIABLE_ID,
			name: "my-variable-updated",
			value: 1234,
			created: "2021-01-01T00:00:00Z",
			updated: "2021-01-01T00:00:00Z",
			tags: ["tag1"],
		};

		// ------------ Mock API requests after queries are invalidated
		const mockVariablesData = seedVariables().map((variable) =>
			variable.id === MOCK_UPDATE_VARIABLE_ID ? MOCK_UPDATE_VARIABLE : variable,
		);
		mockFetchVariablesAPIs(mockVariablesData);

		// ------------ Initialize cache
		queryClient.setQueryData(
			buildVariablesQuery(variableFilter).queryKey,
			seedVariables(),
		);
		queryClient.setQueryData(
			buildCountQuery(variableFilter).queryKey,
			seedVariables().length,
		);

		// ------------ Initialize hooks to test
		const { result: useVariablesResult } = renderHook(
			() => useVariables(variableFilter),
			{ wrapper: createQueryWrapper({ queryClient }) },
		);
		const { result: useUpdateVariableResult } = renderHook(useUpdateVariable, {
			wrapper: createQueryWrapper({ queryClient }),
		});

		// ------------ Invoke mutation
		act(() =>
			useUpdateVariableResult.current.updateVariable(MOCK_UPDATE_VARIABLE),
		);

		// ------------ Assert
		await waitFor(() =>
			expect(useUpdateVariableResult.current.isSuccess).toBe(true),
		);
		expect(useVariablesResult.current.variables.length).toEqual(1);
		expect(useVariablesResult.current.totalCount).toEqual(1);
		const updatedVariable = useVariablesResult.current.variables.find(
			(variable) => variable.id === MOCK_UPDATE_VARIABLE_ID,
		);
		expect(updatedVariable).toMatchObject(MOCK_UPDATE_VARIABLE);
	});
});
