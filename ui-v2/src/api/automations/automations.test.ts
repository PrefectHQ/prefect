import { QueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import { createFakeAutomation } from "@/mocks";

import {
	type Automation,
	buildGetAutomationQuery,
	buildListAutomationsQuery,
	buildListAutomationsRelatedQuery,
	queryKeyFactory,
	useCreateAutomation,
	useDeleteAutomation,
	useUpdateAutomation,
} from "./automations";

describe("automations queries and mutations", () => {
	const seedAutomationsData = () => [
		createFakeAutomation({ id: "0" }),
		createFakeAutomation({ id: "1" }),
	];

	const mockFetchListAutomationsAPI = (automations: Array<Automation>) => {
		server.use(
			http.post(buildApiUrl("/automations/filter"), () => {
				return HttpResponse.json(automations);
			}),
		);
	};

	const mockFetchGetAutomationsAPI = (automation: Automation) => {
		server.use(
			http.get(buildApiUrl("/automations/:id"), () => {
				return HttpResponse.json(automation);
			}),
		);
	};

	const mockFetchListRelatedAutomationsAPI = (
		automations: Array<Automation>,
	) => {
		server.use(
			http.get(buildApiUrl("/automations/related-to/:resource_id"), () => {
				return HttpResponse.json(automations);
			}),
		);
	};

	const filter = { sort: "CREATED_DESC", offset: 0 } as const;

	it("is stores automation list data", async () => {
		// ------------ Mock API requests when cache is empty
		const mockList = seedAutomationsData();
		mockFetchListAutomationsAPI(mockList);

		// ------------ Initialize hooks to test
		const { result } = renderHook(
			() => useSuspenseQuery(buildListAutomationsQuery(filter)),
			{ wrapper: createWrapper() },
		);

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
		expect(result.current.data).toEqual(mockList);
	});

	it("is stores automation list data based on resource id relation", async () => {
		// ------------ Mock API requests when cache is empty
		const mockList = seedAutomationsData();
		mockFetchListRelatedAutomationsAPI(mockList);

		// ------------ Initialize hooks to test
		const { result } = renderHook(
			() =>
				useSuspenseQuery(
					buildListAutomationsRelatedQuery("prefect.deployment.1234"),
				),
			{ wrapper: createWrapper() },
		);

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
		expect(result.current.data).toEqual(mockList);
	});

	it("is retrieves single automation data", async () => {
		// ------------ Mock API requests when cache is empty
		const MOCK_ID = "0";
		const mockData = createFakeAutomation({ id: MOCK_ID });
		mockFetchGetAutomationsAPI(mockData);

		// ------------ Initialize hooks to test
		const { result } = renderHook(
			() => useSuspenseQuery(buildGetAutomationQuery(MOCK_ID)),
			{ wrapper: createWrapper() },
		);

		// ------------ Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
		expect(result.current.data).toEqual(mockData);
	});

	it("useDeleteAutomation is able to call delete API and fetches updated cache", async () => {
		const ID_TO_DELETE = "0";
		const queryClient = new QueryClient();

		// ------------ Mock API requests after queries are invalidated
		const mockData = seedAutomationsData().filter(
			(automation) => automation.id !== ID_TO_DELETE,
		);
		mockFetchListAutomationsAPI(mockData);

		// ------------ Initialize cache
		queryClient.setQueryData(
			queryKeyFactory.filter(filter),
			seedAutomationsData(),
		);

		// ------------ Initialize hooks to test
		const { result: useDeleteAutomationResult } = renderHook(
			useDeleteAutomation,
			{ wrapper: createWrapper({ queryClient }) },
		);

		const { result: useListAutomationsResult } = renderHook(
			() => useSuspenseQuery(buildListAutomationsQuery()),
			{ wrapper: createWrapper({ queryClient }) },
		);

		// ------------ Invoke mutation
		act(() => useDeleteAutomationResult.current.deleteAutomation(ID_TO_DELETE));

		// ------------ Assert
		await waitFor(() =>
			expect(useDeleteAutomationResult.current.isSuccess).toBe(true),
		);
		expect(useListAutomationsResult.current.data).toHaveLength(1);
	});

	it("useCreateAutomation() invalidates cache and fetches updated value", async () => {
		const queryClient = new QueryClient();
		const MOCK_NEW_DATA_ID = "2";
		const NEW_AUTOMATION_DATA = createFakeAutomation({
			id: MOCK_NEW_DATA_ID,
			created: "2021-01-01T00:00:00Z",
			updated: "2021-01-01T00:00:00Z",
		});

		const {
			/* eslint-disable @typescript-eslint/no-unused-vars */
			id: _id,
			created: _created,
			updated: _updated,
			/* eslint-enable @typescript-eslint/no-unused-vars */
			...CREATE_AUTOMATION_PAYLOAD
		} = NEW_AUTOMATION_DATA;

		// ------------ Mock API requests after queries are invalidated
		const mockData = [...seedAutomationsData(), NEW_AUTOMATION_DATA];
		mockFetchListAutomationsAPI(mockData);

		// ------------ Initialize cache
		queryClient.setQueryData(
			queryKeyFactory.filter(filter),
			seedAutomationsData(),
		);

		// ------------ Initialize hooks to test
		const { result: useCreateAutomationResult } = renderHook(
			useCreateAutomation,
			{ wrapper: createWrapper({ queryClient }) },
		);

		const { result: useListAutomationsResult } = renderHook(
			() => useSuspenseQuery(buildListAutomationsQuery(filter)),
			{ wrapper: createWrapper({ queryClient }) },
		);

		// ------------ Invoke mutation
		act(() =>
			useCreateAutomationResult.current.createAutomation(
				CREATE_AUTOMATION_PAYLOAD,
			),
		);

		// ------------ Assert
		await waitFor(() =>
			expect(useCreateAutomationResult.current.isSuccess).toBe(true),
		);

		expect(useListAutomationsResult.current.data).toHaveLength(3);

		const newAutomation = useListAutomationsResult.current.data?.find(
			(automation) => automation.id === MOCK_NEW_DATA_ID,
		);
		expect(newAutomation).toMatchObject(NEW_AUTOMATION_DATA);
	});

	it("useUpdateAutomation() invalidates cache and fetches updated value", async () => {
		const queryClient = new QueryClient();
		const MOCK_INITIAL_DATA = seedAutomationsData();
		const MOCK_EDIT_ID = "1";
		const EDITED_AUTOMATION = MOCK_INITIAL_DATA.find(
			(automation) => automation.id === MOCK_EDIT_ID,
		);
		if (!EDITED_AUTOMATION) {
			throw new Error("Expected 'EDITED_AUTOMATION'");
		}
		EDITED_AUTOMATION.name = "Edited automation name";

		const MOCK_EDITED_DATA = MOCK_INITIAL_DATA.map((automation) =>
			automation.id === MOCK_EDIT_ID ? EDITED_AUTOMATION : automation,
		);

		// ------------ Mock API requests after queries are invalidated
		mockFetchListAutomationsAPI(MOCK_EDITED_DATA);

		// ------------ Initialize cache
		queryClient.setQueryData(
			queryKeyFactory.filter(filter),
			seedAutomationsData(),
		);

		// ------------ Initialize hooks to test
		const { result: useUpdateAutomationResult } = renderHook(
			useUpdateAutomation,
			{ wrapper: createWrapper({ queryClient }) },
		);

		const { result: useListAutomationsResult } = renderHook(
			() => useSuspenseQuery(buildListAutomationsQuery(filter)),
			{ wrapper: createWrapper({ queryClient }) },
		);

		// ------------ Invoke mutation
		const { id, enabled } = EDITED_AUTOMATION;
		act(() =>
			useUpdateAutomationResult.current.updateAutomation({
				id,
				enabled,
			}),
		);

		// ------------ Assert
		await waitFor(() =>
			expect(useUpdateAutomationResult.current.isSuccess).toBe(true),
		);

		const editedAutomation = useListAutomationsResult.current.data?.find(
			(automation) => automation.id === MOCK_EDIT_ID,
		);
		expect(editedAutomation).toMatchObject(EDITED_AUTOMATION);
	});
});
