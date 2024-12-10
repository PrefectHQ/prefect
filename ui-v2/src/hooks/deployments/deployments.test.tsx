import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import {
	type Deployment,
	useCountDeployments,
	usePaginateDeployments,
} from "./index";

import { server } from "@tests/mocks";

describe("deployments hooks", () => {
	const seedDeployments = (): Deployment[] => [
		{
			id: "deployment-1",
			created: "2021-01-01T00:00:00Z",
			updated: "2021-01-01T00:00:00Z",
			name: "Test Deployment 1",
			version: "1.0",
			tags: ["test"],
			schedules: [],
			work_queue_name: "default",
			work_pool_name: "default",
			parameter_openapi_schema: {},
			status: "READY",
			description: null,
			storage_document_id: null,
			infrastructure_document_id: null,
			path: null,
			entrypoint: null,
			flow_id: "test-flow-id",
			paused: false,
			enforce_parameter_schema: false,
		},
	];

	const mockFetchDeploymentsAPI = (deployments: Array<Deployment>) => {
		server.use(
			http.post("http://localhost:4200/api/deployments/paginate", () => {
				return HttpResponse.json(deployments);
			}),
		);
	};

	const mockFetchDeploymentsCountAPI = (count: number) => {
		server.use(
			http.post("http://localhost:4200/api/deployments/count", () => {
				return HttpResponse.json(count);
			}),
		);
	};

	const createQueryWrapper = ({ queryClient = new QueryClient() }) => {
		const QueryWrapper = ({ children }: { children: React.ReactNode }) => (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);
		return QueryWrapper;
	};

	const paginationFilter = {
		page: 1,
		limit: 10,
		sort: "NAME_ASC" as const,
	};

	const countFilter = {
		offset: 0,
		sort: "NAME_ASC" as const,
	};

	/**
	 * Data Management:
	 * - Asserts deployment list data is fetched and stored correctly
	 */
	it("stores paginated deployments data into the appropriate query", async () => {
		// Mock API response
		const mockList = seedDeployments();
		mockFetchDeploymentsAPI(mockList);

		// Initialize hook
		const { result } = renderHook(
			() => usePaginateDeployments(paginationFilter),
			{
				wrapper: createQueryWrapper({}),
			},
		);

		// Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
		expect(result.current.data).toEqual(mockList);
	});

	/**
	 * Data Management:
	 * - Asserts deployment count data is fetched and stored correctly
	 */
	it("stores deployment count data into the appropriate query", async () => {
		// Mock API response
		const mockCount = 1;
		mockFetchDeploymentsCountAPI(mockCount);

		// Initialize hook
		const { result } = renderHook(() => useCountDeployments(countFilter), {
			wrapper: createQueryWrapper({}),
		});

		// Assert
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
		expect(result.current.data).toEqual(mockCount);
	});
});
