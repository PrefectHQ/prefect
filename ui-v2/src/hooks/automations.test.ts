import { useSuspenseQuery } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { createWrapper, server } from "@tests/utils";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { createFakeAutomation } from "@/mocks";

import {
	type Automation,
	buildGetAutomationQuery,
	buildListAutomationsQuery,
} from "./automations";

describe("automations queries", () => {
	const seedAutomationsData = () => [
		createFakeAutomation(),
		createFakeAutomation(),
	];

	const mockFetchListAutomationsAPI = (automations: Array<Automation>) => {
		server.use(
			http.post("http://localhost:4200/api/automations/filter", () => {
				return HttpResponse.json(automations);
			}),
		);
	};

	const mockFetchGetAutomationsAPI = (automation: Automation) => {
		server.use(
			http.get("http://localhost:4200/api/automations/:id", () => {
				return HttpResponse.json(automation);
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
});
